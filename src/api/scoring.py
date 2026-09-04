"""
Live Scoring Service
========================

The actual scoring logic behind the API, deliberately kept as plain
Python with no FastAPI/Pydantic dependency — so it can be (and is)
tested directly in this environment, even though `fastapi` itself
isn't installed here (see `docs/api_report.md`, Section 0). `main.py`
is a thin HTTP wrapper around this class; all the real work — warming
up sender history, computing live features, building the model input,
scoring, and combining with rules — happens here.

On startup, this loads the full historical dataset once to "warm
start" `RealtimeFeatureComputer` (Phase 7's own module) so senders
with existing transaction history get correct features on their very
next transaction, rather than being treated as brand new. In the real
architecture (Phase 9), this warm-up would be replaced by reading
existing state from Redis instead of replaying a CSV — this in-memory
version is an honest stand-in, not the final design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

import joblib
import pandas as pd

from src.api.feature_lookup import NO_PRIOR_TXN_SENTINEL_SECONDS, RealtimeFeatureComputer
from src.models.decision_engine import build_explanation, combine_risk_level, decision_from_risk_level
from src.models.feature_prep import BOOLEAN_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES
from src.rules.engine import RuleEngine

DEFAULT_MODEL_PATH = "models/gradient_boosting_model.joblib"
DEFAULT_HISTORICAL_DATA_PATH = "data/processed/behavioral_features.csv"


@dataclass
class ScoreResult:
    transaction_id: str
    fraud_probability: float
    risk_level: str
    triggered_rules: list
    final_decision: str
    explanation: str
    scored_at: str


def _get_or(mapping: Mapping[str, Any], key: str, default: Any) -> Any:
    value = mapping.get(key)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return value


def enrich_transaction(raw: dict, computer: RealtimeFeatureComputer) -> dict:
    """Attach derived time fields and live-computed behavioral features
    to a raw incoming transaction."""
    timestamp = raw.get("timestamp") or datetime.now(timezone.utc)
    if isinstance(timestamp, str):
        timestamp = pd.to_datetime(timestamp)

    enriched = dict(raw)
    enriched["timestamp"] = timestamp
    enriched["hour_of_day"] = timestamp.hour
    enriched["day_of_week"] = timestamp.weekday()

    behavioral = computer.compute_features(enriched)
    enriched.update(behavioral)
    return enriched


def build_model_input(enriched: dict, feature_names: list, global_median_amount: float) -> pd.DataFrame:
    """Build a single-row feature vector matching the trained model's
    expected columns, applying the same imputation rules as
    src/models/feature_prep.py's batch pipeline (Phase 5) — just
    computed for one transaction using a fixed reference value instead
    of a batch median, since there's no batch to compute one from at
    request time."""
    numeric = {
        "amount": enriched["amount"],
        "hour_of_day": enriched["hour_of_day"],
        "day_of_week": enriched["day_of_week"],
        "sender_prior_txn_count": enriched["sender_prior_txn_count"],
        "sender_avg_amount_prior": _get_or(enriched, "sender_avg_amount_prior", global_median_amount),
        "sender_std_amount_prior": _get_or(enriched, "sender_std_amount_prior", 0.0),
        "amount_zscore_vs_sender": _get_or(enriched, "amount_zscore_vs_sender", 0.0),
        "amount_ratio_vs_sender_avg": _get_or(enriched, "amount_ratio_vs_sender_avg", 1.0),
        "seconds_since_last_txn": _get_or(enriched, "seconds_since_last_txn", NO_PRIOR_TXN_SENTINEL_SECONDS),
        "sender_txn_count_last_1h": enriched["sender_txn_count_last_1h"],
        "sender_txn_count_last_24h": enriched["sender_txn_count_last_24h"],
        "device_seen_count_prior": enriched["device_seen_count_prior"],
        "location_seen_count_prior": enriched["location_seen_count_prior"],
        "receiver_seen_count_prior": enriched["receiver_seen_count_prior"],
        "sender_typical_hour_prior": _get_or(enriched, "sender_typical_hour_prior", enriched["hour_of_day"]),
        "hour_deviation_from_typical": _get_or(enriched, "hour_deviation_from_typical", 0.0),
    }
    assert set(numeric.keys()) == set(NUMERIC_FEATURES), "numeric feature set drifted from feature_prep.py"

    boolean = {name: float(enriched[name]) for name in BOOLEAN_FEATURES}

    categorical = {}
    for cat_col in CATEGORICAL_FEATURES:
        value = enriched.get(cat_col, "")
        # matches pandas.get_dummies' column naming from feature_prep.py
        for known_value in ("P2P", "P2M", "COLLECT"):
            categorical[f"{cat_col}_{known_value}"] = 1.0 if value == known_value else 0.0

    full_row = {**numeric, **boolean, **categorical}
    X = pd.DataFrame([full_row]).reindex(columns=feature_names, fill_value=0.0)
    return X


class LiveScoringService:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        historical_data_path: str = DEFAULT_HISTORICAL_DATA_PATH,
        historical_df: Optional[pd.DataFrame] = None,
        state_store=None,
    ):
        """
        `historical_df`, if given, is used to warm-start sender state
        instead of reading `historical_data_path` from disk — needed
        when the caller wants to warm-start on only *part* of a
        dataset (e.g. a time-based train split), leaving the rest free
        to be streamed in as "new" transactions without double-
        counting them into a sender's history. See
        `src/streaming/realtime_processor.py` for exactly this use.

        `state_store` (Phase 9), if given, is passed through to
        `RealtimeFeatureComputer` — pass a `RedisStateStore`
        (`src/api/state_store.py`) to persist sender state externally
        instead of only in this process's memory. Defaults to
        in-memory, same as before Phase 9.
        """
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = artifact["feature_names"]
        self.rule_engine = RuleEngine()
        self.feature_computer = RealtimeFeatureComputer(state_store=state_store)

        if historical_df is not None:
            df = historical_df.copy()
        else:
            df = pd.read_csv(historical_data_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        self.global_median_amount = float(df["amount"].median())
        self.known_senders = int(df["sender_upi_id"].nunique())

        self.feature_computer.warm_start(df.to_dict("records"))

    def score(self, raw_transaction: dict) -> ScoreResult:
        enriched = enrich_transaction(raw_transaction, self.feature_computer)
        X = build_model_input(enriched, self.feature_names, self.global_median_amount)

        probability = float(self.model.predict_proba(X)[:, 1][0])
        rule_output = self.rule_engine.evaluate(enriched)
        risk_level = combine_risk_level(probability, rule_output)
        final_decision = decision_from_risk_level(risk_level)
        explanation = build_explanation(enriched, rule_output, probability)
        scored_at = datetime.now(timezone.utc).isoformat()

        # Record only *after* scoring, so this transaction becomes part
        # of the sender's history for whatever comes next — never for
        # itself, preserving the causal (no-future-leakage) guarantee
        # from Phase 3.
        self.feature_computer.record_transaction(enriched)

        return ScoreResult(
            transaction_id=raw_transaction["transaction_id"],
            fraud_probability=round(probability, 4),
            risk_level=risk_level,
            triggered_rules=rule_output.triggered_rule_ids,
            final_decision=final_decision,
            explanation=explanation,
            scored_at=scored_at,
        )

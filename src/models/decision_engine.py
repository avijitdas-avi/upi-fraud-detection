"""
Combined Decision Engine
===========================

Merges the rule engine's output (Phase 4, `src/rules/`) with the
primary ML model's fraud probability (Phase 5,
`train_gradient_boosting.py`) into the single structured output the
project specification defines (`docs/project_specification.md`,
Sections 5 and 6): a risk level, a final ALLOW/REVIEW/BLOCK decision,
and an explanation.

Combination policy (documented here since the spec left the exact
mechanics open — Section 6's note: "the exact combination logic will
be finalized when the rule engine and decision layer are
implemented"):

1. **Hard rules override everything.** If `BLOCKLIST` triggers, the
   transaction is forced to CRITICAL / BLOCK regardless of the ML
   score. A known-blocked party is a fact, not a probability — no
   model score should be able to talk it down.
2. **Otherwise, the ML probability sets the base risk level**, using
   the thresholds from Section 6 (LOW/MEDIUM/HIGH/CRITICAL).
3. **Multiple corroborating rules escalate the risk level by one
   tier** (e.g. MEDIUM -> HIGH). The threshold for "multiple" is 2
   triggered non-hard rules by default. A single triggered rule does
   *not* escalate on its own — Phase 4's evaluation showed individual
   rules like `ODD_HOUR` and `NEW_DEVICE_AND_LOCATION` have real false
   positive rates (24% and 15% precision respectively) on their own,
   so one such trigger alone isn't treated as strong enough evidence
   to override what the model already concluded from the same
   underlying features. Two or more independent rules agreeing is a
   stronger, more specific signal.
4. **Risk level never gets escalated downward by the absence of rule
   triggers.** Rules only add confidence, they don't subtract it — the
   ML model may correctly catch fraud patterns no rule was written
   for (that's the whole reason both layers exist together).

This module operates on already-engineered rows (from
`data/processed/behavioral_features.csv`, Phase 3's output) — it does
not compute behavioral features from a live incoming transaction. That
capability belongs to the real-time streaming phases (Kafka/Redis,
Phase 8-9), which this module is designed to slot into later without
its combination logic needing to change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import joblib
import pandas as pd

from src.models.feature_prep import prepare_features
from src.rules.engine import RuleEngine, RuleEngineOutput

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Section 6 of the spec
RISK_LEVEL_THRESHOLDS = [
    (0.00, 0.30, "LOW"),
    (0.30, 0.60, "MEDIUM"),
    (0.60, 0.85, "HIGH"),
    (0.85, 1.01, "CRITICAL"),  # 1.01 so probability == 1.0 is inclusive
]

DECISION_BY_RISK_LEVEL = {
    "LOW": "ALLOW",
    "MEDIUM": "ALLOW",
    "HIGH": "REVIEW",
    "CRITICAL": "BLOCK",
}

HARD_RULES = frozenset({"BLOCKLIST"})
ESCALATION_RULE_COUNT = 2  # number of non-hard triggered rules needed to escalate one tier

GB_MODEL_PATH = "models/gradient_boosting_model.joblib"


@dataclass
class TransactionScore:
    transaction_id: str
    fraud_probability: float
    risk_level: str
    triggered_rules: list
    final_decision: str
    explanation: str
    scored_at: str


def risk_level_from_probability(probability: float) -> str:
    for low, high, level in RISK_LEVEL_THRESHOLDS:
        if low <= probability < high:
            return level
    return "CRITICAL"  # safety net for probability == 1.0 edge case


def _escalate(level: str, steps: int = 1) -> str:
    idx = RISK_LEVELS.index(level)
    return RISK_LEVELS[min(idx + steps, len(RISK_LEVELS) - 1)]


def combine_risk_level(probability: float, rule_output: RuleEngineOutput) -> str:
    triggered = set(rule_output.triggered_rule_ids)

    if triggered & HARD_RULES:
        return "CRITICAL"

    base_level = risk_level_from_probability(probability)
    non_hard_triggered = triggered - HARD_RULES
    if len(non_hard_triggered) >= ESCALATION_RULE_COUNT:
        return _escalate(base_level, steps=1)

    return base_level


def decision_from_risk_level(risk_level: str) -> str:
    return DECISION_BY_RISK_LEVEL[risk_level]


# --- Explanation generation -------------------------------------------------
# No SHAP available in this project's environment (see
# docs/model_training_report.md, Section 0) — this builds a
# per-transaction explanation heuristically, from the same behavioral
# features the model and rules both use, rather than a true SHAP
# attribution. It picks the most unusual factors for *this specific*
# transaction, in plain language.

def _describe_top_factors(transaction: Mapping[str, Any], max_factors: int = 3) -> list:
    factors = []

    zscore = transaction.get("amount_zscore_vs_sender")
    if zscore is not None and not (isinstance(zscore, float) and math.isnan(zscore)):
        if zscore >= 2.0:
            factors.append((abs(zscore), f"amount is {zscore:.1f} standard deviations above the sender's usual amount"))

    ratio = transaction.get("amount_ratio_vs_sender_avg")
    if ratio is not None and not (isinstance(ratio, float) and math.isnan(ratio)) and ratio >= 2.0:
        factors.append((ratio, f"amount is {ratio:.1f}x the sender's typical amount"))

    velocity = transaction.get("sender_txn_count_last_1h")
    if velocity is not None and not (isinstance(velocity, float) and math.isnan(velocity)) and velocity >= 2:
        factors.append((velocity + 3, f"{int(velocity)} other transactions from this sender in the last hour"))

    if transaction.get("is_new_receiver_derived"):
        factors.append((2.5, "first transaction to this receiver"))

    if transaction.get("is_new_device_derived") and transaction.get("is_new_location_derived"):
        factors.append((3.5, "new device and new location at the same time"))
    elif transaction.get("is_new_device_derived"):
        factors.append((1.5, "unrecognized device"))
    elif transaction.get("is_new_location_derived"):
        factors.append((1.5, "unrecognized location"))

    hour_dev = transaction.get("hour_deviation_from_typical")
    if hour_dev is not None and not (isinstance(hour_dev, float) and math.isnan(hour_dev)) and hour_dev >= 6:
        factors.append((hour_dev / 2, "occurring at an hour unusual for this sender"))

    factors.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in factors[:max_factors]]


def build_explanation(transaction: Mapping[str, Any], rule_output: RuleEngineOutput, probability: float) -> str:
    top_factors = _describe_top_factors(transaction)
    rule_descriptions = [r for r in rule_output.triggered_rule_ids]

    if not top_factors and not rule_descriptions:
        return f"No significant risk factors identified (fraud probability {probability:.1%})."

    parts = []
    if top_factors:
        parts.append("Key factors: " + "; ".join(top_factors) + ".")
    if rule_descriptions:
        parts.append("Rules triggered: " + ", ".join(rule_descriptions) + ".")
    parts.append(f"Model fraud probability: {probability:.1%}.")

    return " ".join(parts)


# --- Decision engine ---------------------------------------------------------

class DecisionEngine:
    def __init__(self, model_path: str = GB_MODEL_PATH):
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = artifact["feature_names"]
        self.rule_engine = RuleEngine()

    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score every row of an already-feature-engineered DataFrame
        (i.e. output of Phase 3's behavioral_features.py)."""
        prepared = prepare_features(df)
        X = prepared.X.reindex(columns=self.feature_names, fill_value=0.0)
        probabilities = self.model.predict_proba(X)[:, 1]

        scored_at = datetime.now(timezone.utc).isoformat()
        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            probability = float(probabilities[i])
            rule_output = self.rule_engine.evaluate(row)
            risk_level = combine_risk_level(probability, rule_output)
            final_decision = decision_from_risk_level(risk_level)
            explanation = build_explanation(row, rule_output, probability)

            results.append(TransactionScore(
                transaction_id=row["transaction_id"],
                fraud_probability=round(probability, 4),
                risk_level=risk_level,
                triggered_rules=rule_output.triggered_rule_ids,
                final_decision=final_decision,
                explanation=explanation,
                scored_at=scored_at,
            ))

        output_df = pd.DataFrame([r.__dict__ for r in results])
        output_df["triggered_rules"] = output_df["triggered_rules"].apply(lambda ids: ",".join(ids))
        return output_df

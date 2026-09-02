"""
Feature Preparation for Model Training
=========================================

Turns `data/processed/behavioral_features.csv` (Phase 3 output) into a
clean numeric feature matrix ready for model training, shared by every
model in this phase so they're all trained and compared on identical
inputs.

Column decisions (see `docs/eda_report.md` for the reasoning):

- **Excluded entirely:** identifiers (`transaction_id`,
  `sender_upi_id`, etc.), raw free-text fields (`device_id`,
  `ip_address`, `location`, `sender_bank`, `receiver_bank` — high
  cardinality, not generalizable), the simulator's own
  `is_new_device` / `is_new_receiver` ground-truth labels (not
  something a real system would have — the *derived* versions are
  used instead), `transaction_status` (this is often the *outcome* of
  processing a transaction, not information available beforehand —
  including it risks leaking the answer), and `fraud_type` (only
  exists for evaluation, would leak the label).
- **Included:** `amount`, `hour_of_day`, `day_of_week`,
  `transaction_type` (one-hot encoded), and all 16 behavioral features
  from Phase 3.

Missing values (present only for a sender's first-ever transaction,
where no prior history exists yet) are imputed with neutral values
rather than dropped, so the model still sees these rows — a real
system can't skip scoring someone's first transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TARGET_COL = "label_is_fraud"
TIME_COL = "timestamp"

NUMERIC_FEATURES = [
    "amount",
    "hour_of_day",
    "day_of_week",
    "sender_prior_txn_count",
    "sender_avg_amount_prior",
    "sender_std_amount_prior",
    "amount_zscore_vs_sender",
    "amount_ratio_vs_sender_avg",
    "seconds_since_last_txn",
    "sender_txn_count_last_1h",
    "sender_txn_count_last_24h",
    "device_seen_count_prior",
    "location_seen_count_prior",
    "receiver_seen_count_prior",
    "sender_typical_hour_prior",
    "hour_deviation_from_typical",
]

BOOLEAN_FEATURES = [
    "is_new_device_derived",
    "is_new_location_derived",
    "is_new_receiver_derived",
]

CATEGORICAL_FEATURES = ["transaction_type"]

# Sentinel for "no prior transaction exists" — large enough to be
# clearly distinguishable from any real gap in the data (max real gap
# is under the ~90-day simulation window, i.e. well under 8,000,000 seconds).
NO_PRIOR_TXN_SENTINEL_SECONDS = 9_999_999.0


@dataclass
class PreparedData:
    X: pd.DataFrame
    y: pd.Series
    feature_names: list
    raw: pd.DataFrame  # original rows, same order, for reference (fraud_type, timestamp, etc.)


def _impute(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    global_median_amount = df["amount"].median()

    df["amount_zscore_vs_sender"] = df["amount_zscore_vs_sender"].fillna(0.0)
    df["amount_ratio_vs_sender_avg"] = df["amount_ratio_vs_sender_avg"].fillna(1.0)
    df["sender_avg_amount_prior"] = df["sender_avg_amount_prior"].fillna(global_median_amount)
    df["sender_std_amount_prior"] = df["sender_std_amount_prior"].fillna(0.0)
    df["seconds_since_last_txn"] = df["seconds_since_last_txn"].fillna(NO_PRIOR_TXN_SENTINEL_SECONDS)
    df["sender_txn_count_last_1h"] = df["sender_txn_count_last_1h"].fillna(0.0)
    df["sender_txn_count_last_24h"] = df["sender_txn_count_last_24h"].fillna(0.0)
    df["sender_typical_hour_prior"] = df["sender_typical_hour_prior"].fillna(df["hour_of_day"])
    df["hour_deviation_from_typical"] = df["hour_deviation_from_typical"].fillna(0.0)

    return df


def prepare_features(df: pd.DataFrame) -> PreparedData:
    df = df.copy()
    df = _impute(df)

    numeric_block = df[NUMERIC_FEATURES].astype(float)
    boolean_block = df[BOOLEAN_FEATURES].astype(float)  # True/False -> 1.0/0.0
    categorical_block = pd.get_dummies(df[CATEGORICAL_FEATURES], prefix=CATEGORICAL_FEATURES)

    X = pd.concat([numeric_block, boolean_block, categorical_block], axis=1)
    y = df[TARGET_COL].astype(int)

    return PreparedData(X=X, y=y, feature_names=list(X.columns), raw=df)


def time_based_split(df: pd.DataFrame, test_fraction: float = 0.2):
    """
    Split chronologically rather than randomly: the earliest
    (1 - test_fraction) of transactions by timestamp are train, the
    most recent test_fraction are test. This mirrors how the model
    will actually be used — trained on the past, evaluated on
    transactions it hasn't seen yet — rather than a random split,
    which would let the model "see the future" during training via
    transactions from the same time period as the test set.
    """
    df_sorted = df.sort_values(TIME_COL).reset_index(drop=True)
    split_idx = int(len(df_sorted) * (1 - test_fraction))
    train_df = df_sorted.iloc[:split_idx].reset_index(drop=True)
    test_df = df_sorted.iloc[split_idx:].reset_index(drop=True)
    return train_df, test_df

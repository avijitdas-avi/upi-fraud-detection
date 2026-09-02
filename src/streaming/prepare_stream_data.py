"""
Prepares the data for the real-time streaming demo.

The scoring service warm-starts sender history from historical data
(so senders aren't treated as brand-new on their first streamed
transaction). If the streamer then replayed that *same* data as "new"
transactions, each one would be double-counted into its sender's
history — inflating transaction counts, marking already-seen
receivers/devices as new-again incorrectly, etc.

The fix: reuse the exact time-based split from Phase 5/6
(`src/models/feature_prep.py`) — warm-start on the earliest 80% of
transactions (by timestamp), and stream only the most recent 20% as
"new" live transactions. This also means the streamed transactions are
the same held-out set the model was evaluated on in Phase 5/6, so
results from the demo are directly comparable to those reports.

Usage (run as a module from the project root):
    python -m src.streaming.prepare_stream_data
"""

from __future__ import annotations

import pandas as pd

from src.models.feature_prep import time_based_split

SOURCE_PATH = "data/raw/synthetic_transactions.csv"
WARM_START_OUTPUT_PATH = "data/processed/stream_warm_start.csv"
LIVE_STREAM_OUTPUT_PATH = "data/processed/live_stream_demo.csv"


def prepare():
    df = pd.read_csv(SOURCE_PATH)
    train_df, test_df = time_based_split(df)

    train_df.to_csv(WARM_START_OUTPUT_PATH, index=False)
    test_df.to_csv(LIVE_STREAM_OUTPUT_PATH, index=False)

    print(f"Warm-start (past) transactions: {len(train_df)} -> {WARM_START_OUTPUT_PATH}")
    print(f"Live-stream (new) transactions: {len(test_df)} -> {LIVE_STREAM_OUTPUT_PATH}")
    print(f"Live-stream fraud rate: {test_df['label_is_fraud'].mean():.2%}")


if __name__ == "__main__":
    prepare()

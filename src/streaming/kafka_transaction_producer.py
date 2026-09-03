"""
Kafka Transaction Producer
==============================

The natural evolution of the project owner's own `transaction_streamer.py`:
instead of yielding transactions directly to an in-process consumer,
this publishes each one to a message broker's "upi-transactions"
topic — decoupling the producer from whatever is consuming it, which
is the entire point of using a real message broker (multiple
consumers, consumers that aren't even running yet, replay, etc.
all become possible once this is a real queue instead of a Python
generator).

Works against *either* the tested in-memory fake broker or the real
(untested-here) Kafka broker — see `broker_interface.py` — without any
code change, only which broker object gets passed in.

Usage (run as a module from the project root):
    python -m src.streaming.kafka_transaction_producer
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

TRANSACTIONS_TOPIC = "upi-transactions"


def produce_transactions(broker, file_path: str, delay: float = 0.05, limit: int | None = None) -> int:
    df = pd.read_csv(file_path)
    print(f"Loaded {len(df)} transactions from {file_path}")

    count = 0
    for _, row in df.iterrows():
        transaction = row.to_dict()
        broker.send(TRANSACTIONS_TOPIC, transaction)
        count += 1
        if delay:
            time.sleep(delay)
        if limit and count >= limit:
            break

    print(f"Published {count} transactions to topic '{TRANSACTIONS_TOPIC}'")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish transactions to the Kafka 'upi-transactions' topic.")
    parser.add_argument("--file", type=str, default="data/processed/live_stream_demo.csv")
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--bootstrap-servers", type=str, default="localhost:9092")
    args = parser.parse_args()

    from src.streaming.kafka_broker import KafkaBroker  # imported here so this file can still be
                                                          # imported for its produce_transactions()
                                                          # function without requiring kafka-python
                                                          # to be installed (used by tests against
                                                          # the in-memory broker instead).
    broker = KafkaBroker(bootstrap_servers=args.bootstrap_servers)
    try:
        produce_transactions(broker, args.file, delay=args.delay, limit=args.limit)
    finally:
        broker.close()

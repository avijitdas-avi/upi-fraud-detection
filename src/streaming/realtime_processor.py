"""
Real-Time Processor
=======================

Consumes transactions from `TransactionStreamer` (the project owner's
own file) one at a time and scores each one with the Phase 7 scoring
service, printing a live decision for every transaction as it
"arrives" — the first end-to-end demonstration of the full pipeline
(rules + ML + behavioral features, Phase 3-7) actually running against
a simulated live feed.

This is explicitly a **stepping stone toward Phase 8**, not a
replacement for it: today, `TransactionStreamer` yields transactions
from an in-process Python generator. In Phase 8, that transport layer
gets swapped for a real Kafka producer/consumer — but the scoring
logic this file exercises (`LiveScoringService.score()`) will be
unchanged, since it already doesn't know or care where a transaction
came from.

Run `python -m src.streaming.prepare_stream_data` once first (see that
file's docstring for why) — then:
    python -m src.streaming.realtime_processor
"""

from __future__ import annotations

import argparse
import sys

from src.api.scoring import LiveScoringService
from src.streaming.transaction_streamer import TransactionStreamer

WARM_START_PATH = "data/processed/stream_warm_start.csv"
LIVE_STREAM_PATH = "data/processed/live_stream_demo.csv"


def run(delay: float = 0.05, limit: int | None = None):
    # Force UTF-8 stdout — on some Windows terminals/configurations,
    # the default console encoding can't display certain characters
    # (previously this file used "₹" and an em dash, which could
    # silently fail to print on those setups). This makes output
    # encoding-safe regardless of the terminal's default codepage.
    sys.stdout.reconfigure(encoding="utf-8")

    print("Warming up scoring service from historical data...")
    import pandas as pd
    warm_start_df = pd.read_csv(WARM_START_PATH)
    service = LiveScoringService(historical_df=warm_start_df)
    print(f"Ready - {service.known_senders} known senders loaded.\n")

    streamer = TransactionStreamer(file_path=LIVE_STREAM_PATH, delay=delay)

    tally = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
    true_positives = 0   # flagged (REVIEW/BLOCK) and actually fraud
    false_positives = 0  # flagged and NOT actually fraud
    false_negatives = 0  # ALLOWed but actually fraud
    total_fraud = 0
    processed = 0

    try:
        for transaction in streamer.stream_transactions():
            actual_is_fraud = bool(transaction.get("label_is_fraud", False))
            # These two columns exist only because we're streaming
            # from labeled demo data — a real transaction wouldn't
            # carry its own answer key. Strip them before scoring so
            # the service only ever sees what a real transaction would
            # actually contain.
            transaction.pop("label_is_fraud", None)
            transaction.pop("fraud_type", None)

            result = service.score(transaction)
            tally[result.final_decision] += 1
            processed += 1

            flagged = result.final_decision in ("REVIEW", "BLOCK")
            if actual_is_fraud:
                total_fraud += 1
                if flagged:
                    true_positives += 1
                else:
                    false_negatives += 1
            elif flagged:
                false_positives += 1

            marker = "FRAUD" if actual_is_fraud else "     "
            print(f"[{marker}] {transaction['transaction_id'][:8]}  "
                  f"Rs.{transaction['amount']:>10,.2f}  "
                  f"prob={result.fraud_probability:>6.1%}  "
                  f"{result.risk_level:<8}  {result.final_decision:<6}  "
                  f"rules={result.triggered_rules}")

            if limit and processed >= limit:
                break

    except KeyboardInterrupt:
        print("\nStopped by user.")

    print("\n" + "=" * 70)
    print(f"Processed: {processed} transactions ({total_fraud} actually fraud)")
    print(f"Decisions: {tally}")
    print(f"True positives:  {true_positives}")
    print(f"False positives: {false_positives}")
    print(f"False negatives: {false_negatives}")
    if (true_positives + false_positives) > 0:
        precision = true_positives / (true_positives + false_positives)
        print(f"Precision: {precision:.1%}")
    if total_fraud > 0:
        recall = true_positives / total_fraud
        print(f"Recall: {recall:.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the real-time transaction stream demo.")
    parser.add_argument("--delay", type=float, default=0.05, help="Seconds between transactions (default 0.05).")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N transactions (default: full stream).")
    args = parser.parse_args()
    run(delay=args.delay, limit=args.limit)

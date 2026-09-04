"""
Postgres Persistence — Local Verification Demo
====================================================

Run this yourself once Postgres is available (`docker compose up -d`,
`pip install sqlalchemy psycopg2-binary`) to confirm the real
persistence layer actually works — this could not be executed in the
development sandbox this project was built in (see
docs/postgres_report.md, Section 0).

Mirrors `src/streaming/verify_redis_state.py`'s approach: scores a
handful of transactions using `PostgresDecisionRepository`, then opens
a **second, independent** connection to the same database and confirms
it can read back what the first connection wrote — proving the data
actually persisted in Postgres rather than only existing in the first
process's memory.

Usage:
    python -m src.streaming.verify_postgres_persistence
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.api.scoring import LiveScoringService

WARM_START_PATH = "data/processed/stream_warm_start.csv"

TEST_TRANSACTIONS = [
    {
        "transaction_id": "postgres_verify_1",
        "timestamp": datetime(2026, 9, 6, 3, 0, 0, tzinfo=timezone.utc),
        "sender_upi_id": "postgres_test_sender@upi",
        "receiver_upi_id": "postgres_test_receiver@upi",
        "amount": 25000.0,
        "transaction_type": "P2P",
        "device_id": "dev_postgres_test",
        "location": "Patna",
    },
    {
        "transaction_id": "postgres_verify_2",
        "timestamp": datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc),
        "sender_upi_id": "postgres_test_sender_2@upi",
        "receiver_upi_id": "postgres_test_receiver@upi",
        "amount": 150.0,
        "transaction_type": "P2M",
        "device_id": "dev_postgres_test_2",
        "location": "Chennai",
    },
]


def run():
    from src.db.postgres_repository import Decision, PostgresDecisionRepository

    warm_start_df = pd.read_csv(WARM_START_PATH)

    print("--- Writing: scoring test transactions and saving to Postgres ---")
    service = LiveScoringService(historical_df=warm_start_df)
    repo_write = PostgresDecisionRepository()

    written_ids = []
    for txn in TEST_TRANSACTIONS:
        result = service.score(dict(txn))
        repo_write.save(Decision(
            transaction_id=result.transaction_id,
            sender_upi_id=txn["sender_upi_id"],
            receiver_upi_id=txn["receiver_upi_id"],
            amount=txn["amount"],
            transaction_type=txn["transaction_type"],
            fraud_probability=result.fraud_probability,
            risk_level=result.risk_level,
            triggered_rules=result.triggered_rules,
            final_decision=result.final_decision,
            explanation=result.explanation,
            scored_at=result.scored_at,
        ))
        written_ids.append(result.transaction_id)
        print(f"  Saved {result.transaction_id}: prob={result.fraud_probability:.4f} "
              f"risk={result.risk_level} decision={result.final_decision}")

    print("\n--- Reading: NEW independent Postgres connection ---")
    print("(This proves the data persisted in Postgres, not just in the writer's memory.)")
    repo_read = PostgresDecisionRepository()

    all_found = True
    for transaction_id in written_ids:
        found = repo_read.get_by_id(transaction_id)
        status = "FOUND" if found else "MISSING"
        print(f"  {transaction_id}: {status}")
        all_found = all_found and (found is not None)

    print("\n--- Aggregate queries (also via the second connection) ---")
    print(f"  Total decisions in table: {len(repo_read.get_recent(limit=10000))}")
    print(f"  By final_decision: {repo_read.count_by_decision()}")
    print(f"  By risk_level: {repo_read.count_by_risk_level()}")

    print("\n" + ("ALL RECORDS FOUND — Postgres persistence verified." if all_found else
                   "SOME RECORDS MISSING — something is wrong, worth investigating."))


if __name__ == "__main__":
    run()

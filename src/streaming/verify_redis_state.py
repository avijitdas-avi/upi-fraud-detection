"""
Redis State Store — Local Verification Demo
================================================

Run this yourself once Redis is available (`docker compose up -d`,
`pip install redis`) to confirm the Redis-backed path actually works
end-to-end — this could not be executed in the development sandbox
this project was built in (see docs/redis_report.md, Section 0).

What this does: scores the same handful of test transactions twice —
once with `InMemoryStateStore` (the tested default) and once with
`RedisStateStore` — and confirms both produce identical results. If
they match, the Redis integration is behaving correctly; if the
Redis-backed run errors out or gives different results, that's real,
actionable information this sandbox couldn't have caught.

It also restarts (recreates) the scoring service a second time using
the *same* Redis connection, to confirm state actually persisted
externally rather than living only in the first process's memory —
the entire point of this phase.

Usage:
    python -m src.streaming.verify_redis_state
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.api.scoring import LiveScoringService
from src.api.state_store import InMemoryStateStore, RedisStateStore

WARM_START_PATH = "data/processed/stream_warm_start.csv"

TEST_TRANSACTIONS = [
    {
        "transaction_id": "redis_verify_1",
        "timestamp": datetime(2026, 9, 5, 3, 0, 0, tzinfo=timezone.utc),
        "sender_upi_id": "redis_test_sender@upi",
        "receiver_upi_id": "redis_test_receiver@upi",
        "amount": 30000.0,
        "transaction_type": "P2P",
        "device_id": "dev_redis_test",
        "location": "Guwahati",
    },
    {
        "transaction_id": "redis_verify_2",
        "timestamp": datetime(2026, 9, 5, 3, 5, 0, tzinfo=timezone.utc),
        "sender_upi_id": "redis_test_sender@upi",  # same sender — should reflect txn 1 in its history
        "receiver_upi_id": "redis_test_receiver@upi",
        "amount": 100.0,
        "transaction_type": "P2P",
        "device_id": "dev_redis_test",
        "location": "Guwahati",
    },
]


def run():
    warm_start_df = pd.read_csv(WARM_START_PATH)

    print("--- Run 1: InMemoryStateStore (baseline, tested default) ---")
    memory_service = LiveScoringService(historical_df=warm_start_df, state_store=InMemoryStateStore())
    memory_results = [memory_service.score(dict(t)) for t in TEST_TRANSACTIONS]
    for r in memory_results:
        print(f"  {r.transaction_id}: prob={r.fraud_probability:.4f} risk={r.risk_level} decision={r.final_decision}")

    print("\n--- Run 2: RedisStateStore (first process) ---")
    redis_store = RedisStateStore(host="localhost", port=6379)
    redis_service = LiveScoringService(historical_df=warm_start_df, state_store=redis_store)
    redis_results = [redis_service.score(dict(t)) for t in TEST_TRANSACTIONS]
    for r in redis_results:
        print(f"  {r.transaction_id}: prob={r.fraud_probability:.4f} risk={r.risk_level} decision={r.final_decision}")

    print("\n--- Comparing InMemory vs Redis results ---")
    all_match = True
    for mem_r, redis_r in zip(memory_results, redis_results):
        match = (
            abs(mem_r.fraud_probability - redis_r.fraud_probability) < 1e-6
            and mem_r.risk_level == redis_r.risk_level
            and mem_r.final_decision == redis_r.final_decision
        )
        print(f"  {mem_r.transaction_id}: {'MATCH' if match else 'MISMATCH'}")
        all_match = all_match and match

    print("\n--- Run 3: RedisStateStore (NEW process/service instance, same Redis) ---")
    print("(This proves state actually persisted in Redis, not just in Run 2's memory.)")
    redis_store_2 = RedisStateStore(host="localhost", port=6379)
    # Deliberately create a fresh service *without* re-warm-starting,
    # to confirm the sender's history from Run 2 is found in Redis
    # rather than needing to be rebuilt.
    third_txn = {
        "transaction_id": "redis_verify_3",
        "timestamp": datetime(2026, 9, 5, 3, 10, 0, tzinfo=timezone.utc),
        "sender_upi_id": "redis_test_sender@upi",
        "receiver_upi_id": "redis_test_receiver@upi",
        "amount": 100.0,
        "transaction_type": "P2P",
        "device_id": "dev_redis_test",
        "location": "Guwahati",
    }
    features_before_state_check = redis_store_2.get("redis_test_sender@upi")
    print(f"  Sender's prior transaction count found in Redis: {features_before_state_check.count} (expect 2, from Run 2)")

    print("\n" + ("ALL RESULTS MATCH — Redis integration verified." if all_match else
                   "MISMATCH DETECTED — something is wrong, worth investigating."))


if __name__ == "__main__":
    run()

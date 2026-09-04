"""
Kafka Consumer / Scoring App
=================================

The natural evolution of `realtime_processor.py` from the earlier
non-Kafka streaming demo: instead of iterating a Python generator
directly, this polls the "upi-transactions" topic from a message
broker, scores each transaction with the Phase 7 `LiveScoringService`,
and publishes the result to a "upi-fraud-decisions" output topic —
so downstream systems (PostgreSQL persistence in Phase 10, the
dashboard in Phase 11) can consume *decisions* from Kafka too, instead
of needing to know anything about how scoring happens.

Works against either the tested in-memory fake broker
(`tests/test_kafka_consumer_app.py` does exactly this) or the real
(untested-here) Kafka broker — the scoring/business logic in
`process_stream()` below is identical either way.

Usage (run as a module from the project root, against real Kafka):
    python -m src.streaming.kafka_consumer_app
"""

from __future__ import annotations

import argparse

from src.api.scoring import LiveScoringService
from src.db.repository import Decision, DecisionRepository, InMemoryDecisionRepository

TRANSACTIONS_TOPIC = "upi-transactions"
DECISIONS_TOPIC = "upi-fraud-decisions"


def process_stream(broker, service: LiveScoringService, repository: DecisionRepository | None = None, limit: int | None = None) -> list:
    """Consume transactions from the broker, score each one, publish
    the decision to the output topic, optionally persist it (Phase 10),
    and return the list of results (useful for tests and for the
    summary printout)."""
    results = []
    processed = 0

    for transaction in broker.poll(TRANSACTIONS_TOPIC):
        # These two fields only exist in our labeled demo data — a
        # real transaction wouldn't carry its own answer key. Keep
        # them out of what gets scored, same as the non-Kafka demo.
        transaction.pop("label_is_fraud", None)
        transaction.pop("fraud_type", None)

        result = service.score(transaction)
        broker.send(DECISIONS_TOPIC, {
            "transaction_id": result.transaction_id,
            "fraud_probability": result.fraud_probability,
            "risk_level": result.risk_level,
            "triggered_rules": result.triggered_rules,
            "final_decision": result.final_decision,
            "explanation": result.explanation,
            "scored_at": result.scored_at,
        })

        if repository is not None:
            repository.save(Decision(
                transaction_id=result.transaction_id,
                sender_upi_id=transaction["sender_upi_id"],
                receiver_upi_id=transaction["receiver_upi_id"],
                amount=float(transaction["amount"]),
                transaction_type=transaction["transaction_type"],
                fraud_probability=result.fraud_probability,
                risk_level=result.risk_level,
                triggered_rules=result.triggered_rules,
                final_decision=result.final_decision,
                explanation=result.explanation,
                scored_at=result.scored_at,
            ))

        results.append(result)
        processed += 1

        if limit and processed >= limit:
            break

    return results


def run(
    bootstrap_servers: str = "localhost:9092",
    warm_start_path: str = "data/processed/stream_warm_start.csv",
    limit: int | None = None,
    repository: DecisionRepository | None = None,
):
    import pandas as pd
    from src.streaming.kafka_broker import KafkaBroker  # see kafka_transaction_producer.py for why this
                                                          # import lives inside the function

    print("Warming up scoring service from historical data...")
    warm_start_df = pd.read_csv(warm_start_path)
    service = LiveScoringService(historical_df=warm_start_df)
    print(f"Ready - {service.known_senders} known senders loaded.\n")

    if repository is None:
        repository = InMemoryDecisionRepository()
        print("No repository given — using in-memory (not persisted across restarts). "
              "Pass a PostgresDecisionRepository for real persistence (Phase 10).")

    broker = KafkaBroker(bootstrap_servers=bootstrap_servers)
    print(f"Consuming from '{TRANSACTIONS_TOPIC}', publishing decisions to '{DECISIONS_TOPIC}'...")
    try:
        results = process_stream(broker, service, repository=repository, limit=limit)
    finally:
        broker.close()

    print(f"\nProcessed {len(results)} transactions.")
    tally = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
    for r in results:
        tally[r.final_decision] += 1
    print(f"Decisions: {tally}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consume and score transactions from Kafka.")
    parser.add_argument("--bootstrap-servers", type=str, default="localhost:9092")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--postgres", action="store_true", help="Persist decisions to Postgres instead of in-memory only.")
    args = parser.parse_args()

    repo = None
    if args.postgres:
        from src.db.postgres_repository import PostgresDecisionRepository
        repo = PostgresDecisionRepository()

    run(bootstrap_servers=args.bootstrap_servers, limit=args.limit, repository=repo)

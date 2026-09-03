"""
Tests for the producer/consumer application logic
(`kafka_transaction_producer.py`, `kafka_consumer_app.py`), run
against `InMemoryBroker` instead of real Kafka — since real Kafka
can't run in this sandbox (see `docs/kafka_report.md`, Section 0).

These tests exercise the *actual* application logic (scoring,
publishing decisions, correct topic usage) — the only thing untested
is the Kafka transport itself, which is a thin, standard wrapper
around `kafka-python`'s documented API.
"""

from src.api.scoring import LiveScoringService
from src.streaming.in_memory_broker import InMemoryBroker
from src.streaming.kafka_consumer_app import DECISIONS_TOPIC, TRANSACTIONS_TOPIC, process_stream
from src.streaming.kafka_transaction_producer import produce_transactions

_service = None


def get_service() -> LiveScoringService:
    global _service
    if _service is None:
        import pandas as pd
        warm_start_df = pd.read_csv("data/processed/stream_warm_start.csv")
        _service = LiveScoringService(historical_df=warm_start_df)
    return _service


def test_producer_publishes_to_transactions_topic():
    broker = InMemoryBroker()
    count = produce_transactions(broker, "data/processed/live_stream_demo.csv", delay=0, limit=20)

    assert count == 20
    assert broker.topic_size(TRANSACTIONS_TOPIC) == 20


def test_consumer_scores_and_publishes_decisions():
    broker = InMemoryBroker()
    produce_transactions(broker, "data/processed/live_stream_demo.csv", delay=0, limit=20)

    service = get_service()
    results = process_stream(broker, service, limit=20)

    assert len(results) == 20
    # every produced transaction should have a corresponding decision published
    assert broker.topic_size(DECISIONS_TOPIC) == 20


def test_producer_and_consumer_agree_on_transaction_count_via_real_topics():
    """End-to-end: produce N transactions, consume all of them, confirm
    none were dropped or duplicated — the basic correctness property
    any real message broker also needs to satisfy."""
    broker = InMemoryBroker()
    produced_count = produce_transactions(broker, "data/processed/live_stream_demo.csv", delay=0, limit=100)

    service = get_service()
    results = process_stream(broker, service)  # no limit — drain the whole topic

    assert len(results) == produced_count


def test_decisions_match_expected_schema():
    broker = InMemoryBroker()
    produce_transactions(broker, "data/processed/live_stream_demo.csv", delay=0, limit=5)

    service = get_service()
    process_stream(broker, service, limit=5)

    decisions = list(broker.poll(DECISIONS_TOPIC))
    assert len(decisions) == 5
    for decision in decisions:
        assert "transaction_id" in decision
        assert "fraud_probability" in decision
        assert "risk_level" in decision
        assert "final_decision" in decision
        assert decision["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert decision["final_decision"] in ("ALLOW", "REVIEW", "BLOCK")

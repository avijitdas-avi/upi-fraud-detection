"""
Tests for `InMemoryDecisionRepository` (`src/db/repository.py`) and
its integration into `kafka_consumer_app.process_stream()`. Real
Postgres can't be tested here (see docs/postgres_report.md, Section 0)
— these tests exercise the actual persistence *logic* against the
interface, which is what `PostgresDecisionRepository` also implements.
"""

from src.api.scoring import LiveScoringService
from src.db.repository import Decision, InMemoryDecisionRepository
from src.streaming.in_memory_broker import InMemoryBroker
from src.streaming.kafka_consumer_app import process_stream
from src.streaming.kafka_transaction_producer import produce_transactions

_service = None


def get_service() -> LiveScoringService:
    global _service
    if _service is None:
        import pandas as pd
        warm_start_df = pd.read_csv("data/processed/stream_warm_start.csv")
        _service = LiveScoringService(historical_df=warm_start_df)
    return _service


# --- InMemoryDecisionRepository, in isolation ---

def make_decision(transaction_id: str, final_decision: str, risk_level: str) -> Decision:
    return Decision(
        transaction_id=transaction_id,
        sender_upi_id="sender@upi",
        receiver_upi_id="receiver@upi",
        amount=100.0,
        transaction_type="P2P",
        fraud_probability=0.5,
        risk_level=risk_level,
        triggered_rules=[],
        final_decision=final_decision,
        explanation="test",
        scored_at="2026-01-01T00:00:00",
    )


def test_save_and_get_by_id():
    repo = InMemoryDecisionRepository()
    decision = make_decision("tx1", "BLOCK", "CRITICAL")
    repo.save(decision)

    retrieved = repo.get_by_id("tx1")
    assert retrieved is not None
    assert retrieved.transaction_id == "tx1"
    assert retrieved.final_decision == "BLOCK"


def test_get_by_id_returns_none_for_missing():
    repo = InMemoryDecisionRepository()
    assert repo.get_by_id("nonexistent") is None


def test_get_recent_returns_most_recent_first():
    repo = InMemoryDecisionRepository()
    for i in range(5):
        repo.save(make_decision(f"tx{i}", "ALLOW", "LOW"))

    recent = repo.get_recent(limit=3)
    assert len(recent) == 3
    assert [d.transaction_id for d in recent] == ["tx4", "tx3", "tx2"]


def test_count_by_decision():
    repo = InMemoryDecisionRepository()
    repo.save(make_decision("tx1", "ALLOW", "LOW"))
    repo.save(make_decision("tx2", "ALLOW", "LOW"))
    repo.save(make_decision("tx3", "BLOCK", "CRITICAL"))

    counts = repo.count_by_decision()
    assert counts["ALLOW"] == 2
    assert counts["BLOCK"] == 1
    assert counts["REVIEW"] == 0


def test_count_by_risk_level():
    repo = InMemoryDecisionRepository()
    repo.save(make_decision("tx1", "ALLOW", "LOW"))
    repo.save(make_decision("tx2", "BLOCK", "CRITICAL"))
    repo.save(make_decision("tx3", "BLOCK", "CRITICAL"))

    counts = repo.count_by_risk_level()
    assert counts["LOW"] == 1
    assert counts["CRITICAL"] == 2


def test_len():
    repo = InMemoryDecisionRepository()
    repo.save(make_decision("tx1", "ALLOW", "LOW"))
    repo.save(make_decision("tx2", "ALLOW", "LOW"))
    assert len(repo) == 2


# --- Integration with the consumer app ---

def test_process_stream_persists_every_scored_transaction():
    broker = InMemoryBroker()
    produce_transactions(broker, "data/processed/live_stream_demo.csv", delay=0, limit=30)

    service = get_service()
    repository = InMemoryDecisionRepository()
    results = process_stream(broker, service, repository=repository, limit=30)

    assert len(results) == 30
    assert len(repository) == 30
    # spot-check: the repository's record for a given transaction
    # matches what was actually scored for it
    first_result = results[0]
    stored = repository.get_by_id(first_result.transaction_id)
    assert stored is not None
    assert stored.fraud_probability == first_result.fraud_probability
    assert stored.final_decision == first_result.final_decision


def test_process_stream_without_repository_still_works():
    """repository=None should behave exactly like before Phase 10 —
    scoring and publishing to the decisions topic still happen, just
    without persistence."""
    broker = InMemoryBroker()
    produce_transactions(broker, "data/processed/live_stream_demo.csv", delay=0, limit=10)

    service = get_service()
    results = process_stream(broker, service, repository=None, limit=10)

    assert len(results) == 10

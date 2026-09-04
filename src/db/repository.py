"""
Decision Repository
=======================

Where scored fraud decisions get permanently stored, so they survive
past the moment they're scored — enabling the dashboard (Phase 11) to
show historical data, and giving any downstream system a durable
record of every decision this project's pipeline has ever made.

Same pattern as the message broker (Phase 8) and state store
(Phase 9): an interface (`DecisionRepository`) with two
implementations —

- **`InMemoryDecisionRepository`** — a plain Python list, genuinely
  tested here (`tests/test_decision_repository.py`)
- **`PostgresDecisionRepository`** (`postgres_repository.py`) — the
  real, persistent implementation using SQLAlchemy. *** NOT EXECUTED
  IN THIS DEVELOPMENT SANDBOX — no internet access to install
  `sqlalchemy`/`psycopg2`, no local Postgres server (see
  `docs/postgres_report.md`, Section 0). ***

Whatever calls into this (currently `src/streaming/kafka_consumer_app.py`,
optionally) only depends on this interface — swapping the in-memory
version for real Postgres is a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class Decision:
    """One persisted fraud decision — matches the scoring output
    schema (docs/project_specification.md, Section 5) plus a few raw
    transaction fields useful for later querying/display without a
    join."""
    transaction_id: str
    sender_upi_id: str
    receiver_upi_id: str
    amount: float
    transaction_type: str
    fraud_probability: float
    risk_level: str
    triggered_rules: list
    final_decision: str
    explanation: str
    scored_at: str


class DecisionRepository(Protocol):
    def save(self, decision: Decision) -> None:
        ...

    def get_by_id(self, transaction_id: str) -> Optional[Decision]:
        ...

    def get_recent(self, limit: int = 50) -> list:
        """Most recently scored decisions first."""
        ...

    def count_by_decision(self) -> dict:
        """e.g. {'ALLOW': 9583, 'REVIEW': 28, 'BLOCK': 389}"""
        ...

    def count_by_risk_level(self) -> dict:
        ...


class InMemoryDecisionRepository:
    """Plain Python list, in this process's memory only — lost on
    restart, not shared across processes. Default implementation so
    existing code keeps working without requiring Postgres."""

    def __init__(self):
        self._decisions: list = []
        self._by_id: dict = {}

    def save(self, decision: Decision) -> None:
        self._decisions.append(decision)
        self._by_id[decision.transaction_id] = decision

    def get_by_id(self, transaction_id: str) -> Optional[Decision]:
        return self._by_id.get(transaction_id)

    def get_recent(self, limit: int = 50) -> list:
        return list(reversed(self._decisions[-limit:]))

    def count_by_decision(self) -> dict:
        counts = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
        for d in self._decisions:
            counts[d.final_decision] = counts.get(d.final_decision, 0) + 1
        return counts

    def count_by_risk_level(self) -> dict:
        counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for d in self._decisions:
            counts[d.risk_level] = counts.get(d.risk_level, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._decisions)

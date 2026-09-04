"""
Postgres Decision Repository (Real Implementation)
=======================================================

*** NOT EXECUTED IN THIS DEVELOPMENT SANDBOX — see docs/postgres_report.md,
Section 0. No internet access to install `sqlalchemy`/`psycopg2`, no
local Postgres server. Implements the same interface as
`InMemoryDecisionRepository` (`repository.py`), which *was* tested —
whatever calls into this doesn't need to change at all when you swap
this in for the fake. ***

Requires a running Postgres server (see `docker-compose.yml` at the
project root) and `pip install sqlalchemy psycopg2-binary`.

Usage once both are available:
    repo = PostgresDecisionRepository(
        connection_string="postgresql://upi_user:upi_pass@localhost:5432/upi_fraud_detection"
    )
    repo.save(decision)
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Float, String, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker

from src.db.repository import Decision

Base = declarative_base()


class DecisionRow(Base):
    __tablename__ = "fraud_decisions"

    transaction_id = Column(String, primary_key=True)
    sender_upi_id = Column(String, nullable=False, index=True)
    receiver_upi_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)
    fraud_probability = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False, index=True)
    triggered_rules = Column(JSON, nullable=False)
    final_decision = Column(String, nullable=False, index=True)
    explanation = Column(String, nullable=False)
    scored_at = Column(String, nullable=False)
    persisted_at = Column(DateTime, server_default=func.now())

    def to_decision(self) -> Decision:
        return Decision(
            transaction_id=self.transaction_id,
            sender_upi_id=self.sender_upi_id,
            receiver_upi_id=self.receiver_upi_id,
            amount=self.amount,
            transaction_type=self.transaction_type,
            fraud_probability=self.fraud_probability,
            risk_level=self.risk_level,
            triggered_rules=self.triggered_rules,
            final_decision=self.final_decision,
            explanation=self.explanation,
            scored_at=self.scored_at,
        )


DEFAULT_CONNECTION_STRING = "postgresql://upi_user:upi_pass@localhost:5432/upi_fraud_detection"


class PostgresDecisionRepository:
    def __init__(self, connection_string: str = DEFAULT_CONNECTION_STRING):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)  # creates the table if it doesn't exist yet
        self.Session = sessionmaker(bind=self.engine)

    def save(self, decision: Decision) -> None:
        with self.Session() as session:
            row = DecisionRow(
                transaction_id=decision.transaction_id,
                sender_upi_id=decision.sender_upi_id,
                receiver_upi_id=decision.receiver_upi_id,
                amount=decision.amount,
                transaction_type=decision.transaction_type,
                fraud_probability=decision.fraud_probability,
                risk_level=decision.risk_level,
                triggered_rules=decision.triggered_rules,
                final_decision=decision.final_decision,
                explanation=decision.explanation,
                scored_at=decision.scored_at,
            )
            session.merge(row)  # insert or update — safe to re-run on the same transaction_id
            session.commit()

    def get_by_id(self, transaction_id: str) -> Optional[Decision]:
        with self.Session() as session:
            row = session.get(DecisionRow, transaction_id)
            return row.to_decision() if row else None

    def get_recent(self, limit: int = 50) -> list:
        with self.Session() as session:
            rows = (
                session.query(DecisionRow)
                .order_by(DecisionRow.persisted_at.desc())
                .limit(limit)
                .all()
            )
            return [r.to_decision() for r in rows]

    def count_by_decision(self) -> dict:
        with self.Session() as session:
            results = (
                session.query(DecisionRow.final_decision, func.count(DecisionRow.transaction_id))
                .group_by(DecisionRow.final_decision)
                .all()
            )
            counts = {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0}
            counts.update({decision: count for decision, count in results})
            return counts

    def count_by_risk_level(self) -> dict:
        with self.Session() as session:
            results = (
                session.query(DecisionRow.risk_level, func.count(DecisionRow.transaction_id))
                .group_by(DecisionRow.risk_level)
                .all()
            )
            counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
            counts.update({level: count for level, count in results})
            return counts

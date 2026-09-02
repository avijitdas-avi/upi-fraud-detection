"""
Pydantic schemas for the FastAPI service.

*** Not executed in this development sandbox — see docs/api_report.md,
Section 0. `pydantic` and `fastapi` are not installed here (no
internet access), so this file's syntax could not be verified by
actually importing it in this environment. It's written against the
standard, well-established Pydantic v2 API. Run
`pip install -r requirements.txt` locally (Phase 1 setup) and start
the server per Section 3 of the report to verify. ***

Field names and the response schema match
`docs/project_specification.md` Sections 4 (transaction fields) and 5
(expected model output) as closely as an HTTP request body reasonably
can — a few raw-schema fields (bank names, IFSC-linked info,
`transaction_status`) are intentionally omitted from the *input*
because they are either not needed to compute fraud features or
represent the outcome of processing the transaction, not information
available beforehand.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., description="Unique identifier for the transaction")
    timestamp: Optional[datetime] = Field(
        None, description="When the transaction occurred. Defaults to now if omitted."
    )
    sender_upi_id: str
    receiver_upi_id: str
    amount: float = Field(..., gt=0, description="Transaction amount in INR")
    transaction_type: str = Field(..., description="One of: P2P, P2M, COLLECT")
    device_id: str
    location: str

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": "tx_demo_001",
                "timestamp": "2026-08-30T14:22:00",
                "sender_upi_id": "user123@okhdfcbank",
                "receiver_upi_id": "merchant45@ybl",
                "amount": 2500.0,
                "transaction_type": "P2M",
                "device_id": "dev_abc123",
                "location": "Kolkata",
            }
        }


class TransactionScoreResponse(BaseModel):
    transaction_id: str
    fraud_probability: float
    risk_level: str
    triggered_rules: list
    final_decision: str
    explanation: str
    scored_at: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    known_senders: int

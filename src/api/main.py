"""
FastAPI Application
=======================

*** Not executed in this development sandbox — see docs/api_report.md,
Section 0. `fastapi`/`uvicorn` are not installed here (no internet
access). This file is deliberately thin — nearly all the real logic
lives in `src/api/scoring.py`, which *was* tested directly in this
sandbox (see `tests/test_scoring_service.py`). This file just wires
that tested logic to HTTP routes using standard, well-established
FastAPI patterns. ***

Run locally (once `pip install -r requirements.txt` succeeds):
    uvicorn src.api.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive API docs
(FastAPI generates this automatically).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from src.api.schemas import HealthResponse, TransactionRequest, TransactionScoreResponse
from src.api.scoring import LiveScoringService

app = FastAPI(
    title="UPI Fraud Detection API",
    description="Real-time transaction fraud scoring — combines a trained ML model with rule-based checks.",
    version="0.1.0",
)

_service: LiveScoringService | None = None


@app.on_event("startup")
def startup():
    global _service
    _service = LiveScoringService()


@app.get("/health", response_model=HealthResponse)
def health():
    if _service is None:
        return HealthResponse(status="starting", model_loaded=False, known_senders=0)
    return HealthResponse(status="ok", model_loaded=True, known_senders=_service.known_senders)


@app.post("/score", response_model=TransactionScoreResponse)
def score_transaction(transaction: TransactionRequest):
    if _service is None:
        raise HTTPException(status_code=503, detail="Service is still starting up.")

    result = _service.score(transaction.model_dump())
    return TransactionScoreResponse(
        transaction_id=result.transaction_id,
        fraud_probability=result.fraud_probability,
        risk_level=result.risk_level,
        triggered_rules=result.triggered_rules,
        final_decision=result.final_decision,
        explanation=result.explanation,
        scored_at=result.scored_at,
    )

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

Phase 11 additions: CORS (so the Next.js frontend, hosted on a
different origin — e.g. Vercel — can actually call this API from a
browser), and two read endpoints the dashboard needs
(`/api/decisions/recent`, `/api/decisions/stats`), backed by the
Postgres repository from Phase 10. `/score` now also persists its
result, so a transaction scored manually from the dashboard's "Score a
transaction" form immediately shows up in the live feed.

Run locally (once `pip install -r requirements.txt` succeeds):
    uvicorn src.api.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive API docs
(FastAPI generates this automatically).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    DecisionResponse,
    DecisionStatsResponse,
    HealthResponse,
    TransactionRequest,
    TransactionScoreResponse,
)
from src.api.scoring import LiveScoringService
from src.db.repository import Decision, DecisionRepository

app = FastAPI(
    title="UPI Fraud Detection API",
    description="Real-time transaction fraud scoring — combines a trained ML model with rule-based checks.",
    version="0.1.0",
)

# Allows the Next.js dashboard (a different origin once deployed to
# Vercel) to call this API from a browser. Restrict allow_origins to
# your actual frontend URL(s) in production rather than "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_service: LiveScoringService | None = None
_repository: DecisionRepository | None = None


@app.on_event("startup")
def startup():
    global _service, _repository
    _service = LiveScoringService()
    # If Postgres isn't reachable, the dashboard's read endpoints and
    # decision persistence won't work, but transaction scoring itself
    # (which doesn't require the repository) still will — this is
    # deliberately not fatal to startup.
    try:
        from src.db.postgres_repository import PostgresDecisionRepository
        _repository = PostgresDecisionRepository()
    except Exception as exc:  # noqa: BLE001 — logged, not fatal
        print(f"Warning: could not connect to Postgres ({exc}). "
              f"Scoring will work; dashboard history/stats will not.")
        _repository = None


@app.get("/health", response_model=HealthResponse)
def health():
    if _service is None:
        return HealthResponse(status="starting", model_loaded=False, known_senders=0)
    return HealthResponse(status="ok", model_loaded=True, known_senders=_service.known_senders)


@app.post("/score", response_model=TransactionScoreResponse)
def score_transaction(transaction: TransactionRequest):
    if _service is None:
        raise HTTPException(status_code=503, detail="Service is still starting up.")

    raw = transaction.model_dump()
    result = _service.score(raw)

    if _repository is not None:
        _repository.save(Decision(
            transaction_id=result.transaction_id,
            sender_upi_id=raw["sender_upi_id"],
            receiver_upi_id=raw["receiver_upi_id"],
            amount=float(raw["amount"]),
            transaction_type=raw["transaction_type"],
            fraud_probability=result.fraud_probability,
            risk_level=result.risk_level,
            triggered_rules=result.triggered_rules,
            final_decision=result.final_decision,
            explanation=result.explanation,
            scored_at=result.scored_at,
        ))

    return TransactionScoreResponse(
        transaction_id=result.transaction_id,
        fraud_probability=result.fraud_probability,
        risk_level=result.risk_level,
        triggered_rules=result.triggered_rules,
        final_decision=result.final_decision,
        explanation=result.explanation,
        scored_at=result.scored_at,
    )


@app.get("/api/decisions/recent", response_model=list[DecisionResponse])
def recent_decisions(limit: int = 50):
    if _repository is None:
        raise HTTPException(status_code=503, detail="Decision history is unavailable (Postgres not connected).")

    decisions = _repository.get_recent(limit=limit)
    return [DecisionResponse(**d.__dict__) for d in decisions]


@app.get("/api/decisions/stats", response_model=DecisionStatsResponse)
def decision_stats():
    if _repository is None:
        raise HTTPException(status_code=503, detail="Decision stats are unavailable (Postgres not connected).")

    by_decision = _repository.count_by_decision()
    by_risk_level = _repository.count_by_risk_level()
    total = sum(by_decision.values())
    return DecisionStatsResponse(total=total, by_decision=by_decision, by_risk_level=by_risk_level)

# PostgreSQL Persistence — Phase 10 Report

**Adds:** `src/db/repository.py` (interface + `InMemoryDecisionRepository`),
`src/db/postgres_repository.py` (real implementation), Postgres
service in `docker-compose.yml`, integration into
`src/streaming/kafka_consumer_app.py`, `verify_postgres_persistence.py`

---

## 0. Sandbox Constraints (Same Pattern as Phases 8 & 9)

No `sqlalchemy`, no `psycopg2`, no local Postgres server, no internet
access — same situation as Kafka and Redis. Same approach applied
again: a `DecisionRepository` interface, a genuinely tested in-memory
implementation, and a real Postgres implementation that's correct,
standard SQLAlchemy code but unexecuted here.

## 1. What Changed

Every scored decision can now be persisted permanently — until this
phase, decisions only ever existed transiently (printed to a terminal,
or published to a Kafka topic that nothing was durably storing). This
phase adds:

- **`Decision`** — a dataclass matching the scoring output schema plus
  a few raw transaction fields (sender, receiver, amount, type) kept
  alongside it so later querying/display doesn't need a join back to
  raw transaction data
- **`InMemoryDecisionRepository`** — plain Python list, same
  "in-memory by default, opt into the real thing" pattern as Phases 8-9
- **`PostgresDecisionRepository`** — a `fraud_decisions` table via
  SQLAlchemy, with `save()` using `session.merge()` (safe to call
  again on the same `transaction_id` without erroring), plus query
  methods (`get_by_id`, `get_recent`, `count_by_decision`,
  `count_by_risk_level`) — the last two exist specifically because
  Phase 11's dashboard is going to need exactly these aggregates
- **`kafka_consumer_app.py`** now accepts an optional `repository` —
  pass nothing and it behaves exactly as it did in Phase 8 (no
  persistence); pass `--postgres` on the command line and it persists
  every decision as it's consumed

## 2. What Was Actually Tested

`tests/test_decision_repository.py` — 8/8 passing:
- Save and retrieve by ID
- Missing ID returns `None` rather than erroring
- `get_recent()` returns newest-first, respects the limit
- `count_by_decision()` and `count_by_risk_level()` aggregate correctly
- **Integration test**: runs the full producer → Kafka (in-memory
  fake) → consumer → repository pipeline end-to-end, confirms every
  scored transaction was actually persisted, and spot-checks that a
  stored record's `fraud_probability`/`final_decision` match what was
  actually computed for it — not just that *something* got saved
- Confirms `repository=None` still works exactly as it did in Phase 8
  (no regression for anyone not using persistence yet)

`tests/test_kafka_consumer_app.py` (Phase 8's tests) were re-run after
this change — still 4/4 passing, confirming the `process_stream()`
signature change didn't break existing behavior.

## 3. What Requires Your Local Machine to Verify

`docker-compose.yml` now includes Postgres alongside Kafka and Redis.
`verify_postgres_persistence.py` follows the same pattern as Phase 9's
Redis verification: write via one connection, read via a completely
independent second connection, confirm the data is actually there.

```bash
docker compose up -d
pip install sqlalchemy psycopg2-binary
python -m src.streaming.verify_postgres_persistence
```

Expected: `ALL RECORDS FOUND — Postgres persistence verified.`

**To see the full pipeline persist real data**, run the Kafka demo
with persistence turned on:
```bash
python -m src.streaming.kafka_consumer_app --postgres
```
then in another terminal, the producer as before. Every decision that
flows through gets permanently saved — you could restart the consumer
afterward and the data would still be there (unlike Phase 8's
in-memory-only run).

**Genuinely curious about this one too:** if you want to look at the
data directly, `docker compose exec postgres psql -U upi_user -d
upi_fraud_detection -c "SELECT final_decision, COUNT(*) FROM
fraud_decisions GROUP BY final_decision;"` should show the same
ALLOW/REVIEW/BLOCK breakdown we've seen everywhere else in this
project.

## 4. Scope Note

This phase makes persistence real and verifiable, but doesn't wire it
in as the *default* for the Kafka consumer (still opt-in via
`--postgres`) — same reasoning as Phase 9's Redis integration:
presenting an untested-here path as the automatic default would be
dishonest about what's actually been confirmed to work. Phase 11 (the
dashboard) is what actually reads from this table to display anything
— untouched until then.

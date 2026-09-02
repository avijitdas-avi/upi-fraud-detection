# Real-Time Streaming Demo — Stepping Stone Toward Phase 8

**Built collaboratively:** `src/streaming/transaction_streamer.py` (project
owner's own code, unchanged) + `prepare_stream_data.py` and
`realtime_processor.py` (this session), connecting the streamer to the
Phase 7 scoring service.

---

## What This Is

A working, end-to-end demonstration of the full pipeline (Phase 3-7:
behavioral features, ML model, rules, decision combination, live
scoring) actually running against a simulated live transaction feed —
before any real Kafka setup. `TransactionStreamer` yields one
transaction at a time from historical data with a configurable delay;
`realtime_processor.py` scores each one as it arrives and prints a
live decision.

**This is explicitly a stepping stone, not Phase 8 itself.** The
milestone list still calls for actual Apache Kafka integration. What
changes when that happens: `TransactionStreamer` becomes a Kafka
producer, `realtime_processor.py` becomes a Kafka consumer — but the
per-transaction scoring logic (`LiveScoringService.score()`) doesn't
need to change at all, since it already doesn't know or care where a
transaction came from. Building this now made that boundary very
concrete rather than theoretical.

## A Real Bug This Caught Before It Shipped

The scoring service warm-starts sender history from historical data.
Streaming that *same* historical data back through as "new"
transactions would have double-counted every sender's history —
transaction counts inflated, already-seen receivers/devices
incorrectly marked "new" again, all of it silently wrong. Fixed by
reusing the exact time-based split from Phase 5/6: warm-start on the
earliest 80% of transactions, stream only the held-out most recent
20% as "new." `src/streaming/prepare_stream_data.py` does this split
and `LiveScoringService` now accepts a `historical_df` parameter to
support it.

## Results — A Genuine Correctness Check, Not Just a Demo

Streaming the held-out 10,000-transaction test set through this
pipeline (the identical set Phase 6 evaluated in batch) produced:

| | Streaming (this) | Batch (Phase 6) |
|---|---|---|
| Precision | 94.5% | 94.5% |
| Recall | 94.9% | 94.9% |
| ALLOW / REVIEW / BLOCK | 9,583 / 28 / 389 | 9,583 / 28 / 389 |

**Exact match.** This is a meaningful validation, not a coincidence —
it confirms the incrementally-computed streaming features
(`RealtimeFeatureComputer`, Phase 7) and the batch-computed features
(Phase 3) produce the same scoring outcomes when fed the same data in
the same order, and that nothing about processing transactions
one-at-a-time introduced any drift from the batch pipeline's behavior.

## How to Run It Yourself

```bash
python -m src.streaming.prepare_stream_data   # run once
python -m src.streaming.realtime_processor --delay 1   # visible real-time pace
python -m src.streaming.realtime_processor --delay 0 --limit 50   # fast test run
```

## Scope Note

This still runs in a single process with an in-memory Python
generator standing in for a message broker — no Kafka, no distributed
consumers, no fault tolerance if the process dies mid-stream. That
real infrastructure is Phase 8 (Kafka) and Phase 9 (Redis for shared
state across multiple consumer processes), both still untouched.

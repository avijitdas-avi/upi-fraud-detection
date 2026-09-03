# Kafka Streaming Integration — Phase 8 Report

**Adds:** `src/streaming/broker_interface.py`, `in_memory_broker.py`,
`kafka_broker.py`, `kafka_transaction_producer.py`,
`kafka_consumer_app.py`, `docker-compose.yml`

---

## 0. Sandbox Constraints (More Severe Than Previous Phases)

Earlier phases (5, 7) worked around missing Python packages by using
built-in alternatives and testing real logic wherever possible. Kafka
is a bigger gap: it requires an actual **running broker process**, not
just a Python package.

This sandbox has:
- **No Docker** (confirmed: `docker --version` → not found)
- **No internet access** to download Kafka itself or `pip install kafka-python`
- Java *is* available (OpenJDK 21), but without network access to fetch
  the Kafka distribution, that alone doesn't help

So unlike Phase 5's XGBoost workaround, **there is no real Kafka broker
this project could connect to in this environment, at all.** Rather
than skip real testing entirely, this phase is built around a
transport-agnostic design specifically so the parts that *can* be
tested honestly are:

- **`src/streaming/broker_interface.py`** — a minimal
  produce/consume interface
- **`src/streaming/in_memory_broker.py`** — a fake implementation of
  that interface using a plain Python `deque`, no external
  dependencies, genuinely tested here
- **`src/streaming/kafka_broker.py`** — the real Kafka implementation
  of the *same* interface, using `kafka-python`. Written correctly,
  matching the documented API, but **not executed or verified in this
  sandbox.**
- **`kafka_transaction_producer.py`** and **`kafka_consumer_app.py`**
  — the actual application logic (publish transactions, consume and
  score them) — written against the interface, not against Kafka
  directly, so it runs identically against either broker
  implementation. **This is the part that matters most for
  correctness, and it was tested for real** (Section 2).

## 1. Design: Why an Interface Instead of Coding Directly Against Kafka

If `kafka_consumer_app.py` called `kafka-python`'s `KafkaConsumer`
directly, none of its logic could be verified here — every test would
need a real broker this sandbox doesn't have. By depending on
`broker_interface.py` instead, and writing `InMemoryBroker` as a
second, real implementation of that same interface, the actual
business logic (score each transaction, publish the decision, don't
drop or duplicate messages) gets tested against something simple and
fast, while `KafkaBroker` remains a thin, swappable adapter for the
real thing. Switching from the fake to real Kafka later is a one-line
change (`InMemoryBroker()` → `KafkaBroker(bootstrap_servers=...)`) —
no application logic changes.

## 2. What Was Actually Tested (`tests/test_kafka_consumer_app.py`)

Using `InMemoryBroker`, 4 tests, all passing:

- Producer correctly publishes N transactions to the `upi-transactions` topic
- Consumer correctly scores each one and publishes a decision to `upi-fraud-decisions`
- **No transactions dropped or duplicated** end-to-end (100 produced → 100 consumed → 100 decisions) — a basic correctness property any real broker also has to satisfy, verified here on the actual scoring logic
- Every published decision matches the expected schema (`risk_level` and `final_decision` are always valid values)

This confirms the actual fraud-scoring pipeline works correctly when
driven by a message-queue-style interface instead of the direct
generator iteration from the earlier non-Kafka streaming demo.

## 3. What Requires Your Local Machine to Verify

`docker-compose.yml` sets up a single-node Kafka broker in KRaft mode
(no separate Zookeeper container needed — Kafka 3.x replaced that).
Since I noticed a Docker Desktop installer already among your files
earlier, this may already be a short step for you:

```bash
docker compose up -d
docker compose ps          # confirm it's healthy
pip install kafka-python
```

Then, in two separate terminals:

```bash
# Terminal 1 — consumer (starts first, waits for messages)
python -m src.streaming.kafka_consumer_app

# Terminal 2 — producer (publishes the held-out test set)
python -m src.streaming.kafka_transaction_producer --delay 0.05
```

You should see the consumer terminal print a running tally as
transactions arrive, matching the same shape of output as the earlier
non-Kafka streaming demo — but this time genuinely flowing through a
real message broker, decoupled across two independent processes.

**Worth verifying and reporting back:** whether the final
precision/recall numbers match the 94.5%/94.9% seen in every other
phase. They should — the scoring logic is unchanged — and confirming
that on your machine would be the same kind of real verification that
caught the scikit-learn version mismatch and the encoding bug earlier
in this project. I can't verify it myself this time; you're in a
better position to than I am, for once.

## 4. Design Note: Why a Separate Decisions Topic

`kafka_consumer_app.py` publishes each scored decision to a second
topic (`upi-fraud-decisions`) rather than only printing it. This sets
up Phase 10 (PostgreSQL persistence) and Phase 11 (dashboard) to
simply consume decisions from Kafka themselves, without needing to
know anything about how scoring happens — the same decoupling
principle that motivated moving off the in-process generator in the
first place.

## 5. Scope Note

This phase adds the actual Kafka producer/consumer code and verifies
the application logic behind it. It does not yet: persist anything to
PostgreSQL (Phase 10), maintain behavioral state in Redis instead of
in-process memory (Phase 9 — next), or serve a dashboard (Phase 11).

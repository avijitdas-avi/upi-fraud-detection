"""
In-Memory Broker (Fake, for Testing)
========================================

A minimal implementation of `broker_interface.py`'s
`MessageProducer`/`MessageConsumer` using plain Python
`collections.deque` — no Kafka, no network, no external process. Its
only job is to let the actual consumer application logic
(`kafka_consumer_app.py`) be genuinely tested in this sandbox, since a
real Kafka broker cannot be (see `docs/kafka_report.md`, Section 0).

This does **not** attempt to simulate Kafka's real behavior in every
respect (no partitioning, no consumer groups, no persistence, no
ordering guarantees beyond simple FIFO, no at-least-once delivery
semantics) — it's deliberately just enough to exercise "produce a
message, then consume it" for correctness testing of the application
logic built on top of it.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterator


class InMemoryBroker:
    """A single object acts as both the producer and consumer side —
    convenient for tests, where both ends live in the same process."""

    def __init__(self):
        self._topics: dict = defaultdict(deque)

    # --- MessageProducer interface ---
    def send(self, topic: str, value: dict) -> None:
        self._topics[topic].append(value)

    # --- MessageConsumer interface ---
    def poll(self, topic: str) -> Iterator[dict]:
        queue = self._topics[topic]
        while queue:
            yield queue.popleft()

    def close(self) -> None:
        pass

    def topic_size(self, topic: str) -> int:
        return len(self._topics[topic])

"""
Message Broker Interface
============================

An abstraction over "publish a message to a topic" / "consume messages
from a topic" that the rest of this phase's code depends on, instead
of depending on Kafka directly.

Why this matters for this specific project: this development sandbox
has no internet access and no Docker, so an actual Kafka broker cannot
be run or connected to here (see `docs/kafka_report.md`, Section 0).
By coding the actual consumer/producer *application* logic against
this interface rather than against `kafka-python` directly, that
application logic can be — and is — genuinely tested in this sandbox
using `InMemoryBroker` (`in_memory_broker.py`), while
`KafkaBroker` (`kafka_broker.py`) provides the real implementation for
you to run once you have Kafka available locally (via
`docker-compose.yml`). Swapping between them is a one-line change; the
application code that uses this interface doesn't change at all.
"""

from __future__ import annotations

from typing import Iterator, Protocol


class MessageProducer(Protocol):
    def send(self, topic: str, value: dict) -> None:
        """Publish one message (a JSON-serializable dict) to a topic."""
        ...

    def close(self) -> None:
        ...


class MessageConsumer(Protocol):
    def poll(self, topic: str) -> Iterator[dict]:
        """Yield messages from a topic as they become available.
        For a real Kafka consumer this blocks/streams indefinitely;
        for the in-memory fake it yields whatever has been produced
        so far and then stops — see each implementation for details."""
        ...

    def close(self) -> None:
        ...

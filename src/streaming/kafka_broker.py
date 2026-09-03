"""
Kafka Broker (Real Implementation)
======================================

*** NOT EXECUTED IN THIS DEVELOPMENT SANDBOX — see docs/kafka_report.md,
Section 0. No internet access to install `kafka-python`, no Docker to
run a broker, so this could not be tested here. It implements the
same interface as `in_memory_broker.py` (`broker_interface.py`), which
*was* tested — the application logic in `kafka_consumer_app.py` and
`kafka_transaction_producer.py` doesn't change at all when you swap
this in for the fake. ***

Requires a running Kafka broker (see `docker-compose.yml` at the
project root) and `pip install kafka-python`.

Usage once both are available:
    broker = KafkaBroker(bootstrap_servers="localhost:9092")
    broker.send("upi-transactions", {"transaction_id": "...", ...})
    for message in broker.poll("upi-transactions"):
        ...
"""

from __future__ import annotations

import json
from typing import Iterator

from kafka import KafkaConsumer, KafkaProducer


class KafkaBroker:
    def __init__(self, bootstrap_servers: str = "localhost:9092", consumer_group: str = "upi-fraud-detection"):
        self.bootstrap_servers = bootstrap_servers
        self.consumer_group = consumer_group
        self._producer: KafkaProducer | None = None
        self._consumers: dict = {}

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
        return self._producer

    def send(self, topic: str, value: dict) -> None:
        producer = self._get_producer()
        producer.send(topic, value=value)
        producer.flush()

    def poll(self, topic: str) -> Iterator[dict]:
        if topic not in self._consumers:
            self._consumers[topic] = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="earliest",
            )
        consumer = self._consumers[topic]
        for message in consumer:  # blocks, streams indefinitely — this is real Kafka's actual behavior
            yield message.value

    def close(self) -> None:
        if self._producer is not None:
            self._producer.close()
        for consumer in self._consumers.values():
            consumer.close()

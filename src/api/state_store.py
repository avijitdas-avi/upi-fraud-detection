"""
Sender State Store (Phase 9)
================================

Where `RealtimeFeatureComputer` (Phase 7) actually keeps each sender's
running behavioral state. Before this phase, that state lived directly
in a Python dict inside the computer itself — meaning it vanished on
restart and couldn't be shared across multiple API processes. This
module pulls that storage out into a pluggable interface with two
implementations:

- **`InMemoryStateStore`** — the same plain-dict behavior as before,
  now formalized as one implementation of the interface rather than
  hardcoded. **Genuinely tested** — re-running Phase 7's full-dataset
  replay validation against this implementation (see
  `tests/test_feature_lookup.py`) reproduces the exact same 99.93%
  match rate as before the refactor, confirming this change didn't
  alter behavior.
- **`RedisStateStore`** — persists each sender's state as a single
  JSON blob under a `sender_state:{sender_id}` key. *** NOT EXECUTED
  IN THIS DEVELOPMENT SANDBOX — no internet access to install
  `redis-py`, no Docker to run a Redis server (see
  `docs/redis_report.md`, Section 0). What *is* tested directly,
  without needing a real Redis connection: the serialization
  round-trip itself (`_SenderState.to_dict()` /
  `.from_dict()`, tested in `tests/test_state_serialization.py`) —
  the part of this most likely to have actual bugs, independent of
  whether the network call to Redis succeeds. ***

Swapping between them is a one-line change in whatever constructs
`RealtimeFeatureComputer` — none of that class's logic needs to know
or care which store is behind it.
"""

from __future__ import annotations

import json
from typing import Protocol

from src.api.feature_lookup import _SenderState


class StateStore(Protocol):
    def get(self, sender_id: str) -> _SenderState:
        """Return the sender's current state, or a fresh empty state
        if this sender has never been seen before."""
        ...

    def set(self, sender_id: str, state: _SenderState) -> None:
        """Persist the sender's state."""
        ...


class InMemoryStateStore:
    """Plain Python dict, in this process's memory only — lost on
    restart, not shared across processes. This is the same behavior
    RealtimeFeatureComputer had built-in before this phase; it's the
    default so existing code (Phase 7's scoring service, tests) keeps
    working unchanged."""

    def __init__(self):
        self._data: dict = {}

    def get(self, sender_id: str) -> _SenderState:
        if sender_id not in self._data:
            self._data[sender_id] = _SenderState()
        return self._data[sender_id]

    def set(self, sender_id: str, state: _SenderState) -> None:
        self._data[sender_id] = state


class RedisStateStore:
    """
    *** NOT EXECUTED IN THIS DEVELOPMENT SANDBOX — see module
    docstring above. *** Requires a running Redis server (see
    `docker-compose.yml` at the project root) and `pip install redis`.

    Usage once both are available:
        store = RedisStateStore(host="localhost", port=6379)
        computer = RealtimeFeatureComputer(state_store=store)
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, key_prefix: str = "sender_state:"):
        import redis  # imported here so this module can still be imported
                       # (e.g. for InMemoryStateStore, or for tests that only
                       # exercise serialization) without requiring the redis
                       # package to be installed.
        self._client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self._key_prefix = key_prefix

    def _key(self, sender_id: str) -> str:
        return f"{self._key_prefix}{sender_id}"

    def get(self, sender_id: str) -> _SenderState:
        raw = self._client.get(self._key(sender_id))
        if raw is None:
            return _SenderState()
        return _SenderState.from_dict(json.loads(raw))

    def set(self, sender_id: str, state: _SenderState) -> None:
        self._client.set(self._key(sender_id), json.dumps(state.to_dict()))

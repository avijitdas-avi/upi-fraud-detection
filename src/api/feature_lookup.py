"""
Real-Time Feature Computer
=============================

The decision engine (Phase 6) scores rows that already have behavioral
features attached — computed in batch, offline, by
`src/features/behavioral_features.py` (Phase 3), which can look at an
entire sorted dataset at once. A live API can't do that: it receives
one transaction at a time and has to compute that sender's behavioral
features **incrementally**, using only what's happened before, without
re-scanning history from scratch on every request.

This module maintains a running per-sender state (transaction count,
mean/std of amounts via Welford's algorithm, recent timestamps for
velocity windows, and seen-before counts for device/location/receiver)
and updates it incrementally — the same information Phase 3's batch
script computed, produced the same way a real system would: one
transaction at a time, in memory.

This is an **honest simplification**, not the final architecture: it's
a single-process, in-memory implementation. The real system (Phase 9)
will keep this same state in Redis instead of a Python dict, so it
survives restarts and works across multiple API processes. The
computation logic here — Welford's algorithm, the windowed counts, the
seen-before tracking — is written so it can move to Redis later with
minimal changes to the *logic*, just the storage layer.

**Correctness was verified**, not assumed: `tests/test_feature_lookup.py`
replays the entire Phase 3 dataset through this computer one
transaction at a time and compares its output, row by row, against
Phase 3's own batch-computed features — see that file's docstring and
`docs/api_report.md` (Phase 7) for the actual match-rate results.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional


@dataclass
class _SenderState:
    count: int = 0
    mean_amount: float = 0.0
    m2_amount: float = 0.0  # Welford's running sum of squared differences
    mean_hour: float = 0.0
    m2_hour: float = 0.0
    last_timestamp: Optional[datetime] = None
    recent_timestamps: deque = field(default_factory=deque)  # trailing 24h window
    device_counts: dict = field(default_factory=lambda: defaultdict(int))
    location_counts: dict = field(default_factory=lambda: defaultdict(int))
    receiver_counts: dict = field(default_factory=lambda: defaultdict(int))

    def std_amount(self) -> float:
        if self.count < 2:
            return float("nan")
        return math.sqrt(self.m2_amount / (self.count - 1))  # sample std, ddof=1 — matches pandas .std()

    def mean_amount_or_nan(self) -> float:
        return self.mean_amount if self.count >= 1 else float("nan")

    def mean_hour_or_nan(self) -> float:
        return self.mean_hour if self.count >= 1 else float("nan")


NO_PRIOR_TXN_SENTINEL_SECONDS = 9_999_999.0


class RealtimeFeatureComputer:
    def __init__(self):
        self._senders: dict = defaultdict(_SenderState)

    def warm_start(self, historical_rows) -> None:
        """Replay historical transactions (in chronological order) to
        build up per-sender state, so senders with existing history
        get correct features on their very next transaction rather
        than being treated as brand new."""
        for row in historical_rows:
            self.record_transaction(row)

    def compute_features(self, transaction: Mapping[str, Any]) -> dict:
        """Compute this transaction's behavioral features using only
        the sender's history *before* it — does not modify state.
        Call `record_transaction` afterward to add it to history."""
        sender = transaction["sender_upi_id"]
        state = self._senders[sender]
        timestamp: datetime = transaction["timestamp"]
        amount: float = transaction["amount"]
        hour: int = transaction["hour_of_day"]

        prior_avg = state.mean_amount_or_nan()
        prior_std = state.std_amount()
        safe_std = prior_std if (prior_std and prior_std > 0) else float("nan")
        safe_avg = prior_avg if (prior_avg and prior_avg > 0) else float("nan")

        amount_zscore = (amount - prior_avg) / safe_std if not math.isnan(safe_std) and not math.isnan(prior_avg) else float("nan")
        amount_ratio = amount / safe_avg if not math.isnan(safe_avg) else float("nan")

        if state.last_timestamp is not None:
            seconds_since_last = (timestamp - state.last_timestamp).total_seconds()
        else:
            seconds_since_last = float("nan")

        self._prune_old(state, timestamp)
        count_1h = sum(1 for t in state.recent_timestamps if t >= timestamp - timedelta(hours=1))
        count_24h = len(state.recent_timestamps)  # deque is already pruned to 24h

        device_id = transaction.get("device_id")
        location = transaction.get("location")
        receiver = transaction.get("receiver_upi_id")

        device_seen = state.device_counts.get(device_id, 0)
        location_seen = state.location_counts.get(location, 0)
        receiver_seen = state.receiver_counts.get(receiver, 0)

        typical_hour_prior = state.mean_hour_or_nan()
        if not math.isnan(typical_hour_prior):
            raw_diff = abs(hour - typical_hour_prior)
            hour_deviation = min(raw_diff, 24 - raw_diff)
        else:
            hour_deviation = float("nan")

        return {
            "sender_prior_txn_count": state.count,
            "sender_avg_amount_prior": prior_avg,
            "sender_std_amount_prior": prior_std,
            "amount_zscore_vs_sender": amount_zscore,
            "amount_ratio_vs_sender_avg": amount_ratio,
            "seconds_since_last_txn": seconds_since_last,
            "sender_txn_count_last_1h": float(count_1h),
            "sender_txn_count_last_24h": float(count_24h),
            "device_seen_count_prior": device_seen,
            "is_new_device_derived": device_seen == 0,
            "location_seen_count_prior": location_seen,
            "is_new_location_derived": location_seen == 0,
            "receiver_seen_count_prior": receiver_seen,
            "is_new_receiver_derived": receiver_seen == 0,
            "sender_typical_hour_prior": typical_hour_prior,
            "hour_deviation_from_typical": hour_deviation,
        }

    def record_transaction(self, transaction: Mapping[str, Any]) -> None:
        """Update the sender's running state to include this transaction."""
        sender = transaction["sender_upi_id"]
        state = self._senders[sender]
        timestamp: datetime = transaction["timestamp"]
        amount: float = transaction["amount"]
        hour: int = transaction["hour_of_day"]

        # Welford's online algorithm for running mean/variance
        state.count += 1
        delta = amount - state.mean_amount
        state.mean_amount += delta / state.count
        delta2 = amount - state.mean_amount
        state.m2_amount += delta * delta2

        hour_delta = hour - state.mean_hour
        state.mean_hour += hour_delta / state.count
        hour_delta2 = hour - state.mean_hour
        state.m2_hour += hour_delta * hour_delta2

        state.last_timestamp = timestamp
        self._prune_old(state, timestamp)
        state.recent_timestamps.append(timestamp)

        device_id = transaction.get("device_id")
        location = transaction.get("location")
        receiver = transaction.get("receiver_upi_id")
        if device_id is not None:
            state.device_counts[device_id] += 1
        if location is not None:
            state.location_counts[location] += 1
        if receiver is not None:
            state.receiver_counts[receiver] += 1

    @staticmethod
    def _prune_old(state: _SenderState, current_time: datetime) -> None:
        cutoff = current_time - timedelta(hours=24)
        while state.recent_timestamps and state.recent_timestamps[0] < cutoff:
            state.recent_timestamps.popleft()

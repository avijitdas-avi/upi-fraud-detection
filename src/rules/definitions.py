"""
Rule Definitions
==================

One class per fraud-pattern check, matching the six candidate rules
listed in `docs/project_specification.md` (Section 8). Each rule is
independently testable (see `tests/test_rules.py`) and only depends on
fields already present in `data/processed/behavioral_features.csv`
(the Phase 3 output) plus the raw transaction fields.

All rules treat a missing (NaN) feature value as "cannot evaluate, so
do not trigger" rather than as a positive signal — a transaction with
no prior history for a sender shouldn't be penalized by rules that
require history to compute (e.g. amount z-score). This mirrors how the
real-time system will behave: a brand-new sender has no track record
to compare against yet.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from src.rules.base import RuleResult
from src.rules.config import RuleConfig


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


class HighAmountDeviationRule:
    rule_id = "HIGH_AMOUNT_DEVIATION"
    description = "Transaction amount exceeds N standard deviations from the sender's historical average."

    def __init__(self, config: RuleConfig):
        self.threshold = config.amount_zscore_threshold

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        zscore = transaction.get("amount_zscore_vs_sender")
        if _is_missing(zscore):
            return RuleResult(self.rule_id, False, "Insufficient sender history to evaluate.")
        triggered = zscore >= self.threshold
        detail = f"amount z-score={zscore:.2f} (threshold={self.threshold})"
        return RuleResult(self.rule_id, triggered, detail)


class VelocityRule:
    rule_id = "VELOCITY_BURST"
    description = "More than N transactions from the same sender within a short (1 hour) time window."

    def __init__(self, config: RuleConfig):
        self.threshold = config.velocity_1h_threshold

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        count_1h = transaction.get("sender_txn_count_last_1h")
        if _is_missing(count_1h):
            return RuleResult(self.rule_id, False, "Insufficient sender history to evaluate.")
        triggered = count_1h >= self.threshold
        detail = f"{count_1h:.0f} prior transactions in the last hour (threshold={self.threshold})"
        return RuleResult(self.rule_id, triggered, detail)


class NewReceiverHighValueRule:
    rule_id = "NEW_RECEIVER_HIGH_VALUE"
    description = "First-time transaction to a new receiver combined with a high-value amount."

    def __init__(self, config: RuleConfig):
        self.ratio_threshold = config.new_receiver_amount_ratio_threshold

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        is_new_receiver = transaction.get("is_new_receiver_derived")
        ratio = transaction.get("amount_ratio_vs_sender_avg")
        if is_new_receiver is None or _is_missing(ratio):
            return RuleResult(self.rule_id, False, "Insufficient sender history to evaluate.")
        triggered = bool(is_new_receiver) and ratio >= self.ratio_threshold
        detail = (
            f"new_receiver={bool(is_new_receiver)}, "
            f"amount is {ratio:.2f}x sender's average (threshold={self.ratio_threshold}x)"
        )
        return RuleResult(self.rule_id, triggered, detail)


class NewDeviceNewLocationRule:
    rule_id = "NEW_DEVICE_AND_LOCATION"
    description = "Transaction from a new/unrecognized device and a new location simultaneously."

    def __init__(self, config: RuleConfig):
        pass

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        is_new_device = transaction.get("is_new_device_derived")
        is_new_location = transaction.get("is_new_location_derived")
        if is_new_device is None or is_new_location is None:
            return RuleResult(self.rule_id, False, "Novelty features unavailable.")
        triggered = bool(is_new_device) and bool(is_new_location)
        detail = f"new_device={bool(is_new_device)}, new_location={bool(is_new_location)}"
        return RuleResult(self.rule_id, triggered, detail)


class OddHourRule:
    rule_id = "ODD_HOUR"
    description = "Transaction occurring at an hour atypical for ordinary UPI usage."

    def __init__(self, config: RuleConfig):
        self.odd_hours = set(config.odd_hours)

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        hour = transaction.get("hour_of_day")
        if hour is None or _is_missing(hour):
            return RuleResult(self.rule_id, False, "Hour unavailable.")
        triggered = int(hour) in self.odd_hours
        detail = f"hour_of_day={int(hour)} (odd hours={sorted(self.odd_hours)})"
        return RuleResult(self.rule_id, triggered, detail)


class BlocklistRule:
    rule_id = "BLOCKLIST"
    description = "Sender or receiver present on a known blocklist."

    def __init__(self, config: RuleConfig):
        self.blocked_senders = config.blocked_senders
        self.blocked_receivers = config.blocked_receivers

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        sender = transaction.get("sender_upi_id")
        receiver = transaction.get("receiver_upi_id")
        sender_blocked = sender in self.blocked_senders
        receiver_blocked = receiver in self.blocked_receivers
        triggered = sender_blocked or receiver_blocked
        detail = f"sender_blocked={sender_blocked}, receiver_blocked={receiver_blocked}"
        return RuleResult(self.rule_id, triggered, detail)


def build_default_rules(config: RuleConfig | None = None) -> list:
    """Instantiate all six rules with the given (or default) configuration."""
    cfg = config or RuleConfig()
    return [
        HighAmountDeviationRule(cfg),
        VelocityRule(cfg),
        NewReceiverHighValueRule(cfg),
        NewDeviceNewLocationRule(cfg),
        OddHourRule(cfg),
        BlocklistRule(cfg),
    ]

"""
Unit tests for the rule-based detection engine (Phase 4).

Each rule is tested in isolation with hand-built transaction dicts so
that pass/fail conditions are unambiguous and don't depend on the
generated dataset.
"""

import math

from src.rules.config import RuleConfig
from src.rules.definitions import (
    BlocklistRule,
    HighAmountDeviationRule,
    NewDeviceNewLocationRule,
    NewReceiverHighValueRule,
    OddHourRule,
    VelocityRule,
    build_default_rules,
)
from src.rules.engine import RuleEngine


def make_config() -> RuleConfig:
    return RuleConfig(
        amount_zscore_threshold=3.0,
        velocity_1h_threshold=3,
        new_receiver_amount_ratio_threshold=2.5,
        odd_hours=(0, 1, 2, 3, 4),
        blocked_senders=frozenset({"blocked@upi"}),
        blocked_receivers=frozenset({"blockedreceiver@upi"}),
    )


# --- HighAmountDeviationRule ---

def test_high_amount_deviation_triggers_above_threshold():
    rule = HighAmountDeviationRule(make_config())
    result = rule.evaluate({"amount_zscore_vs_sender": 4.2})
    assert result.triggered is True


def test_high_amount_deviation_does_not_trigger_below_threshold():
    rule = HighAmountDeviationRule(make_config())
    result = rule.evaluate({"amount_zscore_vs_sender": 1.0})
    assert result.triggered is False


def test_high_amount_deviation_handles_missing_history():
    rule = HighAmountDeviationRule(make_config())
    result = rule.evaluate({"amount_zscore_vs_sender": math.nan})
    assert result.triggered is False


# --- VelocityRule ---

def test_velocity_triggers_on_burst():
    rule = VelocityRule(make_config())
    result = rule.evaluate({"sender_txn_count_last_1h": 5})
    assert result.triggered is True


def test_velocity_does_not_trigger_under_threshold():
    rule = VelocityRule(make_config())
    result = rule.evaluate({"sender_txn_count_last_1h": 1})
    assert result.triggered is False


# --- NewReceiverHighValueRule ---

def test_new_receiver_high_value_triggers():
    rule = NewReceiverHighValueRule(make_config())
    result = rule.evaluate({"is_new_receiver_derived": True, "amount_ratio_vs_sender_avg": 3.0})
    assert result.triggered is True


def test_new_receiver_high_value_does_not_trigger_for_known_receiver():
    rule = NewReceiverHighValueRule(make_config())
    result = rule.evaluate({"is_new_receiver_derived": False, "amount_ratio_vs_sender_avg": 3.0})
    assert result.triggered is False


def test_new_receiver_high_value_does_not_trigger_for_low_amount():
    rule = NewReceiverHighValueRule(make_config())
    result = rule.evaluate({"is_new_receiver_derived": True, "amount_ratio_vs_sender_avg": 1.1})
    assert result.triggered is False


# --- NewDeviceNewLocationRule ---

def test_new_device_and_location_triggers_only_when_both_true():
    rule = NewDeviceNewLocationRule(make_config())
    assert rule.evaluate({"is_new_device_derived": True, "is_new_location_derived": True}).triggered is True
    assert rule.evaluate({"is_new_device_derived": True, "is_new_location_derived": False}).triggered is False
    assert rule.evaluate({"is_new_device_derived": False, "is_new_location_derived": True}).triggered is False


# --- OddHourRule ---

def test_odd_hour_triggers_in_configured_range():
    rule = OddHourRule(make_config())
    assert rule.evaluate({"hour_of_day": 2}).triggered is True


def test_odd_hour_does_not_trigger_during_the_day():
    rule = OddHourRule(make_config())
    assert rule.evaluate({"hour_of_day": 14}).triggered is False


# --- BlocklistRule ---

def test_blocklist_triggers_for_blocked_sender():
    rule = BlocklistRule(make_config())
    result = rule.evaluate({"sender_upi_id": "blocked@upi", "receiver_upi_id": "ok@upi"})
    assert result.triggered is True


def test_blocklist_triggers_for_blocked_receiver():
    rule = BlocklistRule(make_config())
    result = rule.evaluate({"sender_upi_id": "ok@upi", "receiver_upi_id": "blockedreceiver@upi"})
    assert result.triggered is True


def test_blocklist_does_not_trigger_for_clean_parties():
    rule = BlocklistRule(make_config())
    result = rule.evaluate({"sender_upi_id": "ok@upi", "receiver_upi_id": "alsook@upi"})
    assert result.triggered is False


# --- RuleEngine ---

def test_engine_aggregates_multiple_triggered_rules():
    engine = RuleEngine(config=make_config())
    transaction = {
        "amount_zscore_vs_sender": 5.0,          # triggers HIGH_AMOUNT_DEVIATION
        "sender_txn_count_last_1h": 4,             # triggers VELOCITY_BURST
        "is_new_receiver_derived": False,
        "amount_ratio_vs_sender_avg": 1.0,
        "is_new_device_derived": False,
        "is_new_location_derived": False,
        "hour_of_day": 12,
        "sender_upi_id": "ok@upi",
        "receiver_upi_id": "alsook@upi",
    }
    output = engine.evaluate(transaction)
    assert output.triggered_count == 2
    assert "HIGH_AMOUNT_DEVIATION" in output.triggered_rule_ids
    assert "VELOCITY_BURST" in output.triggered_rule_ids


def test_engine_no_triggers_on_clean_transaction():
    engine = RuleEngine(config=make_config())
    transaction = {
        "amount_zscore_vs_sender": 0.1,
        "sender_txn_count_last_1h": 0,
        "is_new_receiver_derived": False,
        "amount_ratio_vs_sender_avg": 1.0,
        "is_new_device_derived": False,
        "is_new_location_derived": False,
        "hour_of_day": 12,
        "sender_upi_id": "ok@upi",
        "receiver_upi_id": "alsook@upi",
    }
    output = engine.evaluate(transaction)
    assert output.triggered_count == 0


def test_build_default_rules_returns_all_six():
    rules = build_default_rules()
    assert len(rules) == 6
    rule_ids = {r.rule_id for r in rules}
    assert rule_ids == {
        "HIGH_AMOUNT_DEVIATION",
        "VELOCITY_BURST",
        "NEW_RECEIVER_HIGH_VALUE",
        "NEW_DEVICE_AND_LOCATION",
        "ODD_HOUR",
        "BLOCKLIST",
    }

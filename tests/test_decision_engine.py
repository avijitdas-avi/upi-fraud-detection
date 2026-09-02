"""
Unit tests for the pure decision-combination logic in
`src/models/decision_engine.py` — risk level thresholds, rule
escalation, and the hard-rule override. Does not require the trained
model or dataset (those are exercised end-to-end by
`run_decision_engine.py`, not here).
"""

from src.models.decision_engine import (
    combine_risk_level,
    decision_from_risk_level,
    risk_level_from_probability,
)
from src.rules.engine import RuleEngineOutput


def make_rule_output(triggered_ids):
    return RuleEngineOutput(
        triggered_rule_ids=list(triggered_ids),
        triggered_count=len(triggered_ids),
        all_results=[],
    )


# --- risk_level_from_probability ---

def test_probability_maps_to_low():
    assert risk_level_from_probability(0.10) == "LOW"


def test_probability_maps_to_medium():
    assert risk_level_from_probability(0.45) == "MEDIUM"


def test_probability_maps_to_high():
    assert risk_level_from_probability(0.70) == "HIGH"


def test_probability_maps_to_critical():
    assert risk_level_from_probability(0.95) == "CRITICAL"


def test_probability_boundary_values():
    assert risk_level_from_probability(0.30) == "MEDIUM"  # boundary is inclusive on the upper bucket
    assert risk_level_from_probability(0.60) == "HIGH"
    assert risk_level_from_probability(0.85) == "CRITICAL"
    assert risk_level_from_probability(1.00) == "CRITICAL"


# --- combine_risk_level ---

def test_no_rules_uses_base_probability_level():
    result = combine_risk_level(0.10, make_rule_output([]))
    assert result == "LOW"


def test_single_triggered_rule_does_not_escalate():
    result = combine_risk_level(0.10, make_rule_output(["ODD_HOUR"]))
    assert result == "LOW"


def test_two_triggered_rules_escalate_one_tier():
    result = combine_risk_level(0.10, make_rule_output(["ODD_HOUR", "NEW_DEVICE_AND_LOCATION"]))
    assert result == "MEDIUM"


def test_escalation_caps_at_critical():
    result = combine_risk_level(0.90, make_rule_output(["ODD_HOUR", "NEW_DEVICE_AND_LOCATION"]))
    assert result == "CRITICAL"


def test_blocklist_forces_critical_regardless_of_probability():
    result = combine_risk_level(0.01, make_rule_output(["BLOCKLIST"]))
    assert result == "CRITICAL"


def test_blocklist_with_low_probability_and_no_other_rules_still_critical():
    result = combine_risk_level(0.0, make_rule_output(["BLOCKLIST"]))
    assert result == "CRITICAL"


# --- decision_from_risk_level ---

def test_low_and_medium_map_to_allow():
    assert decision_from_risk_level("LOW") == "ALLOW"
    assert decision_from_risk_level("MEDIUM") == "ALLOW"


def test_high_maps_to_review():
    assert decision_from_risk_level("HIGH") == "REVIEW"


def test_critical_maps_to_block():
    assert decision_from_risk_level("CRITICAL") == "BLOCK"

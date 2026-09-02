"""
Rule Engine
=============

Runs a set of rules against a single transaction and collects the
results. This is deliberately minimal for Phase 4: it reports which
rules triggered and how many, but does **not** combine that with an ML
score or assign a final risk level / decision — that combination logic
is Phase 6 (per `docs/project_specification.md`, Section 10). Keeping
that boundary clean means this engine can be tested and evaluated on
its own before it's wired into anything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.rules.base import RuleResult
from src.rules.config import RuleConfig
from src.rules.definitions import build_default_rules


@dataclass
class RuleEngineOutput:
    triggered_rule_ids: list
    triggered_count: int
    all_results: list  # every RuleResult, triggered or not — useful for debugging/audit


class RuleEngine:
    def __init__(self, rules: Sequence | None = None, config: RuleConfig | None = None):
        self.rules = list(rules) if rules is not None else build_default_rules(config)

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleEngineOutput:
        results = [rule.evaluate(transaction) for rule in self.rules]
        triggered = [r.rule_id for r in results if r.triggered]
        return RuleEngineOutput(
            triggered_rule_ids=triggered,
            triggered_count=len(triggered),
            all_results=results,
        )

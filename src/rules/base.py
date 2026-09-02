"""
Rule Engine — Base Types
=========================

Defines the shared interface every rule implements, and the result
type each rule returns. Keeping this separate from the actual rule
definitions (`definitions.py`) means new rules can be added later
without touching the engine or the interface.

A rule receives a single transaction as a mapping (works for both a
`pandas.Series` — one row of a DataFrame — and a plain `dict`, e.g. a
single incoming transaction in the future real-time path) and returns
a `RuleResult` describing whether it triggered and why.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    triggered: bool
    detail: str


class Rule(Protocol):
    """Interface every rule must implement."""

    rule_id: str
    description: str

    def evaluate(self, transaction: Mapping[str, Any]) -> RuleResult:
        ...

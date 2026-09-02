"""
Rule Configuration
====================

Central place for every threshold used by the rule engine, so rules
can be tuned without touching their logic. Defaults below were chosen
by looking at the class-separation numbers in
`docs/eda_report.md` (Phase 3) — they are deliberately conservative
starting points, not final tuned values. Threshold tuning against
labeled outcomes is expected to happen later, once the ML model
(Phase 5) and the combined decision layer (Phase 6) exist and rule
precision/recall can be evaluated jointly with the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuleConfig:
    # Rule 1 — High Amount Deviation
    # EDA: fraud avg z-score ~5.66 vs ~0 for legit. 3.0 catches strong
    # outliers while leaving room for normal variance.
    amount_zscore_threshold: float = 3.0

    # Rule 2 — Velocity (transactions in trailing 1 hour)
    # EDA: fraud avg 2.36 txns/hr vs 0.06 for legit.
    velocity_1h_threshold: int = 3

    # Rule 3 — New Receiver + High Value
    # "High value" here means a multiple of the sender's own historical average.
    new_receiver_amount_ratio_threshold: float = 2.5

    # Rule 5 — Odd Hour
    # Hours considered atypical for ordinary UPI usage, regardless of the
    # sender's own pattern (a coarse, universal check — complements the
    # sender-specific `hour_deviation_from_typical` feature from Phase 3,
    # which is not used directly as a rule here to avoid duplicating
    # Rule 4's device/location novelty logic).
    odd_hours: tuple = field(default_factory=lambda: (0, 1, 2, 3, 4))

    # Rule 6 — Blocklist
    # No real blocklist data exists yet — this starts empty and is meant
    # to be populated from a real blocklist source in a later phase.
    blocked_senders: frozenset = field(default_factory=frozenset)
    blocked_receivers: frozenset = field(default_factory=frozenset)


DEFAULT_CONFIG = RuleConfig()

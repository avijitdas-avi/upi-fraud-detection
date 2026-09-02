# Rule-Based Detection Engine — Phase 4 Report

**Engine:** `src/rules/` (6 rules, per `docs/project_specification.md`, Section 8)
**Evaluated on:** `data/processed/behavioral_features.csv` (50,000 transactions, 4.00% fraud)
**Output:** `data/processed/rule_engine_results.csv`

This evaluates the rule engine **in isolation** — no ML involved. The
goal is to establish a rules-only baseline before Phase 5 introduces a
model, so we can later measure how much the ML model actually adds on
top of deterministic rules, rather than assuming it helps.

---

## 1. Overall Performance

| Metric | Value |
|---|---|
| Transactions flagged by ≥1 rule | 4,796 (9.6% of all transactions) |
| Fraud caught (true positives) | 1,540 |
| False positives | 3,256 |
| Fraud missed (false negatives) | 460 |
| **Precision** (of flagged, % actually fraud) | **32.1%** |
| **Recall** (of fraud, % flagged) | **77.0%** |

Rules alone catch more than three-quarters of simulated fraud, but at
a real cost: roughly 2 out of every 3 flagged transactions are
actually legitimate. That's expected from rules built without any
statistical fitting — they're deliberately blunt, explainable
instruments. Reducing that false-positive rate while keeping recall
high is exactly the job Phase 5 (ML) and Phase 6 (combined decision
layer) need to do.

## 2. Per-Rule Breakdown

| Rule | Times triggered | Were fraud | Precision |
|---|---|---|---|
| `VELOCITY_BURST` | 718 | 712 | **99.2%** |
| `NEW_RECEIVER_HIGH_VALUE` | 462 | 382 | **82.7%** |
| `HIGH_AMOUNT_DEVIATION` | 1,062 | 559 | 52.6% |
| `ODD_HOUR` | 1,989 | 482 | 24.2% |
| `NEW_DEVICE_AND_LOCATION` | 1,458 | 221 | 15.2% |
| `BLOCKLIST` | 0 | 0 | — (no blocklist data yet) |

**Takeaways:**
- `VELOCITY_BURST` is an almost perfect rule on this dataset — nearly
  every trigger is real fraud. Makes sense: legitimate senders rarely
  cross 3 transactions/hour, so the threshold is doing its job cleanly.
- `NEW_RECEIVER_HIGH_VALUE` is also strong (82.7% precision) and
  catches a fraud pattern the other rules mostly miss (phishing-induced
  fraud — see Section 3).
- `HIGH_AMOUNT_DEVIATION` and especially `ODD_HOUR` and
  `NEW_DEVICE_AND_LOCATION` are much noisier — they trigger on plenty
  of ordinary behavior too (an unusually large but legitimate purchase,
  someone genuinely up late, a new phone). These are reasonable
  candidates for the ML model to help disambiguate, rather than
  relying on the rule alone.
- `BLOCKLIST` never triggers, as expected — there's no real blocklist
  data yet. This rule exists as a stub for when one becomes available
  (e.g. reported-fraud accounts from a later phase or external source).

## 3. What the Rules Miss

460 of 2,000 fraud transactions (23%) were not flagged by any rule.
Breaking that down by fraud type:

| Fraud type | Missed |
|---|---|
| `velocity_fraud` | 254 |
| `micro_transaction_probing` | 155 |
| `mule_account` | 49 |
| `phishing_induced` | 1 |
| `unusual_geo_device` | 1 |

**Why `velocity_fraud` is partially missed:** this isn't a rule design
flaw so much as a structural limit of single-transaction rules. A
velocity burst is only *detectable* once enough of the burst has
already happened — the `sender_txn_count_last_1h` feature only counts
transactions **before** the current one. Checking the actual data: the
891 `velocity_fraud` transactions split into two groups — the 637 that
were caught average 5.7 prior transactions in the trailing hour, while
the 254 that were missed average just 1.0. In other words, the rule
correctly catches a burst partway through, but the burst's first one
or two transactions look identical to an ordinary transaction, because
there's nothing unusual in their own history yet. Catching those
earlier would need either a lower threshold (at the cost of far more
false positives) or a different mechanism entirely (e.g. flagging
retroactively once a burst is detected) — a design question worth
revisiting once Kafka/Redis streaming state exists (Phase 8–9).

**Why `micro_transaction_probing` is largely missed:** the small
"probe" amounts are, individually, unremarkable — a ₹5 transaction
doesn't trigger `HIGH_AMOUNT_DEVIATION`, and probes often go to a
receiver the sender may have technically "seen" once already within
the same probing sequence, so `NEW_RECEIVER_HIGH_VALUE` doesn't
always apply either. This fraud type is a good candidate for a
dedicated future rule (e.g. "N small transactions to the same receiver
within a short window, followed by a larger one") rather than
forcing it through the existing six.

**Why `mule_account` is partially missed:** mule transactions are
large and rapid but go to a receiver the sender has, by construction,
just started transacting with repeatedly — so `VELOCITY_BURST` and
`NEW_RECEIVER_HIGH_VALUE` catch many of them, but not all, depending
on timing.

These gaps are documented here rather than patched by adding more
rules right now — the spec's rule list (Section 8) is intentionally a
starting point, and closing these gaps with more bespoke rules risks
overfitting the rule engine to this specific simulated dataset. The
plan is to let the ML model (Phase 5) pick up on the more subtle,
harder-to-hand-craft patterns instead.

## 4. Scope Note

This report evaluates rules as a standalone layer. It does **not**
define risk levels, a final ALLOW/REVIEW/BLOCK decision, or blend rule
output with a model score — that combination logic belongs to Phase 6.
`src/rules/engine.py` currently only returns which rules fired; nothing
downstream of that has been built yet.

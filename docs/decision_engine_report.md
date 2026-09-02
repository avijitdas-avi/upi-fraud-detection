# Combined Decision Engine — Phase 6 Report

**Combines:** Rule engine (`src/rules/`, Phase 4) + primary ML model
(`models/gradient_boosting_model.joblib`, Phase 5)
**Evaluated on:** The same held-out time-based test split used in Phase 5
(10,000 transactions, 415 fraud — never seen during model training)
**Output:** `data/processed/decision_engine_results.csv`, in the exact
schema `docs/project_specification.md` (Section 5) defines.

---

## 1. Combination Policy

The spec left the exact combination mechanics as a decision for this
phase (Section 6: "the exact combination logic will be finalized when
the rule engine and decision layer are implemented"). Here's what was
built, and why, in `src/models/decision_engine.py`:

1. **Hard rules override everything.** If `BLOCKLIST` triggers, the
   transaction is forced to CRITICAL / BLOCK regardless of the ML
   score — a known-blocked party is a fact, not a probability, so no
   model score should be able to talk it down. (No blocklist data
   exists yet, so this path is currently inert — see Phase 4's report.)
2. **Otherwise, the ML probability sets the base risk level**, using
   the exact thresholds from Section 6 (LOW 0–30%, MEDIUM 30–60%,
   HIGH 60–85%, CRITICAL 85–100%).
3. **Two or more independent triggered rules escalate the risk level
   by one tier.** A *single* triggered rule does not escalate on its
   own. This threshold wasn't arbitrary — Phase 4's evaluation showed
   individual rules like `ODD_HOUR` (24% precision) and
   `NEW_DEVICE_AND_LOCATION` (15% precision) are noisy alone. Multiple
   independent rules agreeing is meaningfully stronger evidence than
   any one of them individually.
4. **Rules never de-escalate.** Their absence doesn't lower an
   otherwise-high ML score — the model may correctly catch fraud
   patterns no rule was written for, which is the entire reason both
   layers exist together rather than picking one.

Risk level maps to a final decision as the spec's Section 6 table
describes: LOW/MEDIUM → ALLOW, HIGH → REVIEW, CRITICAL → BLOCK.

## 2. Explanation Generation (Without SHAP)

Phase 5 flagged SHAP as unavailable in this sandbox (no internet
access to install it) and unresolved. This phase still needed to
produce the spec's `explanation` field, so it does so heuristically:
for each transaction, it looks at that transaction's own feature
values (amount z-score, velocity, receiver/device/location novelty,
hour deviation) and describes whichever are most unusual in plain
language, then appends which rules triggered. This is **not** a true
SHAP attribution — it doesn't tell you how much each feature actually
moved the model's internal decision, only which raw signals look
unusual for this transaction. Installing `shap` and replacing this
heuristic remains a real to-do, noted here again rather than presented
as solved.

Example explanation strings actually produced on test data:

> "Key factors: amount is 3.1x the sender's typical amount; first
> transaction to this receiver. Rules triggered:
> NEW_RECEIVER_HIGH_VALUE. Model fraud probability: 91.2%."

> "No significant risk factors identified (fraud probability 0.8%)."

## 3. Results

| Risk Level | Count | Fraud Rate |
|---|---|---|
| LOW | 9,548 | 0.2% |
| MEDIUM | 35 | 17.1% |
| HIGH | 28 | 32.1% |
| CRITICAL | 389 | 99.0% |

The risk levels are doing exactly what they're supposed to — fraud
rate climbs sharply and monotonically from LOW to CRITICAL, and the
CRITICAL tier is almost entirely real fraud (99.0%).

| Decision | Count |
|---|---|
| ALLOW | 9,583 |
| REVIEW | 28 |
| BLOCK | 389 |

### Combined performance (REVIEW + BLOCK treated as "flagged")

| | Value |
|---|---|
| Flagged | 417 / 10,000 (4.2%) |
| True positives | 394 |
| False positives | 23 |
| False negatives (missed) | 21 |
| **Precision** | **94.5%** |
| **Recall** | **94.9%** |

### BLOCK-only tier (highest confidence)

389 transactions were BLOCKed; **385 of them were actually fraud —
99.0% precision.** This is the tier a real system could act on
automatically with very low risk of blocking a legitimate payment. The
28 REVIEW transactions are the genuinely ambiguous middle ground —
worth a human look rather than an automatic decision either way.

## 4. Comparing All Three Layers

| Layer | Precision | Recall |
|---|---|---|
| Rules only (Phase 4)* | 32.1% | 77.0% |
| ML only (Phase 5, 0.5 threshold) | 93.4% | 95.9% |
| **Combined (Phase 6)** | **94.5%** | 94.9% |

*Rules-only was evaluated on the *full* dataset in Phase 4 (including
transactions the model later trained on), while ML-only and Combined
are evaluated strictly on the held-out test split — so this row isn't
perfectly apples-to-apples, but it's directionally honest: rules alone
are far noisier than either ML-based approach.

**What combining actually added, concretely:** the combined engine's
risk thresholds (HIGH starts at 60% probability) are stricter than the
flat 0.5 cutoff Phase 5 used to flag things, which on its own would
have *reduced* recall. Rule escalation compensated for that almost
exactly — 417 flagged here vs. 426 in Phase 5's ML-only flagging, and
394 true positives here vs. 398 there — while precision improved
(94.5% vs 93.4%). In other words, the escalation logic is doing real
work, not just sitting there unused.

## 5. What's Still Missed

21 of 415 fraud transactions (5.1%) were still allowed through:

| Fraud type | Missed |
|---|---|
| `velocity_fraud` | 17 |
| `odd_hour_fraud` | 3 |
| `micro_transaction_probing` | 1 |

This matches Phase 5's finding almost exactly (17 of the same misses
are `velocity_fraud`) — these are largely the *first* transaction(s)
in a burst, before enough history exists in the trailing-hour window
to look unusual (explained in depth in Phase 4's report, Section 3).
Catching these earlier is a real limitation of scoring transactions
independently rather than watching for emerging patterns across a
live stream — which is exactly what the real-time streaming phases
(Kafka/Redis, Phase 8–9) are for.

## 6. Scope Note

This phase produces the final per-transaction decision structure the
spec defines, evaluated in batch against historical held-out data. It
does **not** yet serve this over an API (Phase 7), consume a live
transaction stream (Phase 8), or maintain fast-access behavioral state
for real-time feature computation (Phase 9) — those remain untouched.

# Exploratory Data Analysis & Behavioral Features — Phase 3 Report

**Input:** `data/raw/synthetic_transactions.csv` (50,000 transactions, 4.00% fraud)
**Output:** `data/processed/behavioral_features.csv` (same 50,000 rows + 16 new behavioral feature columns)

This report summarizes what was found in the raw simulated dataset and
how the behavioral features derived from it separate fraud from
legitimate activity. All features were computed causally — each row's
features are based only on that sender's transactions **before** it in
time, matching how the real-time system will have to compute them
later (no access to the future, no access to hindsight labels).

---

## 1. Raw Data Overview

- 50,000 transactions across 1,250 simulated senders and 833 receivers
- 4.00% fraud rate (2,000 transactions), spread across 8 fraud types
  (see `docs/project_specification.md`, Section 3)
- No missing values in any raw column
- `transaction_status`: fraud transactions fail/pend slightly more often
  than legitimate ones (11.65% vs 5.97% non-SUCCESS), consistent with
  fraud attempts sometimes being blocked or erroring out downstream

## 2. Amount Behavior

| | Legitimate | Fraudulent |
|---|---|---|
| Mean amount | ₹1,039.76 | ₹2,140.47 |
| Median amount | ₹642.56 | ₹802.02 |
| Max amount | ₹37,069.51 | ₹68,584.09 |

Fraudulent transactions run higher on average, but the **median** gap
is much smaller than the mean gap — a reminder that a few large
outliers (mule-account and high-value-anomaly patterns) pull the mean
up, while many fraud transactions (e.g. micro-probing) are actually
small. Raw amount alone is a weak signal; amount **relative to the
sender's own history** is much stronger (see Section 4).

## 3. Time-of-Day Pattern

Fraud rate by hour of day peaks sharply between midnight and 6am
(16–28% fraud rate in that window) and drops to near-baseline
(under 5%) during normal daytime hours. This directly reflects the
`account_takeover` and `odd_hour_fraud` simulation patterns, which
deliberately place transactions at atypical hours.

## 4. Behavioral Features (derived, causal)

16 features were computed per transaction, using only the sender's
prior history at that point in time:

| Feature | What it captures |
|---|---|
| `sender_prior_txn_count` | How much history exists for this sender so far |
| `sender_avg_amount_prior` / `sender_std_amount_prior` | Sender's historical spending baseline |
| `amount_zscore_vs_sender` | How unusual this amount is vs. the sender's own pattern |
| `amount_ratio_vs_sender_avg` | Simpler multiplicative version of the same idea |
| `seconds_since_last_txn` | Time gap since the sender's last transaction |
| `sender_txn_count_last_1h` / `_last_24h` | Velocity — transaction bursts |
| `device_seen_count_prior` / `is_new_device_derived` | Device novelty, derived from history |
| `location_seen_count_prior` / `is_new_location_derived` | Location novelty, derived from history |
| `receiver_seen_count_prior` / `is_new_receiver_derived` | Receiver novelty, derived from history |
| `sender_typical_hour_prior` / `hour_deviation_from_typical` | How far this transaction's hour is from the sender's usual pattern |

**Coverage:** All features are populated for ≥95% of rows. The small
gap (~2.5–5%) is expected and correct — it's each sender's *first*
transaction, where there is no prior history to compute a mean, std,
or time gap from. This is left as a true missing value (not
zero-filled), so `sender_prior_txn_count == 0` can serve as its own
explicit "no history yet" signal for the model.

### Mean feature values, fraud vs. legitimate

| Feature | Legitimate | Fraudulent |
|---|---|---|
| `amount_zscore_vs_sender` | ~0.00 | **5.66** |
| `amount_ratio_vs_sender_avg` | 1.00× | **3.06×** |
| `sender_txn_count_last_1h` | 0.06 | **2.36** |
| `sender_txn_count_last_24h` | 0.44 | **2.81** |
| `seconds_since_last_txn` | 194,012s (~54h) | **74,515s (~21h)** |
| `is_new_device_derived` | 2.6% | **11.2%** |
| `is_new_location_derived` | 2.6% | **11.1%** |
| `is_new_receiver_derived` | 26.5% | **77.7%** |
| `hour_deviation_from_typical` | 2.38h | **5.46h** |

Every behavioral feature moves in the expected direction, several
sharply — `amount_zscore_vs_sender`, `sender_txn_count_last_1h`, and
`is_new_receiver_derived` show the largest separation between classes
and are likely to be the strongest individual predictors once
modeling starts (Phase 5).

### Derived novelty vs. simulator ground-truth labels

The raw dataset already contains `is_new_device`/`is_new_receiver`
columns from the simulator itself. As a sanity check, the
independently *derived* versions were compared against those labels:

- `is_new_device_derived` matches the simulator's `is_new_device` **97.5%** of the time
- `is_new_receiver_derived` matches the simulator's `is_new_receiver` only **72.0%** of the time

This gap is expected, not a bug: the simulator's `is_new_receiver`
label includes some intentional randomness (a sender may transact with
a previously-seen receiver but still get flagged `is_new_receiver` in
the raw data at generation time). The derived feature is stricter and
purely history-based, which is what a real production system would
actually have access to — so `is_new_receiver_derived` is the more
trustworthy feature going forward, and the raw label should be treated
as simulator metadata rather than a feature.

## 5. Implications for Phase 5 (Modeling)

- Amount-relative-to-history and short-window velocity look like the
  strongest candidate features based on class separation
- `sender_prior_txn_count` should probably be kept as a feature in its
  own right (or used to gate confidence in the other features), since
  early transactions for a sender have systematically missing history
- The raw `is_new_device` / `is_new_receiver` columns from the
  simulator should likely be **excluded** from the model's feature set
  in favor of the derived versions, to keep the feature set realistic
  and reproducible against live data later

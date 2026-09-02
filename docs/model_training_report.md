# Model Training — Phase 5 Report

**Input:** `data/processed/behavioral_features.csv` (50,000 transactions, 4.00% fraud)
**Split:** Time-based — earliest 80% of transactions (by timestamp) used
for training, most recent 20% held out for testing. This is deliberately
**not** a random split (see Section 1).
**Models trained:** Logistic Regression (baseline), Gradient-Boosted
Trees (primary), Autoencoder (secondary anomaly signal)

---

## 0. A Note on This Sandbox's Constraints

This development environment has **no internet access**, so `xgboost`,
`lightgbm`, `shap`, and any deep learning framework could not be
installed here. Rather than either faking results or silently
substituting something without saying so:

- The **primary model** was trained with scikit-learn's
  `HistGradientBoostingClassifier` — genuinely the same family of
  algorithm as XGBoost (histogram-based gradient-boosted trees), not
  a simplification of it. `src/models/train_gradient_boosting.py`.
- The **actual XGBoost script**, matching the spec exactly, is written
  and ready at `src/models/train_xgboost.py` — it uses the identical
  feature pipeline and should produce very close results, but it has
  **not been executed or verified** in this sandbox. Run it yourself
  once `pip install -r requirements.txt` succeeds in a normal
  environment, and treat its output as the source of truth for the
  literal spec'd model.
- **Explainability** used scikit-learn's permutation importance
  instead of SHAP — a real, legitimate technique, but a *global*
  (whole-dataset) measure rather than SHAP's *per-transaction* one.
  Installing `shap` is a real to-do before Phase 6/7 build the
  per-transaction `explanation` field the spec calls for.
- The **autoencoder** was built with `MLPRegressor` (trained to
  reconstruct its own input through a bottleneck layer) rather than a
  Keras/PyTorch network, since no deep learning framework was
  installable here.

Every number in this report was actually computed and verified in
this sandbox except where explicitly marked otherwise.

## 1. Why a Time-Based Split, Not a Random One

Most similar student projects split data randomly (e.g.
`train_test_split(..., random_state=42)`). That's a real methodological
issue for fraud detection: a random split lets the model train on
transactions from the *same time period* it's later "tested" on,
which isn't how the model will actually be used — in production it
only ever sees the past when predicting the future. A time-based
split (earliest 80% train, most recent 20% test) avoids that leakage
and gives a more honest estimate of real-world performance. It's also
a stricter test — the model can't lean on coincidental patterns from
the same short time window appearing in both sets.

## 2. Feature Set

16 behavioral features from Phase 3, plus `amount`, `hour_of_day`,
`day_of_week`, and one-hot encoded `transaction_type` — 21 features
total. Excluded on purpose: identifiers, free-text fields (device ID,
IP, bank names — high-cardinality, not generalizable), the
simulator's own `is_new_device`/`is_new_receiver` ground-truth labels
(a real system wouldn't have these — the *derived* Phase 3 versions
are used instead), `transaction_status` (risk of leaking the outcome),
and `fraud_type` (would leak the label directly). Full reasoning is in
`src/models/feature_prep.py`.

Missing values (a sender's first-ever transaction, with no prior
history) were imputed with neutral values rather than dropped, since a
real system has to score first transactions too.

## 3. Results

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|
| Logistic Regression (baseline) | 49.2% | 97.4% | 0.654 | 0.995 | 0.926 |
| **Gradient Boosting (primary)** | **93.4%** | **95.9%** | **0.947** | **0.999** | **0.988** |
| Autoencoder (secondary) | 67.5% | 64.6% | 0.660 | 0.963 | 0.739 |

(Recall/precision at each model's chosen operating threshold — see
Section 4 for how the autoencoder's threshold was set. ROC-AUC/PR-AUC
are threshold-independent and directly comparable across all three.)

**The primary model clearly earns its place.** It beats the baseline
on every metric, most dramatically on precision (93.4% vs 49.2% — the
baseline flags roughly one false alarm for every real fraud catch,
while the primary model flags roughly one false alarm for every 14
real catches). It also misses fewer fraud cases outright: 17 missed
vs. the baseline's 11 missed sounds close, but the baseline gets there
by flagging 821 transactions total (nearly double the primary model's
426) — it's not more careful, it's just casting a much wider net.

## 4. On the Autoencoder's Threshold (and an Honest Limitation)

A classifier's `predict_proba` output is naturally centered so 0.5 is
a meaningful cutoff. A min-max normalized reconstruction error has no
such natural midpoint — thresholding it at a flat 0.5 flagged only 3
transactions out of 10,000 in the test set, which would have made the
autoencoder look almost useless. Instead, it's thresholded at the
**training set's own fraud rate** (never the test labels, to avoid
leakage): if ~4% of transactions are normally fraudulent, the top ~4%
most-anomalous-by-reconstruction-error transactions are flagged. That
produces the 67.5%/64.6% numbers above — a real, if modest, standalone
signal.

**Where the autoencoder was expected to add the most value — catching
fraud the primary model misses — it currently doesn't, on this
dataset.** Checking directly: of the 17 fraud transactions the primary
model missed (mostly `velocity_fraud`, a few `odd_hour_fraud` and
`micro_transaction_probing`), the autoencoder caught **zero** of them.

**This isn't necessarily a flaw in the autoencoder — it's a limitation
of what this specific evaluation can measure.** All the fraud in this
dataset was deliberately simulated as one of the 8 known fraud types
from `docs/project_specification.md` (Section 3), which the
supervised primary model was directly trained to recognize. The
autoencoder's actual value proposition — catching fraud that doesn't
match *any* known pattern, because it never saw fraud labels at all —
can't be fairly tested against a dataset where every fraud case *does*
match a known, labeled pattern. A more honest test would need fraud
types the model was never trained or simulated to expect, which is out
of scope for this phase. For now, the autoencoder is included as a
secondary signal with real, verified — if unremarkable —
standalone performance, and its stated purpose (catching *novel*
fraud) remains unverified rather than proven, and that gap is being
stated plainly rather than glossed over.

## 5. Feature Importance (Permutation Importance, Primary Model)

| Rank | Feature | Importance (drop in PR-AUC when shuffled) |
|---|---|---|
| 1 | `amount_ratio_vs_sender_avg` | 0.131 |
| 2 | `receiver_seen_count_prior` | 0.093 |
| 3 | `seconds_since_last_txn` | 0.089 |
| 4 | `device_seen_count_prior` | 0.013 |
| 5 | `amount` | 0.012 |
| 6 | `hour_of_day` | 0.010 |
| 7 | `sender_txn_count_last_1h` | 0.009 |
| 8 | `hour_deviation_from_typical` | 0.008 |

The top 3 features alone account for the large majority of the
model's predictive power — how unusual the amount is relative to the
sender's own history, whether this is a new receiver, and how long
it's been since the sender's last transaction. This lines up with what
Phase 3's EDA predicted (`docs/eda_report.md`), and it's a reassuring
sign that the model is leaning on genuinely meaningful behavioral
signals rather than something spurious.

Note this is *global* importance (across the whole test set), not
*per-transaction* — see Section 0 for why SHAP (per-transaction) is
still a to-do.

## 6. What's Saved

| File | Contents |
|---|---|
| `models/baseline_logreg.joblib` | Trained Logistic Regression model |
| `models/baseline_scaler.joblib` | Its feature scaler + feature name list |
| `models/gradient_boosting_model.joblib` | Trained primary model + feature name list |
| `models/autoencoder_model.joblib` | Trained autoencoder + scaler + error normalization bounds |
| `data/processed/model_comparison.csv` | The comparison table above, as data |
| `data/processed/feature_importance.csv` | Full permutation importance ranking |

## 7. Scope Note

This phase trains and evaluates models **in isolation** — same
boundary as Phase 4's rule engine. No risk levels, no
ALLOW/REVIEW/BLOCK decision, and no combination of the model score
with the rule engine's output — that's Phase 6. The two systems
(rules from Phase 4, models from this phase) currently know nothing
about each other.

# Project Specification: Real-Time UPI Fraud Detection System

**Status:** Draft — Phase 1
**Last updated:** Phase 1 (project scaffolding)

---

## 1. Project Objective

Build a system that detects potentially fraudulent UPI (Unified Payments
Interface) transactions in real time by combining:

- **Behavioral features** — patterns derived from a user's historical and
  in-session transaction behavior (e.g., typical transaction amount,
  frequency, device, location).
- **Machine learning** — a trained classification model that estimates
  the probability that a given transaction is fraudulent.
- **Rule-based detection** — explicit, human-defined rules that catch
  known fraud patterns and edge cases the ML model may miss or that
  require deterministic, explainable handling.
- **Real-time streaming** — an event-driven pipeline capable of scoring
  transactions as they occur, rather than in offline batches.

The end goal is a modular pipeline that ingests a transaction event,
enriches it with behavioral context, scores it using both ML and rules,
and returns a real-time fraud risk assessment.

## 2. Problem Definition

UPI is a real-time payment system used for high-volume, low-latency
transactions between individuals and merchants in India. Because
transactions settle instantly and are difficult to reverse, fraud
detection must happen **before or at the moment of transaction
processing**, not after the fact.

The core problem this system addresses:

> Given a stream of UPI transactions, identify — within real-time
> latency constraints — which transactions are likely fraudulent, and
> assign each a risk level that downstream systems (or a human
> reviewer) can act on.

This is fundamentally a challenge of:
- **Class imbalance** — genuine fraud is rare relative to legitimate
  transaction volume.
- **Behavioral drift** — normal behavior varies by user and changes
  over time.
- **Latency constraints** — scoring must be fast enough not to disrupt
  the user payment experience.
- **Explainability** — flagged transactions need a defensible reason
  (useful for both trust and for combining ML with rules).

Since access to real UPI transaction data is not available, this
project will **simulate** realistic transaction data and fraud patterns
for development, training, and evaluation purposes (data generation
itself is a later phase, not part of Phase 1).

## 3. Types of UPI Fraud We Intend to Simulate

The system is intended to detect (via simulated data in a later phase)
the following categories of fraud, which are broadly representative of
real-world UPI fraud patterns:

1. **Account takeover fraud** — transactions initiated from a
   compromised account, often showing a sudden change in device,
   location, or behavior compared to the account's history.
2. **Social engineering / phishing-induced fraud** — victim is tricked
   into authorizing a payment (e.g., fake QR codes, fake customer care,
   "collect request" scams). Often shows as a legitimate-looking,
   user-authorized but atypical high-value transaction.
3. **Mule account transactions** — funds routed through intermediary
   accounts used to launder or quickly move stolen money, often
   characterized by rapid in-and-out fund movement.
4. **Velocity-based fraud** — an unusually high number of transactions
   in a short time window (e.g., testing stolen credentials or rapidly
   draining an account).
5. **Micro-transaction probing** — a series of small-value transactions
   used to test whether a stolen credential/account is active before
   attempting a larger fraudulent transaction.
6. **Unusual geo-location / device fraud** — a transaction occurring
   from a device or location inconsistent with the user's established
   pattern (e.g., new device + new city + odd hour).
7. **High-value anomaly fraud** — a transaction amount that is a
   significant outlier relative to the user's historical transaction
   amounts.
8. **Odd-hour transaction fraud** — transactions occurring at times
   atypical for the user (e.g., late night) combined with other risk
   signals.

These categories will guide both the synthetic data generation logic
(Phase 2+) and the rule design (Phase 4+). Not all categories may be
fully separable from simulated data alone; some will be approximated.

## 4. Transaction Fields

The following fields define the planned schema for a single UPI
transaction event. This schema will be used consistently across data
generation, feature engineering, the ML model, and the API.

| Field                  | Type              | Description                                                         |
|-------------------------|-------------------|-----------------------------------------------------------------------|
| `transaction_id`         | string (UUID)     | Unique identifier for the transaction                                |
| `timestamp`               | datetime          | Date and time the transaction occurred                                |
| `sender_upi_id`             | string            | Sender's UPI ID / virtual payment address                            |
| `receiver_upi_id`            | string            | Receiver's UPI ID / virtual payment address                          |
| `sender_account_id`            | string            | Internal identifier for the sender's account                        |
| `receiver_account_id`            | string            | Internal identifier for the receiver's account                      |
| `amount`                          | float             | Transaction amount (INR)                                             |
| `transaction_type`                  | categorical       | e.g., P2P (person-to-person), P2M (person-to-merchant), collect request |
| `device_id`                           | string            | Identifier for the device used to initiate the transaction            |
| `ip_address`                            | string            | IP address at the time of transaction (if available)                 |
| `location`                                | string / geo      | City/region or coordinates of the transaction                        |
| `sender_bank`                               | string            | Sender's bank name / IFSC-linked bank                                |
| `receiver_bank`                               | string            | Receiver's bank name / IFSC-linked bank                              |
| `hour_of_day`                                   | int               | Hour extracted from timestamp (0–23), for behavioral features        |
| `day_of_week`                                     | int               | Day of week extracted from timestamp                                  |
| `is_new_device`                                     | boolean           | Whether the device is new/unrecognized for the sender                |
| `is_new_receiver`                                     | boolean           | Whether this is the first transaction to this receiver               |
| `transaction_status`                                    | categorical       | SUCCESS / FAILED / PENDING                                            |
| `label_is_fraud`                                          | boolean (target)  | Ground-truth fraud label — present only in training/simulated data   |

Additional derived/behavioral fields (e.g., rolling transaction counts,
average amount over last N days) belong to the **feature engineering**
layer (`src/features/`), not the raw transaction schema, and will be
defined when that phase is implemented.

## 5. Expected Model Output

For each scored transaction, the system is expected to output a
structured result containing:

| Field                | Type      | Description                                                       |
|-----------------------|-----------|---------------------------------------------------------------------|
| `transaction_id`        | string    | The transaction being scored                                       |
| `fraud_probability`       | float (0–1) | ML model's predicted probability that the transaction is fraudulent |
| `risk_level`                | categorical | Human-readable risk category derived from probability + rules (see Section 6) |
| `triggered_rules`             | list[string] | Names/IDs of any rule-based checks the transaction triggered      |
| `final_decision`                 | categorical | e.g., ALLOW / REVIEW / BLOCK — combined outcome of ML + rules      |
| `explanation`                       | string      | Short human-readable justification (top contributing factors)     |
| `scored_at`                           | datetime    | Timestamp when the scoring was performed                          |

This output format is designed so that both the ML component and the
rule engine contribute to a single, explainable decision, rather than
the ML score being used in isolation.

## 6. Risk Levels

Transactions will be bucketed into the following risk levels, based on
a combination of `fraud_probability` and any triggered rules:

| Risk Level    | Typical Probability Range | Meaning                                                        | Suggested Action        |
|-----------------|-----------------------------|--------------------------------------------------------------------|----------------------------|
| **LOW**           | 0.00 – 0.30                  | Transaction behaves consistently with normal patterns              | Allow                      |
| **MEDIUM**           | 0.30 – 0.60                  | Some unusual signals present, but not conclusively fraudulent      | Allow, but log for monitoring |
| **HIGH**               | 0.60 – 0.85                  | Strong indicators of fraud from ML and/or rules                    | Flag for manual review     |
| **CRITICAL**              | 0.85 – 1.00                  | Very high confidence of fraud, or a hard rule was triggered         | Block / hold transaction   |

Note: A triggered hard rule (e.g., a known-blocklisted receiver) may
escalate a transaction to CRITICAL regardless of the raw ML
probability — the exact combination logic will be finalized when the
rule engine and decision layer are implemented.

## 7. ML Approach

Planned (not yet implemented):

- **Problem framing:** Binary classification — `is_fraud` vs.
  `not_fraud` — producing a probability score rather than a hard label,
  so downstream logic can apply thresholds/risk levels.
- **Models:** Start with a baseline (e.g., Logistic Regression) for
  interpretability and a sanity-check baseline, then move to
  **XGBoost** as the primary model, given its strong performance on
  structured/tabular data with imbalanced classes.
- **Class imbalance handling:** Techniques such as class weighting,
  SMOTE/oversampling, or threshold tuning will be evaluated, since
  fraud is expected to be rare in the simulated data (mirroring
  real-world UPI fraud rates).
- **Feature set:** Behavioral features derived from transaction history
  (e.g., rolling averages, velocity counts, device/location novelty)
  combined with raw transaction attributes.
- **Evaluation metrics:** Precision, recall, F1-score, ROC-AUC, and
  precision-recall AUC will be prioritized over raw accuracy, given
  class imbalance. Recall on fraud cases and false-positive rate on
  legitimate transactions are both important given the user-experience
  cost of false positives.
- **Explainability:** Feature importance / SHAP values (or similar)
  are planned to support the `explanation` field in the model output.

## 8. Rule-Based Approach

Planned (not yet implemented):

- Rules act as a **complementary, deterministic layer** alongside the
  ML model — useful for known fraud patterns, regulatory/compliance
  requirements, and cases where explainability or guaranteed action is
  required regardless of model confidence.
- Rules will live in `src/rules/` as independently testable, composable
  checks (e.g., one rule per fraud pattern from Section 3), rather than
  a single monolithic rule function.
- Example candidate rules (subject to refinement in a later phase):
  - Transaction amount exceeds N standard deviations from the sender's
    historical average.
  - More than N transactions within a short time window (velocity
    check).
  - First-time transaction to a new receiver combined with a
    high-value amount.
  - Transaction from a new/unrecognized device and a new location
    simultaneously.
  - Transaction occurring at an atypical hour for that sender.
  - Sender or receiver present on a blocklist.
- Each rule will output a boolean trigger plus a rule identifier, which
  feeds into `triggered_rules` and the final decision logic (Section 5
  and 6).

## 9. Planned Real-Time Architecture

At a high level, the intended real-time pipeline (to be built out in
later phases) is:

```
 ┌────────────┐     ┌────────────┐     ┌────────────────────┐
 │ Transaction │────▶│   Kafka    │────▶│  Stream Consumer /   │
 │   Source    │     │  (topic:   │     │  Scoring Service     │
 │ (simulated) │     │ transactions)     │  (feature build +    │
 └────────────┘     └────────────┘     │   ML + rules engine) │
                                          └─────────┬───────────┘
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              ▼                     ▼                     ▼
                        ┌───────────┐        ┌────────────┐        ┌────────────┐
                        │   Redis    │        │ PostgreSQL │        │  FastAPI    │
                        │ (behavioral│        │ (persisted │        │  (serving   │
                        │  state /   │        │ transactions│        │  scores /   │
                        │  fast      │        │ + decisions)│        │  results)   │
                        │  lookups)  │        └────────────┘        └──────┬──────┘
                        └───────────┘                                     │
                                                                            ▼
                                                                     ┌────────────┐
                                                                     │  Streamlit  │
                                                                     │  Dashboard  │
                                                                     └────────────┘
```

Intended role of each component:

- **Apache Kafka** — ingests the real-time stream of transaction
  events; decouples transaction producers from the scoring consumer(s).
- **Redis** — stores fast-access behavioral state per user (e.g.,
  rolling counts, recent transaction stats) so features can be computed
  with low latency without querying the full historical dataset per
  transaction.
- **Scoring service** — consumes transactions from Kafka, builds
  behavioral features (using Redis + historical data), runs the ML
  model and rule engine, and produces a decision.
- **PostgreSQL** — durable storage of transactions, computed features
  (as needed), and fraud decisions for audit, retraining, and
  reporting.
- **FastAPI** — exposes endpoints to query transaction results, submit
  transactions for scoring (e.g., for testing), and serve data to the
  dashboard.
- **Streamlit** — a dashboard for visualizing flagged transactions,
  risk distributions, and system/model performance.
- **Docker** — containerizes each component for consistent local
  development and deployment.

This architecture is a planning reference only — none of these
components are installed, configured, or connected in Phase 1.

## 10. Project Milestones

| Phase | Scope                                                                                   | Status        |
|-------|-------------------------------------------------------------------------------------------|----------------|
| **1** | Project structure and documentation (this document)                                        | ✅ In progress  |
| **2** | Synthetic/simulated UPI transaction dataset generation                                       | Not started    |
| **3** | Exploratory data analysis and behavioral feature engineering                                    | Not started    |
| **4** | Rule-based detection engine (`src/rules/`)                                                        | Not started    |
| **5** | ML model training and evaluation (`src/models/`) — baseline model, then XGBoost                    | Not started    |
| **6** | Combined ML + rules decision layer and risk-level logic                                               | Not started    |
| **7** | FastAPI service exposing scoring endpoints                                                              | Not started    |
| **8** | Real-time streaming integration with Apache Kafka                                                         | Not started    |
| **9** | Redis integration for low-latency behavioral state                                                          | Not started    |
| **10**| PostgreSQL integration for persistence                                                                        | Not started    |
| **11**| Streamlit dashboard for monitoring and review                                                                    | Not started    |
| **12**| Dockerization of all services for local/deployed orchestration                                                     | Not started    |
| **13**| End-to-end testing, tuning, and documentation polish                                                                  | Not started    |

Each phase will be implemented only when explicitly requested, and this
document will be updated to reflect progress and any design changes
made along the way.

# UPI Fraud Detection System

A real-time fraud detection system for UPI (Unified Payments Interface)
transactions, combining behavioral features, machine learning, and
rule-based detection over a streaming architecture.

> **Status:** Phase 1 — project scaffolding and documentation only.
> No model, dataset, or infrastructure has been built yet.

## Planned Technology Stack

| Layer                | Technology              |
|-----------------------|--------------------------|
| Data processing       | Python, Pandas           |
| Machine learning       | Scikit-learn, XGBoost    |
| Streaming              | Apache Kafka             |
| Low-latency state/cache| Redis                   |
| API                    | FastAPI                 |
| Storage                | PostgreSQL               |
| Dashboard               | Streamlit               |
| Containerization         | Docker                 |

See [`docs/project_specification.md`](docs/project_specification.md) for
the full project specification, including problem definition, fraud
types, transaction schema, model output format, risk levels, and
architecture.

## Project Structure

```
upi-fraud-detection/
├── docs/                  # Project documentation and specifications
├── data/
│   ├── raw/               # Raw / source transaction data (unmodified)
│   └── processed/         # Cleaned, feature-engineered datasets
├── notebooks/              # Exploratory analysis and prototyping
├── src/
│   ├── data/               # Data loading, validation, generation utilities
│   ├── features/            # Behavioral feature engineering
│   ├── models/               # ML model training, evaluation, inference
│   ├── rules/                 # Rule-based fraud detection logic
│   └── api/                    # FastAPI service layer
├── tests/                  # Unit and integration tests
├── models/                 # Serialized/trained model artifacts
├── requirements.txt        # Python dependencies (all phases)
└── README.md
```

## Development Phases

This project is being built incrementally, phase by phase. Each phase is
scoped and completed before the next begins. See the **Project
Milestones** section of the specification document for the full phase
breakdown.

**Phase 1 (current):** Project structure and documentation only.

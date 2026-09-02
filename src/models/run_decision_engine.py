"""
Run the combined decision engine on the held-out test set and compare
its performance against rules-only (Phase 4) and ML-only (Phase 5),
to see what combining them actually adds.

Deliberately scored only on the same time-based test split used in
Phase 5 (not the full dataset) — scoring on data the model trained on
would overstate performance and wouldn't be a fair comparison to the
Phase 4/5 numbers already reported.

Usage (run as a module from the project root):
    python -m src.models.run_decision_engine
"""

from __future__ import annotations

import pandas as pd

from src.models.decision_engine import DecisionEngine
from src.models.feature_prep import time_based_split

DATA_PATH = "data/processed/behavioral_features.csv"
OUTPUT_PATH = "data/processed/decision_engine_results.csv"


def run():
    df = pd.read_csv(DATA_PATH)
    df["label_is_fraud"] = df["label_is_fraud"].astype(bool)
    _, test_df = time_based_split(df)

    engine = DecisionEngine()
    scored = engine.score_dataframe(test_df)

    # Bring the ground-truth label and fraud_type along for evaluation only
    # (never used as a model input — see src/models/feature_prep.py)
    scored["label_is_fraud"] = test_df["label_is_fraud"].values
    scored["fraud_type"] = test_df["fraud_type"].values

    scored.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(scored)} scored transactions to {OUTPUT_PATH}\n")
    print_evaluation(scored)


def print_evaluation(df: pd.DataFrame) -> None:
    total_fraud = int(df["label_is_fraud"].sum())
    total = len(df)

    print("=== Risk Level Distribution ===")
    print(df["risk_level"].value_counts().reindex(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).fillna(0).astype(int).to_string())
    print()

    print("=== Final Decision Distribution ===")
    print(df["final_decision"].value_counts().to_string())
    print()

    print("=== Fraud rate by risk level ===")
    print((df.groupby("risk_level")["label_is_fraud"].mean() * 100).reindex(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).round(1).to_string())
    print()

    # Treat REVIEW + BLOCK as "flagged" for a precision/recall comparison
    # against the Phase 4 (rules-only) and Phase 5 (ML-only) numbers.
    flagged = df["final_decision"].isin(["REVIEW", "BLOCK"])
    tp = int((flagged & df["label_is_fraud"]).sum())
    fp = int((flagged & ~df["label_is_fraud"]).sum())
    fn = total_fraud - tp
    precision = tp / flagged.sum() if flagged.sum() else 0.0
    recall = tp / total_fraud if total_fraud else 0.0

    print("=== Combined Decision Performance (REVIEW + BLOCK treated as 'flagged') ===")
    print(f"Flagged: {int(flagged.sum())} / {total} ({flagged.mean():.1%})")
    print(f"True positives:  {tp}")
    print(f"False positives: {fp}")
    print(f"False negatives (missed): {fn}")
    print(f"Precision: {precision:.1%}")
    print(f"Recall:    {recall:.1%}")
    print()

    print("=== BLOCK-only performance (highest-confidence tier) ===")
    blocked = df["final_decision"] == "BLOCK"
    block_tp = int((blocked & df["label_is_fraud"]).sum())
    block_precision = block_tp / blocked.sum() if blocked.sum() else 0.0
    print(f"Blocked: {int(blocked.sum())}, of which fraud: {block_tp} (precision={block_precision:.1%})")
    print()

    print("=== Missed fraud (ALLOW decision) by fraud type ===")
    missed = df.loc[df["label_is_fraud"] & (df["final_decision"] == "ALLOW")]
    print(f"Total missed: {len(missed)} / {total_fraud}")
    if len(missed):
        print(missed["fraud_type"].value_counts().to_string())


if __name__ == "__main__":
    run()

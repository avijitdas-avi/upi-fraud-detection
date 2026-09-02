"""
Train All Models & Compare
=============================

Runs the baseline, primary gradient-boosting model, and autoencoder,
evaluates all three on the same held-out (time-based) test set, and
prints/saves a comparison table.

Usage (run as a module from the project root):
    python -m src.models.train_all
"""

from __future__ import annotations

import pandas as pd

from src.models.explain import compute_permutation_importance
from src.models.train_autoencoder import train_autoencoder
from src.models.train_baseline import train_baseline
from src.models.train_gradient_boosting import train_gradient_boosting


def main():
    print("=" * 70)
    print("Training baseline (Logistic Regression)...")
    baseline_result, _, _ = train_baseline()

    print("Training primary model (Gradient Boosting, XGBoost-family)...")
    gb_result, _, gb_test_prepared, gb_model = train_gradient_boosting()

    print("Training autoencoder (anomaly detection, legit-only)...")
    ae_result, _, _, _ = train_autoencoder()

    print("Computing feature importance for the primary model...")
    importance_df = compute_permutation_importance(gb_model, gb_test_prepared.X, gb_test_prepared.y)
    importance_df.to_csv("data/processed/feature_importance.csv", index=False)

    comparison = pd.DataFrame([
        baseline_result.to_row(),
        gb_result.to_row(),
        ae_result.to_row(),
    ])
    comparison.to_csv("data/processed/model_comparison.csv", index=False)

    print("\n" + "=" * 70)
    print("MODEL COMPARISON (test set, time-based split)")
    print("=" * 70)
    print(comparison.to_string(index=False))

    print("\nTop 10 features by permutation importance:")
    print(importance_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

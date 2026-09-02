"""
Feature Importance (Explainability)
=======================================

The project specification calls for SHAP values to power the model
output's `explanation` field (Section 7). SHAP is not installed in
this sandbox (no internet access) — this module uses scikit-learn's
built-in **permutation importance** instead: a legitimate, real
model-agnostic explainability technique already available. It answers
a related but coarser question than SHAP does:

- **Permutation importance** (used here): "Across the whole test set,
  how much does shuffling this feature hurt the model's performance?"
  — a *global* measure of which features matter overall.
- **SHAP** (spec'd, not run here): "For *this one* transaction, how
  much did each feature push the prediction up or down?" — a *local*,
  per-prediction explanation, which is what the spec's `explanation`
  field really needs (Phase 6/7 will need per-transaction
  explanations, not just global ranking).

Global importance is still genuinely useful now — it tells us which
behavioral features the model actually leans on — but installing
`shap` and switching to it is a real to-do before Phase 6/7 build the
per-transaction `explanation` field for real.

Usage (run as a module from the project root):
    python -m src.models.explain
"""

from __future__ import annotations

import pandas as pd
from sklearn.inspection import permutation_importance

from src.models.feature_prep import prepare_features, time_based_split
from src.models.train_gradient_boosting import train_gradient_boosting


def compute_permutation_importance(model, X_test: pd.DataFrame, y_test: pd.Series, n_repeats: int = 10) -> pd.DataFrame:
    result = permutation_importance(
        model, X_test, y_test,
        n_repeats=n_repeats, random_state=42, scoring="average_precision",
    )
    importance_df = pd.DataFrame({
        "feature": X_test.columns,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False).reset_index(drop=True)
    return importance_df


if __name__ == "__main__":
    _, _, test_prepared, model = train_gradient_boosting()
    importance_df = compute_permutation_importance(model, test_prepared.X, test_prepared.y)

    print("Permutation importance (drop in PR-AUC when feature is shuffled):\n")
    print(importance_df.to_string(index=False))

    importance_df.to_csv("data/processed/feature_importance.csv", index=False)
    print("\nSaved to data/processed/feature_importance.csv")

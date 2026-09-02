"""
Primary Model — Gradient-Boosted Trees
==========================================

The project specification calls for XGBoost as the primary model.
This script trains with scikit-learn's `HistGradientBoostingClassifier`
instead — the same underlying technique (histogram-based gradient-
boosted decision trees) and the same algorithm family XGBoost belongs
to, chosen here purely because this development sandbox has no
internet access to install the `xgboost` package itself. See
`src/models/train_xgboost.py` for the actual XGBoost training script,
written against the identical feature pipeline, ready to run once
`pip install -r requirements.txt` has been run in a real environment
(e.g. locally, per the Phase 1 setup) — that script was not executed
here and its results are not yet verified.

Everything in this script — the features, the split, the imbalance
handling, the evaluation — is written to produce results that
transfer directly to the real XGBoost script; only the specific
library differs.

Usage (run as a module from the project root):
    python -m src.models.train_gradient_boosting
"""

from __future__ import annotations

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src.models.evaluation import evaluate_predictions
from src.models.feature_prep import prepare_features, time_based_split

DATA_PATH = "data/processed/behavioral_features.csv"
MODEL_PATH = "models/gradient_boosting_model.joblib"


def train_gradient_boosting():
    df = pd.read_csv(DATA_PATH)
    train_df, test_df = time_based_split(df)

    train_prepared = prepare_features(train_df)
    test_prepared = prepare_features(test_df)
    test_X = test_prepared.X.reindex(columns=train_prepared.feature_names, fill_value=0.0)

    # class_weight="balanced" handles the ~4% fraud imbalance without
    # needing to oversample/undersample the training data.
    model = HistGradientBoostingClassifier(
        max_iter=200,
        max_depth=6,
        learning_rate=0.08,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(train_prepared.X, train_prepared.y)

    y_proba = model.predict_proba(test_X)[:, 1]
    result = evaluate_predictions("Gradient Boosting (HistGB, XGBoost-family)", test_prepared.y.values, y_proba)

    joblib.dump({"model": model, "feature_names": train_prepared.feature_names}, MODEL_PATH)

    return result, y_proba, test_prepared, model


if __name__ == "__main__":
    result, _, _, _ = train_gradient_boosting()
    print(f"Saved model to {MODEL_PATH}\n")
    for k, v in result.to_row().items():
        print(f"  {k}: {v}")

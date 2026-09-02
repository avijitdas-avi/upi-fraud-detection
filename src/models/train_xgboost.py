"""
Primary Model — XGBoost (as specified in the project tech stack)
====================================================================

*** NOT EXECUTED IN THIS DEVELOPMENT SANDBOX — see note below. ***

This is the actual XGBoost training script matching what
`docs/project_specification.md` specifies as the primary model. It
uses the identical feature pipeline (`src/models/feature_prep.py`) and
evaluation logic (`src/models/evaluation.py`) as
`train_gradient_boosting.py`, so results from the two should be very
close — XGBoost and HistGradientBoostingClassifier are the same
family of algorithm.

Why this wasn't run here: the sandbox this project was developed in
has no internet access, so `pip install xgboost` could not complete.
`train_gradient_boosting.py` was trained and evaluated instead, using
scikit-learn's built-in equivalent, to produce real, verified numbers
without that dependency. This script is provided so you can run the
literal spec'd model once you have a normal Python environment with
`requirements.txt` installed (see Phase 1 setup) — at that point,
running this script and comparing its output to
`docs/model_training_report.md` is a good way to confirm both give
consistent results.

Usage (run as a module from the project root, after `pip install
xgboost`):
    python -m src.models.train_xgboost
"""

from __future__ import annotations

import joblib
import pandas as pd
import xgboost as xgb

from src.models.evaluation import evaluate_predictions
from src.models.feature_prep import prepare_features, time_based_split

DATA_PATH = "data/processed/behavioral_features.csv"
MODEL_PATH = "models/xgboost_model.joblib"


def train_xgboost():
    df = pd.read_csv(DATA_PATH)
    train_df, test_df = time_based_split(df)

    train_prepared = prepare_features(train_df)
    test_prepared = prepare_features(test_df)
    test_X = test_prepared.X.reindex(columns=train_prepared.feature_names, fill_value=0.0)

    # scale_pos_weight compensates for class imbalance (~4% fraud):
    # ratio of negative to positive examples in the training set.
    n_pos = train_prepared.y.sum()
    n_neg = len(train_prepared.y) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos else 1.0

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.08,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        use_label_encoder=False,
    )
    model.fit(train_prepared.X, train_prepared.y)

    y_proba = model.predict_proba(test_X)[:, 1]
    result = evaluate_predictions("XGBoost", test_prepared.y.values, y_proba)

    joblib.dump({"model": model, "feature_names": train_prepared.feature_names}, MODEL_PATH)

    return result, y_proba, test_prepared, model


if __name__ == "__main__":
    result, _, _, _ = train_xgboost()
    print(f"Saved model to {MODEL_PATH}\n")
    for k, v in result.to_row().items():
        print(f"  {k}: {v}")

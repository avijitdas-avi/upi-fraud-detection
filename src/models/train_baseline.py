"""
Baseline Model — Logistic Regression
=======================================

A simple, interpretable baseline. Its job is not to be the best model
— it's to give every other model a number it has to beat. If XGBoost /
HistGradientBoosting can't clearly outperform this, something in the
pipeline (features, split, evaluation) is more likely wrong than the
fancier model being genuinely no better.

Usage (run as a module from the project root):
    python -m src.models.train_baseline
"""

from __future__ import annotations

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.models.evaluation import evaluate_predictions
from src.models.feature_prep import prepare_features, time_based_split

DATA_PATH = "data/processed/behavioral_features.csv"
MODEL_PATH = "models/baseline_logreg.joblib"
SCALER_PATH = "models/baseline_scaler.joblib"


def train_baseline():
    df = pd.read_csv(DATA_PATH)
    train_df, test_df = time_based_split(df)

    train_prepared = prepare_features(train_df)
    test_prepared = prepare_features(test_df)

    # Align test columns to train columns (in case a rare category is
    # missing from one split after one-hot encoding)
    test_X = test_prepared.X.reindex(columns=train_prepared.feature_names, fill_value=0.0)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(train_prepared.X)
    X_test_scaled = scaler.transform(test_X)

    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_train_scaled, train_prepared.y)

    y_proba = model.predict_proba(X_test_scaled)[:, 1]
    result = evaluate_predictions("Logistic Regression (baseline)", test_prepared.y.values, y_proba)

    joblib.dump(model, MODEL_PATH)
    joblib.dump({"scaler": scaler, "feature_names": train_prepared.feature_names}, SCALER_PATH)

    return result, y_proba, test_prepared


if __name__ == "__main__":
    result, _, _ = train_baseline()
    print(f"Saved model to {MODEL_PATH}\n")
    for k, v in result.to_row().items():
        print(f"  {k}: {v}")

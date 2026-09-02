"""
Secondary Model — Shallow Autoencoder (Anomaly Detection)
==============================================================

An autoencoder is trained to reconstruct *only legitimate* transactions
— it never sees a labeled fraud example during training. The idea:
once it has learned what "normal" behavioral features look like, it
will reconstruct a normal transaction well (low error) and a fraud
transaction poorly (high error), because fraud looks different from
what it was trained on. That reconstruction error becomes a second,
independent fraud signal — one that isn't limited to the fraud
patterns we hand-simulated, unlike the supervised models
(baseline/XGBoost), which can only learn to recognize labels they were
shown.

Implementation note: this project's tech stack doesn't include a deep
learning framework (TensorFlow/PyTorch), and this sandbox has no
internet access to install one. This autoencoder is built instead with
scikit-learn's `MLPRegressor`, trained to reconstruct its own input
(output = input) through a bottleneck hidden layer smaller than the
input dimension — a genuine, if shallow, autoencoder, not a
simplification of the concept. If a full deep learning framework
becomes available later, this could be swapped for a Keras/PyTorch
autoencoder using the same train/evaluate structure without changing
anything else in the pipeline.

Usage (run as a module from the project root):
    python -m src.models.train_autoencoder
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from src.models.evaluation import evaluate_predictions
from src.models.feature_prep import prepare_features, time_based_split

DATA_PATH = "data/processed/behavioral_features.csv"
MODEL_PATH = "models/autoencoder_model.joblib"


def train_autoencoder():
    df = pd.read_csv(DATA_PATH)
    train_df, test_df = time_based_split(df)

    train_prepared = prepare_features(train_df)
    test_prepared = prepare_features(test_df)
    test_X = test_prepared.X.reindex(columns=train_prepared.feature_names, fill_value=0.0)

    # Train only on legitimate transactions from the training split —
    # the autoencoder must never see a fraud example during training,
    # or it would learn to reconstruct fraud well too, defeating the
    # point.
    legit_mask = train_prepared.y == 0
    X_train_legit = train_prepared.X[legit_mask]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_legit)
    X_test_scaled = scaler.transform(test_X)

    n_features = X_train_scaled.shape[1]
    bottleneck = max(3, n_features // 3)

    model = MLPRegressor(
        hidden_layer_sizes=(n_features, bottleneck, n_features),
        activation="relu",
        max_iter=500,
        random_state=42,
        early_stopping=True,
    )
    model.fit(X_train_scaled, X_train_scaled)  # target = input (reconstruction)

    reconstructed = model.predict(X_test_scaled)
    reconstruction_error = np.mean((X_test_scaled - reconstructed) ** 2, axis=1)

    # Normalize error to a 0-1 "fraud score" via min-max scaling over
    # the test set, so it's on a comparable footing to the other
    # models' probability outputs for evaluation purposes.
    error_min, error_max = reconstruction_error.min(), reconstruction_error.max()
    fraud_score = (reconstruction_error - error_min) / (error_max - error_min + 1e-9)

    # Unlike a classifier's predict_proba (naturally centered so 0.5 is
    # a meaningful cutoff), a min-max normalized reconstruction error
    # has no such natural midpoint — a flat 0.5 threshold flags almost
    # nothing here. Instead, threshold at the expected fraud rate
    # observed in the *training* data (never the test labels, to avoid
    # leakage): if ~4% of transactions are normally fraudulent, flag
    # roughly the most-anomalous 4% by reconstruction error.
    expected_fraud_rate = train_prepared.y.mean()
    operating_threshold = np.percentile(fraud_score, 100 * (1 - expected_fraud_rate))

    result = evaluate_predictions(
        "Autoencoder (reconstruction error)", test_prepared.y.values, fraud_score,
        threshold=operating_threshold,
    )

    joblib.dump(
        {"model": model, "scaler": scaler, "feature_names": train_prepared.feature_names,
         "error_min": error_min, "error_max": error_max},
        MODEL_PATH,
    )

    return result, fraud_score, test_prepared, model


if __name__ == "__main__":
    result, _, _, _ = train_autoencoder()
    print(f"Saved model to {MODEL_PATH}\n")
    for k, v in result.to_row().items():
        print(f"  {k}: {v}")
    print("\nNote: thresholded at the training set's expected fraud rate "
          "(percentile-based), not a flat 0.5 — see comments in this file.")

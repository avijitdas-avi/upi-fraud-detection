"""
Shared evaluation utilities for comparing models on a common footing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass
class EvalResult:
    model_name: str
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    n_flagged: int
    n_fraud: int
    true_positives: int
    false_positives: int
    false_negatives: int

    def to_row(self) -> dict:
        return {
            "model": self.model_name,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "n_flagged": self.n_flagged,
            "n_fraud": self.n_fraud,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


def evaluate_predictions(model_name: str, y_true: np.ndarray, y_proba: np.ndarray, threshold: float = 0.5) -> EvalResult:
    y_pred = (y_proba >= threshold).astype(int)

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())

    return EvalResult(
        model_name=model_name,
        precision=precision_score(y_true, y_pred, zero_division=0),
        recall=recall_score(y_true, y_pred, zero_division=0),
        f1=f1_score(y_true, y_pred, zero_division=0),
        roc_auc=roc_auc_score(y_true, y_proba),
        pr_auc=average_precision_score(y_true, y_proba),
        n_flagged=int(y_pred.sum()),
        n_fraud=int(y_true.sum()),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )

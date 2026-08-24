"""
GNN evaluation metrics.

Computes classification metrics with special attention to:
- False negative rate (FNR): Model says "safe" when it's actually unsafe.
  This is the dangerous error type and must be minimized.
- Precision/Recall/F1: Standard binary classification metrics.
- Confusion matrix: For detailed error analysis.

The false-negative rate is the single most important safety metric —
a model that has great overall accuracy but misses unsafe trades is
worse than useless, it's dangerous.
"""

import numpy as np
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix,
    classification_report,
    roc_auc_score,
)
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def compute_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Compute comprehensive classification metrics for feasibility prediction.

    Convention:
    - Label 1 = feasible (safe trade)
    - Label 0 = infeasible (unsafe trade — would cause grid violation)

    The critical metric is the FALSE NEGATIVE RATE on infeasible trades:
    how often does the model incorrectly say "feasible" when the trade is
    actually infeasible? This is the safety-critical error.

    Args:
        y_true: Ground-truth binary labels (0 = infeasible, 1 = feasible).
        y_pred_proba: Predicted probabilities of feasibility [0, 1].
        threshold: Classification threshold (default 0.5).

    Returns:
        Dict of metric name → value.
    """
    y_pred = (y_pred_proba >= threshold).astype(int)
    y_true = y_true.astype(int)

    # Basic metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # AUC-ROC (if we have both classes)
    try:
        auc_roc = roc_auc_score(y_true, y_pred_proba)
    except ValueError:
        auc_roc = 0.0

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    # FALSE NEGATIVE RATE on infeasible trades
    # FN = model says "feasible" (1) when truth is "infeasible" (0)
    # This is the DANGEROUS error — an unsafe trade slips through
    total_infeasible = tn + fp  # All actually-infeasible trades
    false_negative_rate = fp / max(1, total_infeasible)  # fp here = infeasible classified as feasible

    # Actually, let's be more careful about the convention:
    # In our convention: positive class = feasible (1)
    # TN = correctly identified infeasible trades
    # FP = infeasible trades wrongly classified as feasible (DANGEROUS)
    # FN = feasible trades wrongly classified as infeasible (conservative, not dangerous)
    # TP = correctly identified feasible trades

    # The dangerous error is FP (infeasible trade predicted as feasible)
    dangerous_error_rate = fp / max(1, tn + fp)  # Among all infeasible, how many slip through?

    # The conservative error is FN (feasible trade predicted as infeasible)
    conservative_error_rate = fn / max(1, tp + fn)  # Among all feasible, how many are blocked?

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "auc_roc": round(auc_roc, 4),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        # SAFETY-CRITICAL METRIC: rate at which unsafe trades slip through
        "dangerous_error_rate": round(dangerous_error_rate, 4),
        # Conservative error: rate at which safe trades are unnecessarily blocked
        "conservative_error_rate": round(conservative_error_rate, 4),
        # Aliases for clarity
        "false_negative_rate": round(dangerous_error_rate, 4),  # Alias
        "total_infeasible": int(tn + fp),
        "total_feasible": int(tp + fn),
        "threshold": threshold,
    }


def find_optimal_threshold(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    target_dangerous_error_rate: float = 0.02,
) -> Dict:
    """
    Find the classification threshold that achieves a target dangerous error rate.

    Since false negatives (unsafe trades approved) are the critical error,
    we want to bias the threshold toward caution. This function finds the
    threshold where at most target_dangerous_error_rate of infeasible trades
    slip through.

    Args:
        y_true: Ground-truth labels.
        y_pred_proba: Predicted probabilities.
        target_dangerous_error_rate: Maximum acceptable rate of unsafe trades
            being classified as safe (default: 2%).

    Returns:
        Dict with optimal threshold and resulting metrics.
    """
    best_threshold = 0.5
    best_f1 = 0.0

    for threshold in np.arange(0.1, 0.95, 0.01):
        metrics = compute_metrics(y_true, y_pred_proba, threshold=threshold)
        if metrics["dangerous_error_rate"] <= target_dangerous_error_rate:
            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                best_threshold = threshold

    best_metrics = compute_metrics(y_true, y_pred_proba, threshold=best_threshold)
    best_metrics["optimal_threshold"] = round(best_threshold, 2)

    logger.info(
        f"Optimal threshold: {best_threshold:.2f} "
        f"(dangerous_error_rate={best_metrics['dangerous_error_rate']:.4f}, "
        f"F1={best_metrics['f1']:.4f})"
    )

    return best_metrics


def print_detailed_report(y_true: np.ndarray, y_pred_proba: np.ndarray, threshold: float = 0.5):
    """Print a detailed human-readable evaluation report."""
    y_pred = (y_pred_proba >= threshold).astype(int)

    print("\n" + "=" * 60)
    print("GNN FEASIBILITY MODEL — EVALUATION REPORT")
    print("=" * 60)

    print(f"\nThreshold: {threshold}")
    print(f"\nClassification Report:")
    print(classification_report(
        y_true, y_pred,
        target_names=["Infeasible (unsafe)", "Feasible (safe)"],
    ))

    metrics = compute_metrics(y_true, y_pred_proba, threshold)

    print(f"\n{'─' * 40}")
    print(f"SAFETY-CRITICAL METRICS:")
    print(f"{'─' * 40}")
    print(f"  Dangerous Error Rate (unsafe approved):  {metrics['dangerous_error_rate']:.2%}")
    print(f"  Conservative Error Rate (safe blocked):  {metrics['conservative_error_rate']:.2%}")
    print(f"  AUC-ROC:                                 {metrics['auc_roc']:.4f}")
    print(f"\n{'─' * 40}")
    print(f"  Total infeasible trades in test set:     {metrics['total_infeasible']}")
    print(f"  Total feasible trades in test set:       {metrics['total_feasible']}")
    print(f"  Unsafe trades that slipped through:      {metrics['false_positives']}")
    print(f"  Safe trades unnecessarily blocked:       {metrics['false_negatives']}")
    print("=" * 60)

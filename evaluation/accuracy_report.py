"""
Evaluation: GNN vs MLP Baseline — Accuracy Report.

Loads the held-out test split (time-based, no leakage), runs both the
trained GNN and the MLP baseline on it, and computes:

- Precision / Recall / F1 for both models
- AUC-ROC for both models
- Confusion matrices
- FALSE NEGATIVE RATE (the safety-critical metric) for both models
- ROC curves and Precision-Recall curves (saved as figures)

The GNN MUST outperform the MLP baseline on infeasible-trade detection —
especially recall — to validate the core novelty claim that graph structure
(electrical topology) helps predict grid feasibility.
"""

import sys
import os
import json
import logging
import numpy as np
import torch
from pathlib import Path

# Add server/ to Python path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from ml.utils.data_loader import TradeDataset, get_flat_features
from ml.gnn.model import create_model
from ml.gnn.baseline_mlp import MLPBaseline
from ml.gnn.evaluate import compute_metrics, print_detailed_report
from ml.gnn.train import create_pyg_batch_from_samples, collate_fn
from core.feeder_setup import create_ieee13_feeder

logger = logging.getLogger(__name__)

# Paths
SERVER_DIR = Path(__file__).resolve().parent.parent / "server"
CHECKPOINT_DIR = SERVER_DIR / "ml" / "gnn" / "checkpoints"
DATA_PATH = SERVER_DIR / "data" / "synthetic_trades" / "training_data.parquet"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"


def load_gnn_model(checkpoint_path: Path, device: torch.device):
    """Load trained GNN model from checkpoint."""
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    model = create_model(
        model_type=checkpoint.get("model_type", "graphsage"),
        output_mode=checkpoint.get("output_mode", "classification"),
        hidden_dim=checkpoint.get("hidden_dim", 64),
        num_layers=checkpoint.get("num_layers", 3),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    val_metrics = checkpoint.get("val_metrics", {})
    logger.info(
        f"GNN loaded: {checkpoint.get('model_type', 'graphsage')}, "
        f"epoch={checkpoint.get('epoch', '?')}, "
        f"val_F1={val_metrics.get('f1', 'N/A')}"
    )
    return model


def load_mlp_model(checkpoint_path: Path, device: torch.device):
    """Load trained MLP baseline from checkpoint."""
    model = MLPBaseline()
    model.load_state_dict(torch.load(checkpoint_path, map_location=device, weights_only=True))
    model = model.to(device)
    model.eval()
    logger.info("MLP baseline loaded")
    return model


def evaluate_gnn(model, test_dataset, net, device, batch_size=64):
    """Run GNN inference on the full test set and return predictions + labels."""
    from torch.utils.data import DataLoader

    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn
    )

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for samples in test_loader:
            batch = create_pyg_batch_from_samples(samples, net)
            batch = batch.to(device)
            output = model(batch)
            probs = output["probability"].cpu().numpy()
            labels = batch.y.squeeze().cpu().numpy()
            all_preds.extend(
                probs.tolist() if hasattr(probs, "tolist") else [probs]
            )
            all_labels.extend(
                labels.tolist() if hasattr(labels, "tolist") else [labels]
            )

    return np.array(all_preds), np.array(all_labels)


def evaluate_mlp(model, test_dataset, device, batch_size=64):
    """Run MLP inference on the full test set and return predictions + labels."""
    from torch.utils.data import DataLoader

    def collate_flat(samples):
        features = torch.stack([get_flat_features(s) for s in samples])
        labels = torch.stack([s["label"] for s in samples]).squeeze()
        return features, labels

    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_flat
    )

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for features, labels in test_loader:
            features = features.to(device)
            output = model(features)
            all_preds.extend(output["probability"].cpu().numpy().tolist())
            all_labels.extend(labels.numpy().tolist())

    return np.array(all_preds), np.array(all_labels)


def generate_figures(
    gnn_preds, mlp_preds, labels, gnn_metrics, mlp_metrics, output_dir: Path
):
    """Generate comparison figures: confusion matrices, ROC, PR curves."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.metrics import (
            confusion_matrix,
            roc_curve,
            precision_recall_curve,
            auc,
        )
    except ImportError:
        logger.warning("matplotlib not available - skipping figure generation")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Color palette
    gnn_color = "#00C896"
    mlp_color = "#FF6B6B"

    # =========================================================================
    # 1. Confusion Matrices (side by side)
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, preds, name, color in [
        (axes[0], gnn_preds, "GNN (GraphSAGE)", gnn_color),
        (axes[1], mlp_preds, "MLP Baseline", mlp_color),
    ]:
        cm = confusion_matrix(labels.astype(int), (preds >= 0.5).astype(int), labels=[0, 1])
        im = ax.imshow(cm, cmap="Blues", interpolation="nearest")
        ax.set_title(f"{name}", fontsize=14, fontweight="bold")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Infeasible", "Feasible"])
        ax.set_yticklabels(["Infeasible", "Feasible"])

        # Annotate cells
        for i in range(2):
            for j in range(2):
                text_color = "white" if cm[i, j] > cm.max() / 2 else "black"
                ax.text(j, i, f"{cm[i, j]}", ha="center", va="center",
                        fontsize=16, fontweight="bold", color=text_color)

        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.suptitle(
        "Confusion Matrices — GNN vs MLP Baseline", fontsize=16, fontweight="bold"
    )
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrices.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved confusion_matrices.png")

    # =========================================================================
    # 2. ROC Curves
    # =========================================================================
    fig, ax = plt.subplots(figsize=(8, 6))

    for preds, name, color in [
        (gnn_preds, "GNN (GraphSAGE)", gnn_color),
        (mlp_preds, "MLP Baseline", mlp_color),
    ]:
        fpr, tpr, _ = roc_curve(labels.astype(int), preds)
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, color=color, lw=2, label=f"{name} (AUC = {roc_auc:.4f})")

    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Random")
    ax.set_xlabel("False Positive Rate", fontsize=12)
    ax.set_ylabel("True Positive Rate", fontsize=12)
    ax.set_title("ROC Curves — GNN vs MLP Baseline", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "roc_curves.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved roc_curves.png")

    # =========================================================================
    # 3. Precision-Recall Curves
    # =========================================================================
    fig, ax = plt.subplots(figsize=(8, 6))

    for preds, name, color in [
        (gnn_preds, "GNN (GraphSAGE)", gnn_color),
        (mlp_preds, "MLP Baseline", mlp_color),
    ]:
        precision, recall, _ = precision_recall_curve(labels.astype(int), preds)
        pr_auc = auc(recall, precision)
        ax.plot(recall, precision, color=color, lw=2, label=f"{name} (AUC = {pr_auc:.4f})")

    ax.set_xlabel("Recall", fontsize=12)
    ax.set_ylabel("Precision", fontsize=12)
    ax.set_title(
        "Precision-Recall Curves — GNN vs MLP Baseline",
        fontsize=14, fontweight="bold",
    )
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "precision_recall_curves.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved precision_recall_curves.png")

    # =========================================================================
    # 4. Metrics Comparison Bar Chart
    # =========================================================================
    fig, ax = plt.subplots(figsize=(10, 6))

    metrics_to_compare = ["accuracy", "precision", "recall", "f1", "auc_roc"]
    labels_bar = ["Accuracy", "Precision", "Recall", "F1 Score", "AUC-ROC"]

    gnn_vals = [gnn_metrics[m] for m in metrics_to_compare]
    mlp_vals = [mlp_metrics[m] for m in metrics_to_compare]

    x = np.arange(len(labels_bar))
    width = 0.35

    bars1 = ax.bar(x - width / 2, gnn_vals, width, label="GNN (GraphSAGE)",
                   color=gnn_color, edgecolor="white", linewidth=0.5)
    bars2 = ax.bar(x + width / 2, mlp_vals, width, label="MLP Baseline",
                   color=mlp_color, edgecolor="white", linewidth=0.5)

    # Value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.3f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha="center", va="bottom", fontsize=9,
            )

    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("Model Performance Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels_bar)
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "metrics_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved metrics_comparison.png")

    # =========================================================================
    # 5. Safety Metrics Comparison
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Dangerous error rate
    ax = axes[0]
    vals = [gnn_metrics["dangerous_error_rate"] * 100, mlp_metrics["dangerous_error_rate"] * 100]
    bars = ax.bar(["GNN", "MLP"], vals, color=[gnn_color, mlp_color],
                  edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{val:.2f}%", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("Dangerous Error Rate\n(Unsafe trades approved)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Rate (%)")
    ax.grid(axis="y", alpha=0.3)

    # Conservative error rate
    ax = axes[1]
    vals = [gnn_metrics["conservative_error_rate"] * 100, mlp_metrics["conservative_error_rate"] * 100]
    bars = ax.bar(["GNN", "MLP"], vals, color=[gnn_color, mlp_color],
                  edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{val:.2f}%", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("Conservative Error Rate\n(Safe trades blocked)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Rate (%)")
    ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Safety-Critical Metrics — Lower is Better", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "safety_metrics.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved safety_metrics.png")


def run_accuracy_report():
    """Run the full accuracy evaluation report."""
    print("\n" + "=" * 70)
    print("  GNN FEASIBILITY MODEL - ACCURACY REPORT")
    print("  GNN vs MLP Baseline vs pandapower ground truth")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    # -------------------------------------------------------------------------
    # 1. Load models
    # -------------------------------------------------------------------------
    print("\n--- Loading models ---")
    gnn_model = load_gnn_model(CHECKPOINT_DIR / "best_model.pt", device)
    mlp_model = load_mlp_model(CHECKPOINT_DIR / "best_mlp_baseline.pt", device)

    # -------------------------------------------------------------------------
    # 2. Load test data
    # -------------------------------------------------------------------------
    print("\n--- Loading test data ---")
    test_dataset = TradeDataset(str(DATA_PATH), split="test")
    print(f"Test set size: {len(test_dataset)} samples")

    # -------------------------------------------------------------------------
    # 3. Create feeder for graph construction
    # -------------------------------------------------------------------------
    net = create_ieee13_feeder()

    # -------------------------------------------------------------------------
    # 4. Run GNN evaluation
    # -------------------------------------------------------------------------
    print("\n--- Evaluating GNN (GraphSAGE) ---")
    gnn_preds, gnn_labels = evaluate_gnn(gnn_model, test_dataset, net, device)
    gnn_metrics = compute_metrics(gnn_labels, gnn_preds)

    print_detailed_report(gnn_labels, gnn_preds)

    # -------------------------------------------------------------------------
    # 5. Run MLP evaluation
    # -------------------------------------------------------------------------
    print("\n--- Evaluating MLP Baseline ---")
    mlp_preds, mlp_labels = evaluate_mlp(mlp_model, test_dataset, device)
    mlp_metrics = compute_metrics(mlp_labels, mlp_preds)

    print_detailed_report(mlp_labels, mlp_preds)

    # -------------------------------------------------------------------------
    # 6. Comparison summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  COMPARISON SUMMARY")
    print("=" * 70)

    comparison = {
        "Metric": [
            "Accuracy", "Precision", "Recall", "F1 Score", "AUC-ROC",
            "Dangerous Error Rate", "Conservative Error Rate",
            "False Positives (unsafe approved)", "False Negatives (safe blocked)",
        ],
        "GNN (GraphSAGE)": [
            f"{gnn_metrics['accuracy']:.4f}",
            f"{gnn_metrics['precision']:.4f}",
            f"{gnn_metrics['recall']:.4f}",
            f"{gnn_metrics['f1']:.4f}",
            f"{gnn_metrics['auc_roc']:.4f}",
            f"{gnn_metrics['dangerous_error_rate']:.4f} ({gnn_metrics['dangerous_error_rate']*100:.2f}%)",
            f"{gnn_metrics['conservative_error_rate']:.4f} ({gnn_metrics['conservative_error_rate']*100:.2f}%)",
            f"{gnn_metrics['false_positives']}",
            f"{gnn_metrics['false_negatives']}",
        ],
        "MLP Baseline": [
            f"{mlp_metrics['accuracy']:.4f}",
            f"{mlp_metrics['precision']:.4f}",
            f"{mlp_metrics['recall']:.4f}",
            f"{mlp_metrics['f1']:.4f}",
            f"{mlp_metrics['auc_roc']:.4f}",
            f"{mlp_metrics['dangerous_error_rate']:.4f} ({mlp_metrics['dangerous_error_rate']*100:.2f}%)",
            f"{mlp_metrics['conservative_error_rate']:.4f} ({mlp_metrics['conservative_error_rate']*100:.2f}%)",
            f"{mlp_metrics['false_positives']}",
            f"{mlp_metrics['false_negatives']}",
        ],
    }

    # Print as table
    header = f"{'Metric':<35} {'GNN (GraphSAGE)':<30} {'MLP Baseline':<30}"
    print(header)
    print("-" * 95)
    for i in range(len(comparison["Metric"])):
        row = f"{comparison['Metric'][i]:<35} {comparison['GNN (GraphSAGE)'][i]:<30} {comparison['MLP Baseline'][i]:<30}"
        print(row)

    # Key finding
    gnn_wins = gnn_metrics["f1"] > mlp_metrics["f1"]
    gnn_safer = gnn_metrics["dangerous_error_rate"] < mlp_metrics["dangerous_error_rate"]
    print("\n" + "-" * 70)
    if gnn_wins:
        delta_f1 = gnn_metrics["f1"] - mlp_metrics["f1"]
        print(f"[PASS] GNN OUTPERFORMS MLP by {delta_f1:.4f} F1 points")
    else:
        print(f"[FAIL] WARNING: MLP outperforms GNN - investigate before proceeding!")

    if gnn_safer:
        print(f"[PASS] GNN has LOWER dangerous error rate (safer)")
    else:
        print(f"[FAIL] WARNING: MLP has lower dangerous error rate")
    print("-" * 70)

    # -------------------------------------------------------------------------
    # 7. Generate figures
    # -------------------------------------------------------------------------
    print("\n--- Generating figures ---")
    generate_figures(
        gnn_preds, mlp_preds, gnn_labels,
        gnn_metrics, mlp_metrics, FIGURES_DIR,
    )

    # -------------------------------------------------------------------------
    # 8. Save structured results
    # -------------------------------------------------------------------------
    results = {
        "gnn_metrics": gnn_metrics,
        "mlp_metrics": mlp_metrics,
        "test_set_size": len(test_dataset),
        "gnn_outperforms_mlp": bool(gnn_wins),
        "gnn_safer_than_mlp": bool(gnn_safer),
        "comparison_summary": comparison,
    }

    results_path = FIGURES_DIR / "accuracy_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    run_accuracy_report()

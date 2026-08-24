"""
GNN training loop.

Handles:
- Data loading from the generated training set
- Class-weighted loss (infeasible class weighted higher for safety)
- Train/validation/test evaluation per epoch
- Model checkpointing (save best model)
- Logging metrics for experiment tracking
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch_geometric.data import Data, Batch
import numpy as np
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict

from ml.gnn.model import create_model
from ml.utils.data_loader import TradeDataset, get_flat_features
from ml.utils.graph_features import build_edge_index, NUM_NODE_FEATURES
from ml.gnn.evaluate import compute_metrics
from core.feeder_setup import create_ieee13_feeder

logger = logging.getLogger(__name__)


def create_pyg_batch_from_samples(samples, net):
    """
    Convert a batch of dataset samples into a PyG Batch object.

    Each sample contains bus voltages and line loadings as flat tensors.
    We reconstruct the graph structure from the network topology.
    """
    edge_index = build_edge_index(net)
    data_list = []

    for sample in samples:
        # Build node features from the flat representation
        bus_voltages = sample["bus_voltages"]  # [13]
        features = sample["features"]

        num_buses = len(bus_voltages)
        node_features = torch.zeros((num_buses, NUM_NODE_FEATURES), dtype=torch.float32)

        for i in range(num_buses):
            node_features[i, 0] = bus_voltages[i]  # voltage
            node_features[i, 1] = 0.0  # net injection (not available in flat format)

            # Bus type (approximate)
            if i == 0:
                node_features[i, 2] = 0.0
            else:
                node_features[i, 2] = 0.5

            # Trade effect
            if i == features["seller_bus"]:
                node_features[i, 3] = features["amount_kw"] / 10.0
            elif i == features["buyer_bus"]:
                node_features[i, 3] = -features["amount_kw"] / 10.0

            node_features[i, 4] = 1.0 if i in (features["seller_bus"], features["buyer_bus"]) else 0.0
            node_features[i, 5] = features["amount_kw"] / 10.0

        data = Data(
            x=node_features,
            edge_index=edge_index.clone(),
            y=sample["label"],
        )
        data_list.append(data)

    return Batch.from_data_list(data_list)


def collate_fn(samples):
    """Custom collate function for the DataLoader."""
    return samples  # Return list of dicts; we'll batch them in the training loop


def train_gnn(
    data_path: str,
    model_type: str = "graphsage",
    output_mode: str = "classification",
    hidden_dim: int = 64,
    num_layers: int = 3,
    learning_rate: float = 0.001,
    weight_decay: float = 1e-4,
    num_epochs: int = 100,
    batch_size: int = 64,
    infeasible_weight: float = 3.0,
    patience: int = 15,
    checkpoint_dir: Optional[str] = None,
    device: str = "auto",
) -> Dict:
    """
    Train the GNN feasibility model.

    Args:
        data_path: Path to training data (parquet/csv from trade_simulator).
        model_type: "graphsage" or "gat".
        output_mode: "classification" or "regression".
        hidden_dim: GNN hidden dimension.
        num_layers: Number of graph conv layers.
        learning_rate: Optimizer learning rate.
        weight_decay: L2 regularization.
        num_epochs: Maximum training epochs.
        batch_size: Batch size.
        infeasible_weight: Weight for the infeasible class (higher = more penalty
            for false negatives, i.e., saying "safe" when actually unsafe).
        patience: Early stopping patience (epochs without improvement).
        checkpoint_dir: Directory to save model checkpoints.
        device: "auto", "cuda", or "cpu".

    Returns:
        Dict with training history and best metrics.
    """
    # Device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)
    logger.info(f"Training on device: {device}")

    # Create network (for graph structure)
    net = create_ieee13_feeder()

    # Load datasets
    train_dataset = TradeDataset(data_path, split="train")
    val_dataset = TradeDataset(data_path, split="val")
    test_dataset = TradeDataset(data_path, split="test")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)

    # Create model
    model = create_model(model_type=model_type, output_mode=output_mode, hidden_dim=hidden_dim, num_layers=num_layers)
    model = model.to(device)
    logger.info(f"Model: {model_type}, parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Loss function with class weights
    # Infeasible trades (label=0) are weighted higher because false negatives
    # (model says "safe" when it's actually unsafe) are the dangerous error type
    pos_weight = torch.tensor([1.0 / infeasible_weight], device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # Optimizer
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=5)

    # Checkpoint setup
    if checkpoint_dir is None:
        checkpoint_dir = "ml/gnn/checkpoints"
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

    # Training loop
    best_val_f1 = 0.0
    epochs_without_improvement = 0
    history = {"train_loss": [], "val_loss": [], "val_f1": [], "val_recall": []}

    for epoch in range(num_epochs):
        # === Training ===
        model.train()
        train_loss = 0.0
        train_batches = 0

        for samples in train_loader:
            batch = create_pyg_batch_from_samples(samples, net)
            batch = batch.to(device)

            optimizer.zero_grad()
            output = model(batch)
            loss = criterion(output["logit"], batch.y.squeeze().to(device))
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            train_batches += 1

        avg_train_loss = train_loss / max(1, train_batches)

        # === Validation ===
        model.eval()
        val_loss = 0.0
        val_batches = 0
        val_preds = []
        val_labels = []

        with torch.no_grad():
            for samples in val_loader:
                batch = create_pyg_batch_from_samples(samples, net)
                batch = batch.to(device)

                output = model(batch)
                loss = criterion(output["logit"], batch.y.squeeze().to(device))

                val_loss += loss.item()
                val_batches += 1

                probs = output["probability"].cpu().numpy()
                labels = batch.y.squeeze().cpu().numpy()
                val_preds.extend(probs.tolist() if hasattr(probs, 'tolist') else [probs])
                val_labels.extend(labels.tolist() if hasattr(labels, 'tolist') else [labels])

        avg_val_loss = val_loss / max(1, val_batches)
        val_metrics = compute_metrics(np.array(val_labels), np.array(val_preds))

        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        history["val_f1"].append(val_metrics["f1"])
        history["val_recall"].append(val_metrics["recall"])

        scheduler.step(val_metrics["f1"])

        # Logging
        if (epoch + 1) % 5 == 0 or epoch == 0:
            logger.info(
                f"Epoch {epoch+1}/{num_epochs} — "
                f"train_loss={avg_train_loss:.4f}, val_loss={avg_val_loss:.4f}, "
                f"val_F1={val_metrics['f1']:.4f}, val_recall={val_metrics['recall']:.4f}, "
                f"val_FNR={val_metrics['false_negative_rate']:.4f}"
            )

        # Checkpointing
        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            epochs_without_improvement = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_metrics": val_metrics,
                "model_type": model_type,
                "output_mode": output_mode,
                "hidden_dim": hidden_dim,
                "num_layers": num_layers,
            }, Path(checkpoint_dir) / "best_model.pt")
            logger.info(f"  ✓ New best model saved (val_F1={best_val_f1:.4f})")
        else:
            epochs_without_improvement += 1

        # Early stopping
        if epochs_without_improvement >= patience:
            logger.info(f"Early stopping after {epoch+1} epochs (no improvement for {patience} epochs)")
            break

    # === Final test evaluation ===
    logger.info("\n=== Final Test Evaluation ===")
    checkpoint = torch.load(Path(checkpoint_dir) / "best_model.pt", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    test_preds = []
    test_labels = []

    with torch.no_grad():
        for samples in test_loader:
            batch = create_pyg_batch_from_samples(samples, net)
            batch = batch.to(device)
            output = model(batch)
            probs = output["probability"].cpu().numpy()
            labels = batch.y.squeeze().cpu().numpy()
            test_preds.extend(probs.tolist() if hasattr(probs, 'tolist') else [probs])
            test_labels.extend(labels.tolist() if hasattr(labels, 'tolist') else [labels])

    test_metrics = compute_metrics(np.array(test_labels), np.array(test_preds))
    logger.info(f"Test metrics: {json.dumps(test_metrics, indent=2)}")

    # Save training history
    with open(Path(checkpoint_dir) / "training_history.json", "w") as f:
        json.dump({"history": history, "test_metrics": test_metrics}, f, indent=2)

    return {
        "best_val_f1": best_val_f1,
        "test_metrics": test_metrics,
        "history": history,
        "epochs_trained": epoch + 1,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    data_path = sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_trades/training_data.parquet"
    results = train_gnn(data_path=data_path, num_epochs=50, batch_size=32)
    print(f"\nTraining complete! Best val F1: {results['best_val_f1']:.4f}")

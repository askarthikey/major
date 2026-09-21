"""
Non-graph MLP baseline for ablation study.

This is a standard feedforward neural network that receives the SAME features
as the GNN but flattened into a single vector (no graph structure). It exists
for one purpose: to prove that the graph structure helps.

If the GNN outperforms this baseline on infeasible-trade detection, that proves
the electrical topology carries useful information for feasibility prediction —
which is the core novelty claim.

If the GNN does NOT outperform this baseline, that's a problem: it means either
the features are carrying all the signal and the topology doesn't matter, or
the GNN architecture needs work. Either way, this comparison MUST be reported
honestly in the paper.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict


# Input dimension: 8 scalar features + 13 bus voltages + 11 line loadings = 32
MLP_INPUT_DIM = 8 + 13 + 11


class MLPBaseline(nn.Module):
    """
    Non-graph MLP baseline.

    Architecture: 3-layer MLP with batch norm and dropout.
    Same features as GNN, but without any graph structure.
    """

    def __init__(
        self,
        input_dim: int = MLP_INPUT_DIM,
        hidden_dim: int = 128,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: Flat feature tensor of shape [batch_size, input_dim].

        Returns:
            Dict with 'logit' and 'probability'.
        """
        logit = self.network(x).squeeze(-1)
        return {
            "logit": logit,
            "probability": torch.sigmoid(logit),
        }


def train_mlp_baseline(
    data_path: str,
    num_epochs: int = 100,
    batch_size: int = 64,
    learning_rate: float = 0.001,
    infeasible_weight: float = 3.0,
    device: str = "auto",
) -> Dict:
    """
    Train the MLP baseline for comparison against the GNN.

    Uses the same data, same split, same loss, same metrics —
    the only difference is no graph structure.
    """
    from torch.utils.data import DataLoader
    from ml.utils.data_loader import TradeDataset, get_flat_features
    from ml.gnn.evaluate import compute_metrics
    import numpy as np
    from pathlib import Path

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)

    # Load data
    train_dataset = TradeDataset(data_path, split="train")
    val_dataset = TradeDataset(data_path, split="val")
    test_dataset = TradeDataset(data_path, split="test")

    def collate_flat(samples):
        features = torch.stack([get_flat_features(s) for s in samples])
        labels = torch.stack([s["label"] for s in samples]).squeeze()
        return features, labels

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_flat)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_flat)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_flat)

    # Model
    model = MLPBaseline().to(device)
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([1.0 / infeasible_weight], device=device)
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-4)

    best_val_f1 = 0.0
    checkpoint_dir = Path("ml/gnn/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(num_epochs):
        # Train
        model.train()
        for features, labels in train_loader:
            features, labels = features.to(device), labels.to(device)
            optimizer.zero_grad()
            output = model(features)
            loss = criterion(output["logit"], labels)
            loss.backward()
            optimizer.step()

        # Validate
        model.eval()
        val_preds, val_labels = [], []
        with torch.no_grad():
            for features, labels in val_loader:
                features = features.to(device)
                output = model(features)
                val_preds.extend(output["probability"].cpu().numpy().tolist())
                val_labels.extend(labels.numpy().tolist())

        val_metrics = compute_metrics(np.array(val_labels), np.array(val_preds))

        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            torch.save(model.state_dict(), checkpoint_dir / "best_mlp_baseline.pt")

        if (epoch + 1) % 10 == 0:
            print(f"MLP Epoch {epoch+1}: val_F1={val_metrics['f1']:.4f}, "
                  f"dangerous_err={val_metrics['dangerous_error_rate']:.4f}")

    # Test
    model.load_state_dict(torch.load(checkpoint_dir / "best_mlp_baseline.pt", weights_only=True))
    model.eval()
    test_preds, test_labels = [], []
    with torch.no_grad():
        for features, labels in test_loader:
            features = features.to(device)
            output = model(features)
            test_preds.extend(output["probability"].cpu().numpy().tolist())
            test_labels.extend(labels.numpy().tolist())

    test_metrics = compute_metrics(np.array(test_labels), np.array(test_preds))

    return {
        "model": "MLP Baseline",
        "best_val_f1": best_val_f1,
        "test_metrics": test_metrics,
    }

if __name__ == "__main__":
    import sys
    import json
    data_path = sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_trades/training_data.parquet"
    print(f"Training MLP Baseline on {data_path}...")
    results = train_mlp_baseline(data_path, num_epochs=50)
    print("\n=== Final Test Evaluation ===")
    print(json.dumps(results["test_metrics"], indent=2))
    print(f"\nTraining complete! Best val F1: {results['best_val_f1']:.4f}")

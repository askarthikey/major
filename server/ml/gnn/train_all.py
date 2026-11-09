"""
Master Training Script for GNN Model Zoo.

This script trains all GNN variants (GCN, GraphSAGE, GAT, GRGN) and compares them
against each other on the same dataset and conditions.
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
from typing import Optional, Dict, List

from ml.gnn.model_zoo import create_model_zoo
from ml.utils.data_loader import TradeDataset
from ml.utils.graph_features import build_edge_index, NUM_NODE_FEATURES
from ml.gnn.evaluate import compute_metrics
from core.feeder_setup import create_ieee13_feeder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def create_pyg_batch_from_samples(samples, net):
    """Convert batch of dataset samples into a PyG Batch object."""
    edge_index = build_edge_index(net)
    data_list = []

    for sample in samples:
        bus_voltages = sample["bus_voltages"]
        features = sample["features"]
        num_buses = len(bus_voltages)
        node_features = torch.zeros((num_buses, NUM_NODE_FEATURES), dtype=torch.float32)

        for i in range(num_buses):
            node_features[i, 0] = bus_voltages[i]
            node_features[i, 2] = 0.5 if i != 0 else 0.0
            if i == features["seller_bus"]:
                node_features[i, 3] = features["amount_kw"] / 10.0
            elif i == features["buyer_bus"]:
                node_features[i, 3] = -features["amount_kw"] / 10.0
            node_features[i, 4] = 1.0 if i in (features["seller_bus"], features["buyer_bus"]) else 0.0
            node_features[i, 5] = features["amount_kw"] / 10.0

        data = Data(x=node_features, edge_index=edge_index.clone(), y=sample["label"])
        data_list.append(data)

    return Batch.from_data_list(data_list)

def collate_fn(samples):
    return samples

def train_single_model(
    model_name: str,
    train_loader,
    val_loader,
    test_loader,
    net,
    device,
    config: Dict
) -> Dict:
    """Trains one model from the zoo and returns metrics."""
    logger.info(f"\n--- Training Model: {model_name.upper()} ---")

    model = create_model_zoo(model_name, **config["model_params"]).to(device)
    optimizer = optim.Adam(model.parameters(), lr=config["lr"], weight_decay=config["weight_decay"])
    pos_weight = torch.tensor([1.0 / config["infeasible_weight"]], device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=5)

    best_val_f1 = 0.0
    epochs_without_improvement = 0
    history = {"train_loss": [], "val_loss": []}

    for epoch in range(config["epochs"]):
        model.train()
        train_loss = 0.0
        for samples in train_loader:
            batch = create_pyg_batch_from_samples(samples, net).to(device)
            optimizer.zero_grad()
            output = model(batch)
            loss = criterion(output["logit"], batch.y.squeeze().to(device))
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        val_loss, val_preds, val_labels = 0.0, [], []
        with torch.no_grad():
            for samples in val_loader:
                batch = create_pyg_batch_from_samples(samples, net).to(device)
                output = model(batch)
                loss = criterion(output["logit"], batch.y.squeeze().to(device))
                val_loss += loss.item()
                val_preds.extend(output["probability"].cpu().numpy().tolist())
                val_labels.extend(batch.y.squeeze().cpu().numpy().tolist())

        val_metrics = compute_metrics(np.array(val_labels), np.array(val_preds))
        avg_train_loss = train_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)

        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        scheduler.step(val_metrics["f1"])

        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            epochs_without_improvement = 0
            # Save checkpoint for this specific model
            model_path = Path(config["checkpoint_dir"]) / f"{model_name}_best.pt"
            torch.save(model.state_dict(), model_path)
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= config["patience"]:
            break

    # Final Test Eval
    model.load_state_dict(torch.load(Path(config["checkpoint_dir"]) / f"{model_name}_best.pt"))
    model.eval()
    test_preds, test_labels = [], []
    with torch.no_grad():
        for samples in test_loader:
            batch = create_pyg_batch_from_samples(samples, net).to(device)
            output = model(batch)
            test_preds.extend(output["probability"].cpu().numpy().tolist())
            test_labels.extend(batch.y.squeeze().cpu().numpy().tolist())

    test_metrics = compute_metrics(np.array(test_labels), np.array(test_preds))
    return {"test_metrics": test_metrics, "history": history}

def train_all_models(data_path: str):
    """Orchestrates training of the entire model zoo."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = create_ieee13_feeder()

    # Load datasets
    train_dataset = TradeDataset(data_path, split="train")
    val_dataset = TradeDataset(data_path, split="val")
    test_dataset = TradeDataset(data_path, split="test")

    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False, collate_fn=collate_fn)
    test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False, collate_fn=collate_fn)

    config = {
        "lr": 0.001,
        "weight_decay": 1e-4,
        "epochs": 100,
        "patience": 15,
        "infeasible_weight": 3.0,
        "checkpoint_dir": "server/ml/gnn/checkpoints/zoo",
        "model_params": {"hidden_dim": 64, "num_layers": 3},
    }
    Path(config["checkpoint_dir"]).mkdir(parents=True, exist_ok=True)

    model_names = ["gcn", "graphsage", "gat", "grgn"]
    all_results = {}

    for name in model_names:
        res = train_single_model(name, train_loader, val_loader, test_loader, net, device, config)
        all_results[name] = res

    # Save summary
    with open(Path(config["checkpoint_dir"]) / "zoo_summary.json", "w") as f:
        json.dump(all_results, f, indent=2)

    return all_results

if __name__ == "__main__":
    import sys
    # Use the data path from the simulator
    data_path = sys.argv[1] if len(sys.argv) > 1 else "server/data/synthetic_trades/training_data.parquet"
    all_results = train_all_models(data_path)
    print("\nAll models trained. Summary saved to server/ml/gnn/checkpoints/zoo/zoo_summary.json")

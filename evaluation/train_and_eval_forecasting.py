"""
Master Training and Evaluation Suite for Forecasting.

This script:
1. Trains an LSTM forecaster for a representative household.
2. Evaluates it against the Naive Persistence baseline.
3. Generates a comparative report and visualization.
"""

import torch
import torch.nn as nn
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
import logging
from pathlib import Path
from typing import Dict, List

from ml.forecasting.lstm_model import LSTMForecaster, prepare_sequences, add_time_features
from ml.forecasting.baseline_naive import evaluate_naive_baseline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_and_evaluate():
    # Paths
    profiles_path = "server/data/processed/profiles.parquet"
    checkpoint_dir = Path("server/ml/forecasting/checkpoints")
    figures_dir = Path("evaluation/figures")
    figures_dir.mkdir(parents=True, exist_ok=True)

    if not Path(profiles_path).exists():
        logger.error(f"Profiles not found at {profiles_path}")
        return

    # 1. Load Data
    df = pd.read_parquet(profiles_path)
    hh_id = df["household_id"].unique()[0] # Train for one representative household
    logger.info(f"Training forecasting models for household: {hh_id}")

    # 2. Train LSTM
    # Prepare data
    hh_data = df[df["household_id"] == hh_id].sort_values("timestamp")
    features = add_time_features(hh_data["load_kw"].values, hh_data["solar_kw"].values)
    X, y = prepare_sequences(features)

    # Split
    n = len(X)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)
    X_train, y_train = torch.tensor(X[:train_end], dtype=torch.float32), torch.tensor(y[:train_end], dtype=torch.float32)
    X_val, y_val = torch.tensor(X[train_end:val_end], dtype=torch.float32), torch.tensor(y[train_end:val_end], dtype=torch.float32)
    X_test, y_test = torch.tensor(X[val_end:], dtype=torch.float32), torch.tensor(y[val_end:], dtype=torch.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMForecaster().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Training loop
    model.train()
    for epoch in range(100):
        optimizer.zero_grad()
        pred = model(X_train.to(device))
        loss = criterion(pred, y_train.to(device))
        loss.backward()
        optimizer.step()

    # Save model
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), checkpoint_dir / f"forecaster_{hh_id}.pt")
    logger.info(f"LSTM model saved to {checkpoint_dir}")

    # 3. Evaluation
    # LSTM Test Metrics
    model.eval()
    with torch.no_grad():
        test_pred = model(X_test.to(device)).cpu().numpy()
        test_actual = y_test.numpy()

    mae_load = np.mean(np.abs(test_pred[:, 0] - test_actual[:, 0]))
    rmse_load = np.sqrt(np.mean((test_pred[:, 0] - test_actual[:, 0])**2))

    # Naive Metrics
    naive_res = evaluate_naive_baseline(df, hh_id)

    # 4. Generate Figure: LSTM vs Naive
    plt.figure(figsize=(10, 6))
    metrics = ['MAE Load', 'RMSE Load']
    lstm_vals = [mae_load, rmse_load]
    naive_vals = [naive_res["test_mae_load_kw"], naive_res["test_rmse_load_kw"]]

    x = np.arange(len(metrics))
    width = 0.35

    plt.bar(x - width/2, naive_vals, width, label='Naive Persistence', color='#bdc3c7')
    plt.bar(x + width/2, lstm_vals, width, label='LSTM Forecaster', color='#3498db')

    plt.title(f"Forecasting Accuracy: LSTM vs Naive (HH: {hh_id})", fontsize=14)
    plt.xticks(x, metrics)
    plt.ylabel("Error (kWh)")
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(figures_dir / "forecasting_comparison.png")
    plt.close()

    # 5. Save results to JSON
    forecast_results = {
        "household_id": hh_id,
        "lstm": {
            "mae_load": float(mae_load),
            "rmse_load": float(rmse_load)
        },
        "naive": {
            "mae_load": float(naive_res["test_mae_load_kw"]),
            "rmse_load": float(naive_res["test_rmse_load_kw"])
        },
        "improvement_pct": float((1 - mae_load / naive_res["test_mae_load_kw"]) * 100)
    }
    with open(figures_dir / "forecasting_results.json", "w") as f:
        json.dump(forecast_results, f, indent=2)

    logger.info("✅ Forecasting training and evaluation complete. Figures generated.")

if __name__ == "__main__":
    train_and_evaluate()

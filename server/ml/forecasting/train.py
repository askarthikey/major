"""
LSTM forecasting training script.
"""

import torch
import torch.nn as nn
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Optional

from ml.forecasting.lstm_model import LSTMForecaster, prepare_sequences, add_time_features

logger = logging.getLogger(__name__)


def train_forecaster(
    profiles: pd.DataFrame,
    household_id: str,
    seq_length: int = 12,
    num_epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.001,
    checkpoint_dir: Optional[str] = None,
    device: str = "auto",
) -> Dict:
    """
    Train an LSTM forecaster for a single household.

    Args:
        profiles: DataFrame with timestamp, household_id, load_kw, solar_kw.
        household_id: Which household to train for.
        seq_length: Input sequence length.
        num_epochs: Training epochs.
        batch_size: Batch size.
        learning_rate: Learning rate.
        checkpoint_dir: Where to save the model.
        device: Compute device.

    Returns:
        Dict with training results and test metrics.
    """
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)

    # Filter data for this household
    hh_data = profiles[profiles["household_id"] == household_id].sort_values("timestamp")

    if len(hh_data) < seq_length + 10:
        logger.warning(f"Not enough data for household {household_id}")
        return {"error": "insufficient data"}

    # Prepare features
    features = add_time_features(
        hh_data["load_kw"].values,
        hh_data["solar_kw"].values,
    )

    X, y = prepare_sequences(features, seq_length)

    # Time-based split (70/15/15)
    n = len(X)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)

    X_train, y_train = torch.tensor(X[:train_end], dtype=torch.float32), torch.tensor(y[:train_end], dtype=torch.float32)
    X_val, y_val = torch.tensor(X[train_end:val_end], dtype=torch.float32), torch.tensor(y[train_end:val_end], dtype=torch.float32)
    X_test, y_test = torch.tensor(X[val_end:], dtype=torch.float32), torch.tensor(y[val_end:], dtype=torch.float32)

    # Model
    model = LSTMForecaster(seq_length=seq_length).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    best_val_loss = float("inf")

    for epoch in range(num_epochs):
        model.train()
        # Simple full-batch training for small datasets
        X_b, y_b = X_train.to(device), y_train.to(device)
        optimizer.zero_grad()
        pred = model(X_b)
        loss = criterion(pred, y_b)
        loss.backward()
        optimizer.step()

        # Validation
        model.eval()
        with torch.no_grad():
            val_pred = model(X_val.to(device))
            val_loss = criterion(val_pred, y_val.to(device)).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            if checkpoint_dir:
                Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), Path(checkpoint_dir) / f"forecaster_{household_id}.pt")

    # Test
    model.eval()
    with torch.no_grad():
        test_pred = model(X_test.to(device)).cpu().numpy()
        test_actual = y_test.numpy()

    mae = np.mean(np.abs(test_pred - test_actual), axis=0)
    rmse = np.sqrt(np.mean((test_pred - test_actual) ** 2, axis=0))

    return {
        "household_id": household_id,
        "test_mae_load_kw": float(mae[0]),
        "test_mae_solar_kw": float(mae[1]),
        "test_rmse_load_kw": float(rmse[0]),
        "test_rmse_solar_kw": float(rmse[1]),
        "best_val_loss": best_val_loss,
    }

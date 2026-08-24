"""
LSTM model for per-household short-term load and solar generation forecasting.

This is supporting engineering, not the core novelty (that's the GNN).
The forecaster predicts each household's near-term (15min-1hr ahead) load
and solar generation, which the market engine uses to generate realistic
bids/asks from each household.

Architecture:
- Per-household LSTM with sequence input (past N timesteps)
- Predicts next-step load_kw and solar_kw
- Trained separately from the GNN
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LSTMForecaster(nn.Module):
    """
    LSTM-based short-term load/solar forecaster.

    Input: sequence of past observations [load_kw, solar_kw, hour_sin, hour_cos]
    Output: next-step prediction [load_kw, solar_kw]
    """

    def __init__(
        self,
        input_dim: int = 4,   # [load_kw, solar_kw, hour_sin, hour_cos]
        hidden_dim: int = 64,
        num_layers: int = 2,
        output_dim: int = 2,  # [load_kw, solar_kw]
        dropout: float = 0.2,
        seq_length: int = 12,  # Past 12 timesteps (3 hours at 15-min intervals)
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.seq_length = seq_length

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )

        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, output_dim),
            nn.ReLU(),  # Load and solar are non-negative
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor of shape [batch, seq_length, input_dim]

        Returns:
            Predictions of shape [batch, output_dim]
        """
        lstm_out, _ = self.lstm(x)
        # Take the last timestep's output
        last_hidden = lstm_out[:, -1, :]
        return self.fc(last_hidden)


def prepare_sequences(
    data: np.ndarray,
    seq_length: int = 12,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create input sequences and targets from time series data.

    Args:
        data: Array of shape [timesteps, features]
        seq_length: Number of past timesteps to use as input

    Returns:
        X: Input sequences [num_samples, seq_length, features]
        y: Targets [num_samples, 2] (next load_kw, next solar_kw)
    """
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i:i + seq_length])
        # Target: next timestep's load and solar
        y.append(data[i + seq_length, :2])  # [load_kw, solar_kw]
    return np.array(X), np.array(y)


def add_time_features(load_kw: np.ndarray, solar_kw: np.ndarray, timestamps=None) -> np.ndarray:
    """
    Add cyclical time features to the input.

    Features: [load_kw, solar_kw, hour_sin, hour_cos]
    """
    n = len(load_kw)
    if timestamps is not None:
        hours = np.array([t.hour + t.minute / 60.0 for t in timestamps])
    else:
        # Assume 15-min intervals starting at midnight
        hours = np.array([(i * 15 / 60) % 24 for i in range(n)])

    hour_sin = np.sin(2 * np.pi * hours / 24)
    hour_cos = np.cos(2 * np.pi * hours / 24)

    return np.column_stack([load_kw, solar_kw, hour_sin, hour_cos])

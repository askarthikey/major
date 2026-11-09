"""
MLP Baseline Implementation for the Model Zoo.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict

# Input dimension: 8 scalar features + 13 bus voltages + 11 line loadings = 32
MLP_INPUT_DIM = 8 + 13 + 11

class MLPBaseline(nn.Module):
    def __init__(self, input_dim: int = MLP_INPUT_DIM, hidden_dim: int = 128, dropout: float = 0.3):
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
        logit = self.network(x).squeeze(-1)
        return {
            "logit": logit,
            "probability": torch.sigmoid(logit),
        }

"""
Naive persistence baseline for forecasting.

Prediction rule: tomorrow's value = today's value at the same time.
(Or more precisely: next timestep = current timestep.)

This is the simplest possible forecaster and serves as a sanity check.
The LSTM must beat this to justify its complexity. If it doesn't,
the LSTM is not adding value and the naive approach should be used instead.

This is NOT the novel contribution — forecasting is supporting engineering.
Keep claims honest and modest in the paper.
"""

import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class NaivePersistenceForecaster:
    """
    Naive persistence: next value = last observed value.

    For load: predict the same load as the current timestep.
    For solar: predict the same solar as the current timestep.
    """

    def predict(self, current_load_kw: float, current_solar_kw: float) -> Dict[str, float]:
        """Predict next timestep = current timestep."""
        return {
            "load_kw": current_load_kw,
            "solar_kw": current_solar_kw,
        }


class SeasonalNaiveForecaster:
    """
    Seasonal naive: predict the value from the same time yesterday.

    Better than pure persistence for daily-cyclical patterns.
    """

    def __init__(self, timesteps_per_day: int = 96):
        self.timesteps_per_day = timesteps_per_day
        self.history = []

    def update(self, load_kw: float, solar_kw: float):
        """Add an observation to the history."""
        self.history.append((load_kw, solar_kw))

    def predict(self) -> Dict[str, float]:
        """Predict using value from same time yesterday."""
        if len(self.history) >= self.timesteps_per_day:
            past = self.history[-self.timesteps_per_day]
            return {"load_kw": past[0], "solar_kw": past[1]}
        elif self.history:
            last = self.history[-1]
            return {"load_kw": last[0], "solar_kw": last[1]}
        else:
            return {"load_kw": 1.0, "solar_kw": 0.0}


def evaluate_naive_baseline(profiles: pd.DataFrame, household_id: str) -> Dict:
    """
    Evaluate the naive persistence baseline on a household's data.

    Returns MAE and RMSE for comparison with the LSTM.
    """
    hh_data = profiles[profiles["household_id"] == household_id].sort_values("timestamp")

    if len(hh_data) < 2:
        return {"error": "insufficient data"}

    # Persistence: predict next = current
    actual_load = hh_data["load_kw"].values[1:]
    pred_load = hh_data["load_kw"].values[:-1]

    actual_solar = hh_data["solar_kw"].values[1:]
    pred_solar = hh_data["solar_kw"].values[:-1]

    mae_load = np.mean(np.abs(actual_load - pred_load))
    mae_solar = np.mean(np.abs(actual_solar - pred_solar))
    rmse_load = np.sqrt(np.mean((actual_load - pred_load) ** 2))
    rmse_solar = np.sqrt(np.mean((actual_solar - pred_solar) ** 2))

    return {
        "household_id": household_id,
        "model": "naive_persistence",
        "test_mae_load_kw": float(mae_load),
        "test_mae_solar_kw": float(mae_solar),
        "test_rmse_load_kw": float(rmse_load),
        "test_rmse_solar_kw": float(rmse_solar),
    }

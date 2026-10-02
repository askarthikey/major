"""
Centralized configuration management using Pydantic BaseSettings.
Loads values from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from pathlib import Path


# Project root: two levels up from this file (server/config/settings.py → server/ → project/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- MongoDB ---
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB Atlas connection URI",
    )
    db_name: str = Field(
        default="solar_p2p_trading",
        description="MongoDB database name",
    )

    # --- FastAPI ---
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated list of allowed CORS origins",
    )

    # --- Simulation ---
    simulation_speed: float = Field(
        default=1.0,
        description="Simulation speed multiplier (1.0 = real-time)",
    )
    default_timestep_minutes: int = Field(
        default=15,
        description="Default timestep duration in minutes for simulation",
    )

    # --- ML / GNN ---
    gnn_model_path: str = Field(
        default="server/ml/gnn/checkpoints/best_model.pt",
        description="Path to the trained GNN model checkpoint",
    )
    gnn_fallback_to_pandapower: bool = Field(
        default=True,
        description="If True, fall back to pandapower solver when GNN model is unavailable",
    )

    # --- Grid ---
    voltage_tolerance_pu: float = Field(
        default=0.05,
        description="Voltage tolerance in per-unit (±5% = 0.05)",
    )
    line_loading_limit_pct: float = Field(
        default=100.0,
        description="Maximum line loading percentage before violation",
    )

    # --- Auth / JWT ---
    jwt_secret_key: str = Field(
        default="solar-p2p-dev-secret-change-in-production",
        description="Secret key for JWT token signing",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(
        default=1440,
        description="JWT token expiry in minutes (default: 24 hours)",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def data_raw_dir(self) -> Path:
        return SERVER_ROOT / "data" / "raw"

    @property
    def data_processed_dir(self) -> Path:
        return SERVER_ROOT / "data" / "processed"

    @property
    def data_synthetic_dir(self) -> Path:
        return SERVER_ROOT / "data" / "synthetic_trades"

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()

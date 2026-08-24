"""
Tests for the ledger hash chain.
"""

import pytest
import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ledger.hash_chain import compute_trade_hash, GENESIS_HASH


class TestHashChain:
    """Tests for SHA-256 hash chain integrity."""

    def test_genesis_hash_is_deterministic(self):
        expected = hashlib.sha256(b"solar-p2p-genesis-block").hexdigest()
        assert GENESIS_HASH == expected

    def test_hash_computation_is_deterministic(self):
        trade = {
            "trade_id": "test-001",
            "timestamp": "2024-06-15T12:00:00",
            "buyer_bus": 7,
            "seller_bus": 2,
            "buyer_household_id": "HH_02",
            "seller_household_id": "HH_01",
            "amount_kwh": 1.5,
            "price_per_kwh": 4.0,
            "total_price": 6.0,
            "status": "executed",
            "simulation_timestep": 10,
        }
        hash1 = compute_trade_hash(trade, GENESIS_HASH)
        hash2 = compute_trade_hash(trade, GENESIS_HASH)
        assert hash1 == hash2, "Same input should produce same hash"

    def test_different_data_produces_different_hash(self):
        trade1 = {
            "trade_id": "test-001",
            "timestamp": "2024-06-15T12:00:00",
            "buyer_bus": 7, "seller_bus": 2,
            "buyer_household_id": "HH_02", "seller_household_id": "HH_01",
            "amount_kwh": 1.5, "price_per_kwh": 4.0, "total_price": 6.0,
            "status": "executed", "simulation_timestep": 10,
        }
        trade2 = {**trade1, "amount_kwh": 2.0, "total_price": 8.0}
        hash1 = compute_trade_hash(trade1, GENESIS_HASH)
        hash2 = compute_trade_hash(trade2, GENESIS_HASH)
        assert hash1 != hash2, "Different data should produce different hash"

    def test_chain_linking(self):
        """Verify that changing prev_hash changes the resulting hash."""
        trade = {
            "trade_id": "test-001",
            "timestamp": "2024-06-15T12:00:00",
            "buyer_bus": 7, "seller_bus": 2,
            "buyer_household_id": "HH_02", "seller_household_id": "HH_01",
            "amount_kwh": 1.5, "price_per_kwh": 4.0, "total_price": 6.0,
            "status": "executed", "simulation_timestep": 10,
        }
        hash_with_genesis = compute_trade_hash(trade, GENESIS_HASH)
        hash_with_other = compute_trade_hash(trade, "other_prev_hash")
        assert hash_with_genesis != hash_with_other

    def test_hash_is_valid_sha256(self):
        trade = {
            "trade_id": "test-001", "timestamp": "2024-06-15T12:00:00",
            "buyer_bus": 7, "seller_bus": 2,
            "buyer_household_id": "HH_02", "seller_household_id": "HH_01",
            "amount_kwh": 1.5, "price_per_kwh": 4.0, "total_price": 6.0,
            "status": "executed", "simulation_timestep": 10,
        }
        h = compute_trade_hash(trade, GENESIS_HASH)
        assert len(h) == 64, "SHA-256 hash should be 64 hex characters"
        assert all(c in "0123456789abcdef" for c in h)

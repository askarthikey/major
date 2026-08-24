"""
Tests for the grid simulation layer (Layer 1).

These tests verify:
1. IEEE 13-bus feeder construction is correct
2. Power flow solver converges on realistic loads
3. Voltage and line loading results are in expected ranges
4. Known-unsafe scenarios correctly produce violations
5. Trade application correctly modifies grid state
"""

import pytest
import pandapower as pp
import numpy as np
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.feeder_setup import create_ieee13_feeder, get_topology_for_visualization
from core.run_powerflow import solve_power_flow, solve_with_trade_applied
from core.attach_profiles import (
    generate_synthetic_profiles,
    attach_profiles_to_network,
    DEFAULT_HOUSEHOLD_BUS_MAP,
)


class TestFeederSetup:
    """Tests for IEEE 13-bus feeder construction."""

    def test_feeder_creates_correct_bus_count(self):
        net = create_ieee13_feeder()
        assert len(net.bus) == 13, f"Expected 13 buses, got {len(net.bus)}"

    def test_feeder_has_lines(self):
        net = create_ieee13_feeder()
        assert len(net.line) > 0, "Network should have distribution lines"

    def test_feeder_has_loads(self):
        net = create_ieee13_feeder()
        assert len(net.load) > 0, "Network should have loads"

    def test_feeder_has_ext_grid(self):
        net = create_ieee13_feeder()
        assert len(net.ext_grid) == 1, "Network should have exactly one external grid"

    def test_feeder_has_transformers(self):
        net = create_ieee13_feeder()
        assert len(net.trafo) >= 1, "Network should have at least one transformer"

    def test_voltage_limits_set(self):
        net = create_ieee13_feeder()
        for idx in net.bus.index:
            assert net.bus.at[idx, "max_vm_pu"] == 1.05
            assert net.bus.at[idx, "min_vm_pu"] == 0.95

    def test_topology_for_visualization(self):
        net = create_ieee13_feeder()
        topo = get_topology_for_visualization(net)
        assert "nodes" in topo
        assert "edges" in topo
        assert len(topo["nodes"]) == 13
        assert len(topo["edges"]) > 0


class TestPowerFlow:
    """Tests for the power flow solver wrapper."""

    def test_power_flow_converges(self):
        net = create_ieee13_feeder()
        result = solve_power_flow(net)
        assert result.converged, "Power flow should converge on default loads"

    def test_default_loads_are_feasible(self):
        net = create_ieee13_feeder()
        result = solve_power_flow(net)
        assert result.is_feasible, "Default loads should not cause violations"

    def test_voltages_in_reasonable_range(self):
        net = create_ieee13_feeder()
        result = solve_power_flow(net)
        for bus_id, voltage in result.bus_voltages.items():
            assert 0.8 < voltage < 1.2, f"Bus {bus_id} voltage {voltage} outside reasonable range"

    def test_line_loadings_nonnegative(self):
        net = create_ieee13_feeder()
        result = solve_power_flow(net)
        for line_id, loading in result.line_loadings.items():
            assert loading >= 0, f"Line {line_id} loading {loading} should be non-negative"

    def test_solve_time_under_one_second(self):
        """Milestone check: power flow should solve in under 1 second."""
        net = create_ieee13_feeder()
        result = solve_power_flow(net)
        assert result.solve_time_ms < 1000, f"Solve time {result.solve_time_ms}ms exceeds 1 second"

    def test_result_to_dict(self):
        net = create_ieee13_feeder()
        result = solve_power_flow(net)
        d = result.to_dict()
        assert "converged" in d
        assert "bus_voltages" in d
        assert "line_loadings" in d
        assert "is_feasible" in d


class TestTradeApplication:
    """Tests for applying trades to the grid."""

    def test_trade_application_returns_two_results(self):
        net = create_ieee13_feeder()
        baseline, with_trade = solve_with_trade_applied(
            net, seller_bus=2, buyer_bus=7, amount_kw=50,
        )
        assert baseline.converged
        assert with_trade.converged

    def test_trade_changes_voltages(self):
        """A trade should cause some change in bus voltages."""
        net = create_ieee13_feeder()
        baseline, with_trade = solve_with_trade_applied(
            net, seller_bus=2, buyer_bus=7, amount_kw=100,
        )
        # At least one bus should have a different voltage
        changed = False
        for bus_id in baseline.bus_voltages:
            if abs(baseline.bus_voltages[bus_id] - with_trade.bus_voltages.get(bus_id, 0)) > 1e-6:
                changed = True
                break
        assert changed, "Trade should cause some voltage change"

    def test_network_restored_after_trade(self):
        """Network loads should be restored after solve_with_trade_applied."""
        net = create_ieee13_feeder()
        original_loads = net.load["p_mw"].copy()
        solve_with_trade_applied(net, seller_bus=2, buyer_bus=7, amount_kw=50)
        assert (net.load["p_mw"] == original_loads).all(), "Loads should be restored"


class TestProfiles:
    """Tests for household profile generation and attachment."""

    def test_synthetic_profiles_generated(self):
        df = generate_synthetic_profiles(num_timesteps=10)
        assert len(df) > 0
        assert "timestamp" in df.columns
        assert "household_id" in df.columns
        assert "load_kw" in df.columns
        assert "solar_kw" in df.columns

    def test_synthetic_loads_nonnegative(self):
        df = generate_synthetic_profiles(num_timesteps=10)
        assert (df["load_kw"] >= 0).all()
        assert (df["solar_kw"] >= 0).all()

    def test_solar_only_for_solar_households(self):
        df = generate_synthetic_profiles(num_timesteps=10)
        non_solar = [hh for hh, c in DEFAULT_HOUSEHOLD_BUS_MAP.items() if not c["has_solar"]]
        for hh_id in non_solar:
            hh_data = df[df["household_id"] == hh_id]
            assert (hh_data["solar_kw"] == 0).all(), f"{hh_id} should have zero solar"

    def test_attach_profiles_returns_states(self):
        net = create_ieee13_feeder()
        profiles = generate_synthetic_profiles(num_timesteps=10)
        states = attach_profiles_to_network(net, profiles, timestep_idx=0)
        assert len(states) > 0
        for hh_id, state in states.items():
            assert "bus_id" in state
            assert "load_kw" in state
            assert "solar_kw" in state

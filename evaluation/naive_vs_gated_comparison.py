"""
Evaluation: Naive vs GNN-Gated Market Comparison — THE HEADLINE EXPERIMENT.

This script runs the same simulated trading session twice:
1. NAIVE: economic-only matching (no feasibility gate)
2. GATED: with GNN feasibility gate checking every trade

And reports:
(a) How many line overloads/voltage violations the naive version causes
(b) How many violations the gated version prevents
(c) The economic efficiency cost of adding the safety gate

This three-part comparison is the SINGLE MOST IMPORTANT figure/table in the paper.
Every naive trade is validated against pandapower ground truth to count actual
violations — this ensures the violation count is honest and physics-based.
"""

import sys
import json
import logging
import copy
import time
import numpy as np
from pathlib import Path
from datetime import datetime

# Add server/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import pandapower as pp

from core.feeder_setup import create_ieee13_feeder
from core.attach_profiles import (
    generate_synthetic_profiles,
    load_real_profiles,
    attach_profiles_to_network,
)
from core.run_powerflow import solve_power_flow, solve_with_trade_applied
from market.auction_engine import (
    DoubleAuctionEngine,
    generate_orders_from_household_states,
)
from market.feasibility_gate import FeasibilityGate
from ml.gnn.inference import GNNInferenceEngine

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).resolve().parent.parent / "server"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"
GNN_CHECKPOINT = SERVER_DIR / "ml" / "gnn" / "checkpoints" / "best_model.pt"


class SimulationResult:
    """Aggregated results from a simulation run."""

    def __init__(self, mode: str):
        self.mode = mode  # "naive" or "gated"
        self.total_trades_matched = 0
        self.total_trades_executed = 0
        self.total_trades_rejected = 0
        self.total_trades_partial = 0
        self.total_energy_kwh = 0.0
        self.total_revenue = 0.0
        self.total_voltage_violations = 0
        self.total_line_violations = 0
        self.total_violations = 0  # combined
        self.violated_timesteps = 0
        self.per_timestep = []

    def add_timestep(self, data: dict):
        self.per_timestep.append(data)
        self.total_trades_matched += data.get("matched", 0)
        self.total_trades_executed += data.get("executed", 0)
        self.total_trades_rejected += data.get("rejected", 0)
        self.total_trades_partial += data.get("partial", 0)
        self.total_energy_kwh += data.get("energy_kwh", 0)
        self.total_revenue += data.get("revenue", 0)
        v_viol = data.get("voltage_violations", 0)
        l_viol = data.get("line_violations", 0)
        self.total_voltage_violations += v_viol
        self.total_line_violations += l_viol
        self.total_violations += v_viol + l_viol
        if v_viol + l_viol > 0:
            self.violated_timesteps += 1

    def to_dict(self):
        return {
            "mode": self.mode,
            "total_trades_matched": self.total_trades_matched,
            "total_trades_executed": self.total_trades_executed,
            "total_trades_rejected": self.total_trades_rejected,
            "total_trades_partial": self.total_trades_partial,
            "total_energy_kwh": round(self.total_energy_kwh, 3),
            "total_revenue": round(self.total_revenue, 2),
            "total_voltage_violations": self.total_voltage_violations,
            "total_line_violations": self.total_line_violations,
            "total_violations": self.total_violations,
            "violated_timesteps": self.violated_timesteps,
            "num_timesteps": len(self.per_timestep),
        }


def run_naive_simulation(
    net, profiles, num_timesteps: int, seed: int = 42,
    timestep_offset: int = 0,
) -> SimulationResult:
    """
    Run the NAIVE simulation: pure economic matching, no feasibility gate.

    Every trade matched by the auction is assumed to execute.
    After execution, we validate each trade against pandapower ground truth
    to count how many would have caused actual grid violations.
    """
    result = SimulationResult("naive")
    np.random.seed(seed)

    for t in range(num_timesteps):
        actual_t = t + timestep_offset
        # 1. Attach profiles for this timestep
        household_states = attach_profiles_to_network(
            net, profiles, actual_t, load_scale_factor=50.0
        )

        # 2. Baseline power flow
        baseline_pf = solve_power_flow(net)
        if not baseline_pf.converged:
            result.add_timestep({"timestep": t, "error": "no convergence"})
            continue

        # 3. Generate orders and match via auction
        orders = generate_orders_from_household_states(household_states)
        auction = DoubleAuctionEngine()
        matched_trades = auction.submit_bulk_orders(orders)

        # 4. In naive mode, ALL matched trades execute (no feasibility gate)
        timestep_voltage_violations = 0
        timestep_line_violations = 0
        timestep_energy = 0.0
        timestep_revenue = 0.0

        for trade in matched_trades:
            timestep_energy += trade.amount_kwh
            timestep_revenue += trade.amount_kwh * trade.clearing_price

            # Validate against pandapower ground truth: would this trade actually
            # cause a grid violation?
            _, trade_pf = solve_with_trade_applied(
                net,
                seller_bus=trade.seller_bus,
                buyer_bus=trade.buyer_bus,
                amount_kw=trade.amount_kwh * 4,  # 15-min kWh -> kW
            )

            if trade_pf.converged:
                timestep_voltage_violations += len(trade_pf.voltage_violations)
                timestep_line_violations += len(trade_pf.line_violations)
            else:
                # Non-convergence is itself a violation indicator
                timestep_voltage_violations += 1

        result.add_timestep({
            "timestep": t,
            "matched": len(matched_trades),
            "executed": len(matched_trades),
            "rejected": 0,
            "partial": 0,
            "energy_kwh": timestep_energy,
            "revenue": timestep_revenue,
            "voltage_violations": timestep_voltage_violations,
            "line_violations": timestep_line_violations,
        })

        if (t + 1) % 24 == 0 or t == 0:
            logger.info(
                f"[NAIVE] Timestep {t+1}/{num_timesteps}: "
                f"{len(matched_trades)} trades, "
                f"{timestep_voltage_violations} voltage violations, "
                f"{timestep_line_violations} line violations"
            )

    return result


def run_gated_simulation(
    net, profiles, num_timesteps: int, gnn_engine: GNNInferenceEngine, seed: int = 42,
    timestep_offset: int = 0,
) -> SimulationResult:
    """
    Run the GATED simulation: economic matching + GNN feasibility gate.

    Every trade matched by the auction goes through the GNN feasibility gate.
    Trades predicted as infeasible are rejected or partially filled.
    After execution, we also validate the executed trades against pandapower
    to count any residual violations (false negatives from the GNN).
    """
    result = SimulationResult("gated")
    np.random.seed(seed)
    gate = FeasibilityGate(gnn_engine=gnn_engine, enable_partial_fill=True)

    for t in range(num_timesteps):
        actual_t = t + timestep_offset
        # 1. Attach profiles for this timestep
        household_states = attach_profiles_to_network(
            net, profiles, actual_t, load_scale_factor=50.0
        )

        # 2. Baseline power flow
        baseline_pf = solve_power_flow(net)
        if not baseline_pf.converged:
            result.add_timestep({"timestep": t, "error": "no convergence"})
            continue

        # 3. Generate orders and match via auction
        orders = generate_orders_from_household_states(household_states)
        auction = DoubleAuctionEngine()
        matched_trades = auction.submit_bulk_orders(orders)

        # 4. Feasibility gate checks each matched trade
        timestep_executed = 0
        timestep_rejected = 0
        timestep_partial = 0
        timestep_energy = 0.0
        timestep_revenue = 0.0
        timestep_voltage_violations = 0
        timestep_line_violations = 0

        for trade in matched_trades:
            from ledger.models import TradeStatus

            trade_record = gate.check_trade(
                trade=trade,
                net=net,
                bus_voltages=baseline_pf.bus_voltages,
                line_loadings=baseline_pf.line_loadings,
                household_states=household_states,
            )

            if trade_record.status == TradeStatus.EXECUTED:
                timestep_executed += 1
                timestep_energy += trade_record.amount_kwh
                timestep_revenue += trade_record.total_price

                # Validate executed trades against pandapower
                _, trade_pf = solve_with_trade_applied(
                    net,
                    seller_bus=trade.seller_bus,
                    buyer_bus=trade.buyer_bus,
                    amount_kw=trade_record.amount_kwh * 4,
                )
                if trade_pf.converged:
                    timestep_voltage_violations += len(trade_pf.voltage_violations)
                    timestep_line_violations += len(trade_pf.line_violations)

            elif trade_record.status == TradeStatus.PARTIAL_FILL:
                timestep_partial += 1
                timestep_energy += trade_record.amount_kwh
                timestep_revenue += trade_record.total_price

                # Validate partial fill against pandapower
                _, trade_pf = solve_with_trade_applied(
                    net,
                    seller_bus=trade.seller_bus,
                    buyer_bus=trade.buyer_bus,
                    amount_kw=trade_record.amount_kwh * 4,
                )
                if trade_pf.converged:
                    timestep_voltage_violations += len(trade_pf.voltage_violations)
                    timestep_line_violations += len(trade_pf.line_violations)

            else:
                timestep_rejected += 1

        result.add_timestep({
            "timestep": t,
            "matched": len(matched_trades),
            "executed": timestep_executed,
            "rejected": timestep_rejected,
            "partial": timestep_partial,
            "energy_kwh": timestep_energy,
            "revenue": timestep_revenue,
            "voltage_violations": timestep_voltage_violations,
            "line_violations": timestep_line_violations,
        })

        if (t + 1) % 24 == 0 or t == 0:
            logger.info(
                f"[GATED] Timestep {t+1}/{num_timesteps}: "
                f"{len(matched_trades)} matched -> "
                f"{timestep_executed} executed, {timestep_rejected} rejected, "
                f"{timestep_partial} partial, "
                f"{timestep_voltage_violations} V violations"
            )

    return result


def generate_figures(naive: SimulationResult, gated: SimulationResult, output_dir: Path):
    """Generate comparison figures."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available - skipping figure generation")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    n_color = "#FF6B6B"
    g_color = "#00C896"

    # =========================================================================
    # 1. Violations Comparison Bar Chart
    # =========================================================================
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # (a) Total violations
    ax = axes[0]
    bars = ax.bar(
        ["Naive\n(No Gate)", "GNN-Gated"],
        [naive.total_violations, gated.total_violations],
        color=[n_color, g_color],
        edgecolor="white",
        linewidth=0.5,
    )
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                f"{int(h)}", ha="center", fontsize=14, fontweight="bold")
    ax.set_title("(a) Grid Violations", fontsize=13, fontweight="bold")
    ax.set_ylabel("Total Violations")
    ax.grid(axis="y", alpha=0.3)

    # (b) Energy traded
    ax = axes[1]
    bars = ax.bar(
        ["Naive", "GNN-Gated"],
        [naive.total_energy_kwh, gated.total_energy_kwh],
        color=[n_color, g_color],
        edgecolor="white",
        linewidth=0.5,
    )
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                f"{h:.1f}", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("(b) Energy Traded (kWh)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Total kWh")
    ax.grid(axis="y", alpha=0.3)

    # (c) Revenue
    ax = axes[2]
    bars = ax.bar(
        ["Naive", "GNN-Gated"],
        [naive.total_revenue, gated.total_revenue],
        color=[n_color, g_color],
        edgecolor="white",
        linewidth=0.5,
    )
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                f"₹{h:.1f}", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("(c) Market Revenue (₹)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Total Revenue (₹)")
    ax.grid(axis="y", alpha=0.3)

    plt.suptitle(
        "Naive vs GNN-Gated Market Comparison",
        fontsize=15, fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_dir / "naive_vs_gated_bars.png", dpi=150, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # 2. Violations Over Time
    # =========================================================================
    fig, ax = plt.subplots(figsize=(12, 5))

    naive_viols = [
        step.get("voltage_violations", 0) + step.get("line_violations", 0)
        for step in naive.per_timestep
    ]
    gated_viols = [
        step.get("voltage_violations", 0) + step.get("line_violations", 0)
        for step in gated.per_timestep
    ]

    timesteps = list(range(len(naive_viols)))
    # Convert to simulation time (15-min intervals)
    hours = [(t * 15 / 60) % 24 for t in timesteps]

    ax.fill_between(timesteps, naive_viols, alpha=0.3, color=n_color)
    ax.plot(timesteps, naive_viols, color=n_color, linewidth=2, label="Naive (No Gate)")
    ax.fill_between(timesteps, gated_viols, alpha=0.3, color=g_color)
    ax.plot(timesteps, gated_viols, color=g_color, linewidth=2, label="GNN-Gated")

    ax.set_xlabel("Timestep (15-min intervals)", fontsize=12)
    ax.set_ylabel("Violations Count", fontsize=12)
    ax.set_title(
        "Grid Violations Over Time — Naive vs GNN-Gated",
        fontsize=14, fontweight="bold",
    )
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_dir / "violations_over_time.png", dpi=150, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # 3. Trade Outcomes Breakdown
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Naive
    ax = axes[0]
    if naive.total_trades_executed > 0:
        ax.pie([naive.total_trades_executed], labels=["Executed"], colors=[n_color],
               autopct=lambda p: f'{int(naive.total_trades_executed)}', startangle=90,
               textprops={"fontsize": 14, "fontweight": "bold"})
    else:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center", fontsize=14)
    ax.set_title("Naive (No Gate)", fontsize=13, fontweight="bold")

    # Gated
    ax = axes[1]
    sizes = [gated.total_trades_executed, gated.total_trades_rejected, gated.total_trades_partial]
    labels_pie = [
        f"Executed\n({gated.total_trades_executed})",
        f"Rejected\n({gated.total_trades_rejected})",
        f"Partial\n({gated.total_trades_partial})",
    ]
    colors = [g_color, "#FF6B6B", "#FFD93D"]
    # Filter out zero-size slices
    non_zero = [(s, l, c) for s, l, c in zip(sizes, labels_pie, colors) if s > 0]
    if non_zero:
        sizes_nz, labels_nz, colors_nz = zip(*non_zero)
        ax.pie(sizes_nz, labels=labels_nz, colors=colors_nz,
               autopct="%1.1f%%", startangle=90,
               textprops={"fontsize": 11})
    else:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center", fontsize=14)
    ax.set_title("GNN-Gated", fontsize=13, fontweight="bold")

    plt.suptitle("Trade Outcomes Breakdown", fontsize=15, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_dir / "trade_outcomes.png", dpi=150, bbox_inches="tight")
    plt.close()

    logger.info("Saved comparison figures")


def run_comparison(num_timesteps: int = 96, seed: int = 42):
    """
    Run the naive vs gated comparison experiment.

    This is THE headline result of the entire project.
    """
    print("\n" + "=" * 70)
    print("  NAIVE vs GNN-GATED MARKET COMPARISON")
    print("  The headline experiment")
    print("=" * 70)

    start_time = time.time()

    # -------------------------------------------------------------------------
    # 1. Set up (identical for both runs)
    # -------------------------------------------------------------------------
    print("\n--- Setting up ---")
    net = create_ieee13_feeder()

    # Prefer real profiles
    real_profiles = load_real_profiles()
    timestep_offset = 0
    if real_profiles is not None:
        profiles = real_profiles
        # Find a summer day with solar generation (not winter/night)
        # Pick a timestep range around June-July for maximum solar
        timestamps = sorted(profiles['timestamp'].unique())
        total_ts = len(timestamps)
        # Target mid-year (summer) — scan for a range with high solar
        best_offset = total_ts // 2  # Default to mid-dataset
        best_solar = 0
        for candidate in range(total_ts // 3, 2 * total_ts // 3, 96):
            if candidate + num_timesteps > total_ts:
                break
            chunk = profiles[profiles['timestamp'].isin(
                timestamps[candidate:candidate + num_timesteps]
            )]
            solar_sum = chunk['solar_kw'].sum()
            if solar_sum > best_solar:
                best_solar = solar_sum
                best_offset = candidate
        timestep_offset = best_offset
        ts_start = timestamps[timestep_offset]
        ts_end = timestamps[min(timestep_offset + num_timesteps - 1, total_ts - 1)]
        print(f"Using real Pecan Street profiles")
        print(f"Selected timestep range: {ts_start} to {ts_end} (offset={timestep_offset})")
        print(f"Solar generation in range: {best_solar:.1f} kW total")
    else:
        profiles = generate_synthetic_profiles(num_timesteps=num_timesteps)
        print(f"Using synthetic profiles ({num_timesteps} timesteps)")

    print(f"Simulation: {num_timesteps} timesteps (= {num_timesteps * 15 / 60:.0f} hours)")

    # Load GNN
    gnn_engine = GNNInferenceEngine(checkpoint_path=str(GNN_CHECKPOINT))
    if gnn_engine.model_loaded:
        print(f"GNN model loaded [PASS]")
    else:
        print("WARNING: GNN not loaded - gated simulation will use pandapower fallback")

    # -------------------------------------------------------------------------
    # 2. Run NAIVE simulation
    # -------------------------------------------------------------------------
    print(f"\n{'='*50}")
    print("  Running NAIVE simulation (no feasibility gate)...")
    print(f"{'='*50}")
    naive_result = run_naive_simulation(
        net, profiles, num_timesteps, seed=seed, timestep_offset=timestep_offset,
    )
    print(f"Naive complete: {naive_result.total_violations} total violations")

    # -------------------------------------------------------------------------
    # 3. Run GATED simulation
    # -------------------------------------------------------------------------
    print(f"\n{'='*50}")
    print("  Running GATED simulation (GNN feasibility gate)...")
    print(f"{'='*50}")
    gated_result = run_gated_simulation(
        net, profiles, num_timesteps, gnn_engine, seed=seed,
        timestep_offset=timestep_offset,
    )
    print(f"Gated complete: {gated_result.total_violations} total violations")

    # -------------------------------------------------------------------------
    # 4. Compute comparison metrics
    # -------------------------------------------------------------------------
    total_time = time.time() - start_time

    violations_prevented = naive_result.total_violations - gated_result.total_violations
    violations_prevented_pct = (
        violations_prevented / max(1, naive_result.total_violations) * 100
    )

    energy_reduction = naive_result.total_energy_kwh - gated_result.total_energy_kwh
    energy_reduction_pct = (
        energy_reduction / max(0.001, naive_result.total_energy_kwh) * 100
    )

    revenue_reduction = naive_result.total_revenue - gated_result.total_revenue
    revenue_reduction_pct = (
        revenue_reduction / max(0.001, naive_result.total_revenue) * 100
    )

    trades_blocked = (
        gated_result.total_trades_rejected + gated_result.total_trades_partial
    )
    trades_blocked_pct = (
        trades_blocked / max(1, naive_result.total_trades_executed) * 100
    )

    # -------------------------------------------------------------------------
    # 5. Print results
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  HEADLINE RESULTS")
    print("=" * 70)

    print(f"\n  (a) VIOLATIONS PREVENTED:")
    print(f"      Naive caused:     {naive_result.total_violations} total violations")
    print(f"        - Voltage:      {naive_result.total_voltage_violations}")
    print(f"        - Line loading: {naive_result.total_line_violations}")
    print(f"        - Timesteps:    {naive_result.violated_timesteps}/{num_timesteps} had violations")
    print(f"      Gated caused:     {gated_result.total_violations} total violations")
    print(f"        - Voltage:      {gated_result.total_voltage_violations}")
    print(f"        - Line loading: {gated_result.total_line_violations}")
    print(f"      --------------")
    print(f"      PREVENTED:        {violations_prevented} violations ({violations_prevented_pct:.1f}%)")

    print(f"\n  (b) ECONOMIC EFFICIENCY COST:")
    print(f"      Naive energy:     {naive_result.total_energy_kwh:.2f} kWh")
    print(f"      Gated energy:     {gated_result.total_energy_kwh:.2f} kWh")
    print(f"      Energy cost:      {energy_reduction:.2f} kWh ({energy_reduction_pct:.1f}%)")
    print(f"      Naive revenue:    Rs {naive_result.total_revenue:.2f}")
    print(f"      Gated revenue:    Rs {gated_result.total_revenue:.2f}")
    print(f"      Revenue cost:     Rs {revenue_reduction:.2f} ({revenue_reduction_pct:.1f}%)")

    print(f"\n  (c) TRADE OUTCOMES:")
    print(f"      Naive executed:   {naive_result.total_trades_executed} trades (all)")
    print(f"      Gated executed:   {gated_result.total_trades_executed} trades")
    print(f"      Gated rejected:   {gated_result.total_trades_rejected} trades")
    print(f"      Gated partial:    {gated_result.total_trades_partial} trades")
    print(f"      Trades blocked:   {trades_blocked} ({trades_blocked_pct:.1f}%)")

    print(f"\n  Total computation time: {total_time:.1f}s")
    print("=" * 70)

    # The one-liner for the paper abstract:
    print(f"\n  PAPER ABSTRACT STAT:")
    print(f"     \"The GNN-gated market prevented {violations_prevented_pct:.0f}% of grid violations")
    print(f"      at an economic efficiency cost of {energy_reduction_pct:.1f}% reduced energy traded.\"")
    print()

    # -------------------------------------------------------------------------
    # 6. Generate figures
    # -------------------------------------------------------------------------
    print("--- Generating figures ---")
    generate_figures(naive_result, gated_result, FIGURES_DIR)

    # -------------------------------------------------------------------------
    # 7. Save structured results
    # -------------------------------------------------------------------------
    comparison_results = {
        "naive": naive_result.to_dict(),
        "gated": gated_result.to_dict(),
        "comparison": {
            "violations_prevented": violations_prevented,
            "violations_prevented_pct": round(violations_prevented_pct, 2),
            "energy_reduction_kwh": round(energy_reduction, 3),
            "energy_reduction_pct": round(energy_reduction_pct, 2),
            "revenue_reduction": round(revenue_reduction, 2),
            "revenue_reduction_pct": round(revenue_reduction_pct, 2),
            "trades_blocked": trades_blocked,
            "trades_blocked_pct": round(trades_blocked_pct, 2),
        },
        "config": {
            "num_timesteps": num_timesteps,
            "seed": seed,
            "gnn_model_loaded": gnn_engine.model_loaded,
        },
        "computation_time_seconds": round(total_time, 1),
    }

    results_path = FIGURES_DIR / "comparison_results.json"
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(comparison_results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    return comparison_results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    num_timesteps = int(sys.argv[1]) if len(sys.argv) > 1 else 96
    run_comparison(num_timesteps=num_timesteps)

"""
Evaluation: GNN Inference Speed vs pandapower Power Flow Solve.

Times both approaches on the same set of candidate trades:
1. GNN: Load model, create PyG graph, run forward pass
2. pandapower: Full Newton-Raphson power flow solve

Reports mean, median, p95, p99 latency and the speedup factor.
This is the practical justification for using ML at all — if the GNN
isn't meaningfully faster, you might as well just run the real solver.

Expected speedup: 100-1000x.
"""

import sys
import json
import logging
import time
import numpy as np
import torch
from pathlib import Path

# Add server/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from core.feeder_setup import create_ieee13_feeder
from core.attach_profiles import generate_synthetic_profiles, attach_profiles_to_network
from core.run_powerflow import solve_power_flow, solve_with_trade_applied
from ml.gnn.inference import GNNInferenceEngine

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).resolve().parent.parent / "server"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"
GNN_CHECKPOINT = SERVER_DIR / "ml" / "gnn" / "checkpoints" / "best_model.pt"

# Household-bus mapping (must match the project's config)
SOLAR_BUSES = [1, 2, 5, 7, 10]
NON_SOLAR_BUSES = [3, 4, 6, 8, 9, 11, 12]


def generate_random_trades(num_trades: int, rng: np.random.Generator):
    """Generate random candidate trades for benchmarking."""
    trades = []
    for _ in range(num_trades):
        seller_bus = rng.choice(SOLAR_BUSES)
        buyer_bus = rng.choice(NON_SOLAR_BUSES)
        amount_kw = rng.uniform(0.5, 5.0)
        trades.append({
            "seller_bus": int(seller_bus),
            "buyer_bus": int(buyer_bus),
            "amount_kw": float(amount_kw),
        })
    return trades


def benchmark_gnn(gnn_engine, net, bus_voltages, line_loadings, household_states, trades):
    """Benchmark GNN inference on all trades. Returns list of latency_ms."""
    latencies = []
    for trade in trades:
        start = time.perf_counter()
        gnn_engine.predict(
            net=net,
            bus_voltages=bus_voltages,
            line_loadings=line_loadings,
            household_states=household_states,
            seller_bus=trade["seller_bus"],
            buyer_bus=trade["buyer_bus"],
            amount_kw=trade["amount_kw"],
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
    return latencies


def benchmark_pandapower(net, trades):
    """Benchmark full pandapower power flow solve on all trades. Returns list of latency_ms."""
    latencies = []
    for trade in trades:
        start = time.perf_counter()
        solve_with_trade_applied(
            net,
            seller_bus=trade["seller_bus"],
            buyer_bus=trade["buyer_bus"],
            amount_kw=trade["amount_kw"],
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
    return latencies


def compute_latency_stats(latencies):
    """Compute summary statistics for a list of latencies in ms."""
    arr = np.array(latencies)
    return {
        "mean_ms": round(float(np.mean(arr)), 4),
        "median_ms": round(float(np.median(arr)), 4),
        "std_ms": round(float(np.std(arr)), 4),
        "min_ms": round(float(np.min(arr)), 4),
        "max_ms": round(float(np.max(arr)), 4),
        "p95_ms": round(float(np.percentile(arr, 95)), 4),
        "p99_ms": round(float(np.percentile(arr, 99)), 4),
        "total_ms": round(float(np.sum(arr)), 2),
        "num_trades": len(arr),
    }


def generate_figures(gnn_latencies, pp_latencies, output_dir: Path):
    """Generate latency distribution plots."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available - skipping figure generation")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    gnn_arr = np.array(gnn_latencies)
    pp_arr = np.array(pp_latencies)

    # =========================================================================
    # 1. Latency Distribution (Histogram)
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.hist(gnn_arr, bins=40, color="#00C896", alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.axvline(np.mean(gnn_arr), color="#008060", linestyle="--", linewidth=2,
               label=f"Mean: {np.mean(gnn_arr):.2f} ms")
    ax.set_title("GNN Inference Latency", fontsize=13, fontweight="bold")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Count")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    ax.hist(pp_arr, bins=40, color="#FF6B6B", alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.axvline(np.mean(pp_arr), color="#CC4444", linestyle="--", linewidth=2,
               label=f"Mean: {np.mean(pp_arr):.2f} ms")
    ax.set_title("pandapower Solve Latency", fontsize=13, fontweight="bold")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Count")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Latency Distribution — GNN vs pandapower", fontsize=15, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "latency_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # 2. Speedup Box Plot
    # =========================================================================
    fig, ax = plt.subplots(figsize=(8, 6))

    bp = ax.boxplot(
        [gnn_arr, pp_arr],
        tick_labels=["GNN", "pandapower"],
        patch_artist=True,
        widths=0.5,
    )

    colors = ["#00C896", "#FF6B6B"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    speedup = np.mean(pp_arr) / np.mean(gnn_arr)
    ax.set_title(
        f"Inference Latency Comparison (Speedup: {speedup:.0f}×)",
        fontsize=14, fontweight="bold",
    )
    ax.set_ylabel("Latency (ms)")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "latency_boxplot.png", dpi=150, bbox_inches="tight")
    plt.close()

    logger.info("Saved latency figures")


def run_speed_benchmark(num_trades: int = 500, warmup_trades: int = 20):
    """Run the full speed benchmark."""
    print("\n" + "=" * 70)
    print("  SPEED BENCHMARK - GNN vs pandapower")
    print("=" * 70)

    rng = np.random.default_rng(42)

    # -------------------------------------------------------------------------
    # 1. Set up grid with realistic profiles
    # -------------------------------------------------------------------------
    print("\n--- Setting up IEEE 13-bus feeder ---")
    net = create_ieee13_feeder()
    profiles = generate_synthetic_profiles(num_timesteps=96)

    # Attach profiles at a mid-day timestep (high solar generation)
    household_states = attach_profiles_to_network(net, profiles, timestep_idx=40)

    # Get baseline power flow
    baseline_pf = solve_power_flow(net)
    if not baseline_pf.converged:
        print("ERROR: Baseline power flow did not converge!")
        return

    bus_voltages = baseline_pf.bus_voltages
    line_loadings = baseline_pf.line_loadings

    # -------------------------------------------------------------------------
    # 2. Load GNN model
    # -------------------------------------------------------------------------
    print("\n--- Loading GNN model ---")
    gnn_engine = GNNInferenceEngine(checkpoint_path=str(GNN_CHECKPOINT))
    if not gnn_engine.model_loaded:
        print("WARNING: GNN model not loaded - will use pandapower fallback")
        print("Cannot benchmark GNN speed without a trained model.")
        return

    # -------------------------------------------------------------------------
    # 3. Generate trades
    # -------------------------------------------------------------------------
    print(f"\n--- Generating {num_trades} random trades ---")
    all_trades = generate_random_trades(num_trades + warmup_trades, rng)
    warmup = all_trades[:warmup_trades]
    trades = all_trades[warmup_trades:]

    # -------------------------------------------------------------------------
    # 4. Warmup (JIT compilation, cache warming)
    # -------------------------------------------------------------------------
    print(f"--- Warming up ({warmup_trades} trades) ---")
    benchmark_gnn(gnn_engine, net, bus_voltages, line_loadings, household_states, warmup)
    benchmark_pandapower(net, warmup)
    print("  Warmup complete")

    # -------------------------------------------------------------------------
    # 5. Benchmark GNN
    # -------------------------------------------------------------------------
    print(f"\n--- Benchmarking GNN ({num_trades} trades) ---")
    gnn_latencies = benchmark_gnn(
        gnn_engine, net, bus_voltages, line_loadings, household_states, trades,
    )
    gnn_stats = compute_latency_stats(gnn_latencies)

    # -------------------------------------------------------------------------
    # 6. Benchmark pandapower
    # -------------------------------------------------------------------------
    print(f"--- Benchmarking pandapower ({num_trades} trades) ---")
    pp_latencies = benchmark_pandapower(net, trades)
    pp_stats = compute_latency_stats(pp_latencies)

    # -------------------------------------------------------------------------
    # 7. Compute speedup
    # -------------------------------------------------------------------------
    speedup_mean = pp_stats["mean_ms"] / max(gnn_stats["mean_ms"], 0.001)
    speedup_median = pp_stats["median_ms"] / max(gnn_stats["median_ms"], 0.001)

    # -------------------------------------------------------------------------
    # 8. Print results
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  SPEED BENCHMARK RESULTS")
    print("=" * 70)

    header = f"{'Metric':<25} {'GNN (ms)':<20} {'pandapower (ms)':<20}"
    print(header)
    print("-" * 65)
    for metric in ["mean_ms", "median_ms", "std_ms", "min_ms", "max_ms", "p95_ms", "p99_ms"]:
        label = metric.replace("_ms", "").upper()
        print(f"  {label:<23} {gnn_stats[metric]:<20.4f} {pp_stats[metric]:<20.4f}")

    print("\n" + "-" * 65)
    print(f"  {'SPEEDUP (mean)':<23} {speedup_mean:.0f}x")
    print(f"  {'SPEEDUP (median)':<23} {speedup_median:.0f}x")
    print(f"  {'Total GNN time':<23} {gnn_stats['total_ms']:.1f} ms")
    print(f"  {'Total PP time':<23} {pp_stats['total_ms']:.1f} ms")
    print(f"  {'Trades benchmarked':<23} {num_trades}")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 9. Generate figures
    # -------------------------------------------------------------------------
    print("\n--- Generating figures ---")
    generate_figures(gnn_latencies, pp_latencies, FIGURES_DIR)

    # -------------------------------------------------------------------------
    # 10. Save results
    # -------------------------------------------------------------------------
    results = {
        "gnn_stats": gnn_stats,
        "pandapower_stats": pp_stats,
        "speedup_mean": round(speedup_mean, 1),
        "speedup_median": round(speedup_median, 1),
        "num_trades": num_trades,
        "warmup_trades": warmup_trades,
        "device": str(torch.device("cuda" if torch.cuda.is_available() else "cpu")),
    }

    results_path = FIGURES_DIR / "speed_results.json"
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    num_trades = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_speed_benchmark(num_trades=num_trades)

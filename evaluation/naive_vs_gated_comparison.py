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
"""

# Placeholder — to be implemented after GNN training is complete.
# See plan.md Phase 7 for full detail.

import logging

logger = logging.getLogger(__name__)


def run_comparison(
    num_timesteps: int = 96,
    data_path: str = None,
    gnn_checkpoint: str = None,
):
    """
    Run the naive vs gated comparison experiment.

    TODO: Implement after GNN training.
    """
    logger.info("Naive vs Gated comparison — not yet implemented")
    logger.info("Run this after completing GNN training (Phase 3)")
    raise NotImplementedError("Complete GNN training first (Phase 3)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_comparison()

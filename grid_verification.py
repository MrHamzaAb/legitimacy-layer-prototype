"""
grid_verification.py — Verify simulator output against analytical predictions.

Runs the Legitimacy Layer simulator at 20 seeds per cell across the 2x2
grid of configurations in Table VI, and compares the simulation mean
against the closed-form analytical prediction for each cell.

Reports per-cell:
  - analytical prediction
  - simulation mean across 20 seeds
  - simulation stdev across 20 seeds
  - absolute difference (|sim - analytical|)
  - PASS/FAIL against a 1.5 percentage point tolerance

This script is the authoritative verification artefact for Table VI of
the ICHCAI 2026 revision: the paper's claim that simulation agrees with
analytical prediction within +/- 1.5 pp is defensible only if every cell
passes when this script is run.

Usage:
    python grid_verification.py

Repository: https://github.com/MrHamzaAb/legitimacy-layer-prototype
"""

import statistics
from dataclasses import dataclass
from typing import Callable, List

from scipy.stats import beta as scipy_beta

from legitimacy_layer import (
    Directive,
    SimulationConfig,
    UncertaintyDist,
    run_simulation,
)


TOLERANCE_PP = 1.5  # percentage points
N_SEEDS = 20
N_DECISIONS = 1000


# ---------------------------------------------------------------------------
# Analytical prediction (mirrors analytical_prediction.py)
# ---------------------------------------------------------------------------

def analytical_escalate_rate(
    uncertainty_cdf: Callable[[float], float],
    p_contestation: float,
    p_low: float = 0.5,
    p_high: float = 0.3,
    p_critical: float = 0.2,
    p_reversibility: float = 0.5,
    low_threshold: float = 0.3,
    high_threshold: float = 0.6,
) -> float:
    """Closed-form ESCALATE rate derived from Algorithm 1's priority order."""
    p_c = p_contestation
    p_u_lt_low = uncertainty_cdf(low_threshold)
    p_u_le_high = uncertainty_cdf(high_threshold)
    p_u_gt_high = 1.0 - p_u_le_high

    contestation_escalate = p_c
    critical_escalate = (1 - p_c) * p_critical
    high_pool = (1 - p_c) * p_high
    low_pool = (1 - p_c) * p_low

    high_uncertain_escalate = high_pool * p_u_gt_high
    fallthrough_high = high_pool * p_u_le_high

    execute_async = low_pool * p_reversibility * p_u_le_high
    execute = low_pool * (1 - p_reversibility) * p_u_lt_low
    fallthrough_low = low_pool - execute_async - execute

    return (
        contestation_escalate
        + critical_escalate
        + high_uncertain_escalate
        + fallthrough_high
        + fallthrough_low
    )


def uniform_cdf(u: float) -> float:
    return max(0.0, min(1.0, u))


def beta_2_5_cdf(u: float) -> float:
    return float(scipy_beta.cdf(u, 2, 5))


# ---------------------------------------------------------------------------
# Cell definition and verification
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    label: str
    uncertainty_dist: UncertaintyDist
    uncertainty_cdf: Callable[[float], float]
    p_contestation: float


def simulate_cell(cell: Cell, n_seeds: int = N_SEEDS) -> List[float]:
    """Run the simulator at n_seeds different seeds; return % ESCALATE per run."""
    rates = []
    for seed in range(n_seeds):
        cfg = SimulationConfig(
            n_decisions=N_DECISIONS,
            random_seed=seed,
            p_contestation=cell.p_contestation,
            uncertainty_dist=cell.uncertainty_dist,
        )
        result = run_simulation(cfg)
        rates.append(result.directive_percentages[Directive.ESCALATE.value])
    return rates


def verify_cell(cell: Cell) -> dict:
    """Verify one grid cell and return a results dict."""
    sim_rates = simulate_cell(cell)
    sim_mean = statistics.mean(sim_rates)
    sim_stdev = statistics.stdev(sim_rates)
    analytical = 100.0 * analytical_escalate_rate(
        cell.uncertainty_cdf, cell.p_contestation
    )
    diff = abs(sim_mean - analytical)
    passed = diff <= TOLERANCE_PP
    return {
        "label": cell.label,
        "analytical": analytical,
        "sim_mean": sim_mean,
        "sim_stdev": sim_stdev,
        "sim_min": min(sim_rates),
        "sim_max": max(sim_rates),
        "diff_pp": diff,
        "passed": passed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CELLS = [
    Cell("Uniform x p_c=0.20",   UncertaintyDist.UNIFORM,   uniform_cdf,   0.20),
    Cell("Uniform x p_c=0.02",   UncertaintyDist.UNIFORM,   uniform_cdf,   0.02),
    Cell("Beta(2,5) x p_c=0.20", UncertaintyDist.BETA_2_5,  beta_2_5_cdf,  0.20),
    Cell("Beta(2,5) x p_c=0.02", UncertaintyDist.BETA_2_5,  beta_2_5_cdf,  0.02),
]


if __name__ == "__main__":
    print("=" * 78)
    print(" Table VI verification: simulator vs analytical prediction")
    print(f" {N_SEEDS} seeds per cell, {N_DECISIONS} decisions per seed, "
          f"tolerance = {TOLERANCE_PP} pp")
    print("=" * 78)
    print()

    results = [verify_cell(c) for c in CELLS]

    header = f"{'Cell':26s} {'Analytical':>11s} {'Sim mean':>11s} " \
             f"{'Sim stdev':>11s} {'|diff| pp':>11s}  {'Result':>6s}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['label']:26s} "
            f"{r['analytical']:10.2f}% "
            f"{r['sim_mean']:10.2f}% "
            f"{r['sim_stdev']:10.2f}% "
            f"{r['diff_pp']:10.2f}   "
            f"{'PASS' if r['passed'] else 'FAIL':>6s}"
        )
    print()

    all_passed = all(r["passed"] for r in results)
    if all_passed:
        print("All 4 cells agree with analytical prediction within "
              f"{TOLERANCE_PP} pp.")
    else:
        print("One or more cells exceeded tolerance. Diagnose before using "
              "Table VI numbers in the paper.")

    worst = max(r["diff_pp"] for r in results)
    print(f"Worst-case |sim - analytical| across grid: {worst:.2f} pp")

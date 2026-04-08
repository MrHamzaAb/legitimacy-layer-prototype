"""Reproducibility and integrity tests for the simulation."""

from legitimacy_layer.simulation import SimulationConfig, run_simulation


def test_simulation_deterministic():
    """Two runs with the same seed must produce identical results."""
    config = SimulationConfig(n_decisions=200, random_seed=0)
    r1 = run_simulation(config)
    r2 = run_simulation(config)
    assert r1.directive_counts == r2.directive_counts


def test_simulation_count():
    config = SimulationConfig(n_decisions=500, random_seed=1)
    result = run_simulation(config)
    assert len(result.instances) == 500


def test_simulation_percentages_sum_to_100():
    config = SimulationConfig(n_decisions=100, random_seed=7)
    result = run_simulation(config)
    total_pct = sum(result.directive_percentages.values())
    assert abs(total_pct - 100.0) < 0.01


def test_paper_seed_reproducible():
    """Canonical seed=42, n=1000 must match paper Table IV counts."""
    config = SimulationConfig(n_decisions=1_000, random_seed=42)
    result = run_simulation(config)
    counts = result.directive_counts
    assert counts["EXECUTE"] == 53
    assert counts["EXECUTE_ASYNC"] == 118
    assert counts["ESCALATE"] == 829
    assert counts["HALT"] == 0

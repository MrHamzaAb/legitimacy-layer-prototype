"""
main.py — Legitimacy Layer Research Prototype Entry Point.

Run this script to execute the full 1 000-decision simulation and display
the directive distribution summary (Table IV equivalent).

Usage
-----
    python main.py

The simulation is fully deterministic. Re-running with the same seed
produces identical output.
"""

from legitimacy_layer.simulation import SimulationConfig, print_summary, run_simulation


def main() -> None:
    config = SimulationConfig(
        n_decisions=1_000,
        random_seed=42,
        p_low=0.50,
        p_high=0.30,
        p_critical=0.20,
        p_contestation=0.20,
        audit_path="simulation_audit.jsonl",
    )

    result = run_simulation(config)
    print_summary(result)


if __name__ == "__main__":
    main()

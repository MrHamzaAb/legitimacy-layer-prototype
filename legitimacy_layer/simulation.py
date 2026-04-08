"""
simulation.py — Reproducible 1 000-decision Monte Carlo Simulation.

Implements the minimal simulation described in Section V-G of the paper.
All 1,000 decision instances are evaluated under fixed NORMAL_AUTONOMY mode,
matching the paper's assumption exactly and reproducing Table IV.

The governance mode state machine is intentionally not active during this
simulation. Its behaviour is demonstrated separately via the deterministic
mode transition sequence in Table V of the paper.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List

from .audit import AuditLog
from .controller import (
    Directive,
    GovernanceMode,
    ImpactClass,
    route_decision,
)


# ---------------------------------------------------------------------------
# Simulation configuration
# ---------------------------------------------------------------------------

@dataclass
class SimulationConfig:
    n_decisions: int = 1_000
    random_seed: int = 42

    # Impact class probabilities (must sum to 1.0)
    p_low: float = 0.50
    p_high: float = 0.30
    p_critical: float = 0.20

    # Contestation probability
    p_contestation: float = 0.20

    # Routing thresholds — passed directly to route_decision.
    # Defaults match the paper's canonical values (Section IV-C).
    # These are governance policy inputs, not architectural constants;
    # domain-specific calibration is a deployment concern (Section III-C).
    low_threshold: float = 0.30
    high_threshold: float = 0.60

    # Audit output path
    audit_path: str = "simulation_audit.jsonl"


# ---------------------------------------------------------------------------
# Decision instance
# ---------------------------------------------------------------------------

@dataclass
class DecisionInstance:
    decision_id: int
    uncertainty_score: float
    impact_class: ImpactClass
    reversibility_flag: bool
    contestation_signal: bool
    governance_mode: GovernanceMode
    directive: Directive


# ---------------------------------------------------------------------------
# Simulation results
# ---------------------------------------------------------------------------

@dataclass
class SimulationResult:
    config: SimulationConfig
    instances: List[DecisionInstance]
    directive_counts: Dict[str, int] = field(default_factory=dict)
    directive_percentages: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        total = len(self.instances)
        for d in Directive:
            self.directive_counts[d.value] = sum(
                1 for i in self.instances if i.directive == d
            )
        self.directive_percentages = {
            k: round(v / total * 100, 2) for k, v in self.directive_counts.items()
        }


# ---------------------------------------------------------------------------
# Main simulation entry point
# ---------------------------------------------------------------------------

def run_simulation(config: SimulationConfig = SimulationConfig()) -> SimulationResult:
    """
    Execute the full simulation and return structured results.

    All decisions are routed under fixed NORMAL_AUTONOMY mode, exactly
    as described in Section V-G of the paper. The governance mode state
    machine is not active during this simulation — it operates as a
    separate architectural component demonstrated in Table V.

    Parameters
    ----------
    config : SimulationConfig
        Simulation parameters. Use defaults for paper-reproducible output.

    Returns
    -------
    SimulationResult
        All decision instances and aggregate directive counts (Table IV).
    """
    rng = random.Random(config.random_seed)

    # Weighted impact class population
    impact_population = (
        [ImpactClass.LOW] * int(config.p_low * 100)
        + [ImpactClass.HIGH] * int(config.p_high * 100)
        + [ImpactClass.CRITICAL] * int(config.p_critical * 100)
    )

    # Fixed governance mode throughout — matches paper Section V-G exactly
    governance_mode = GovernanceMode.NORMAL_AUTONOMY

    audit_log = AuditLog(path=config.audit_path)
    instances: List[DecisionInstance] = []

    for decision_id in range(1, config.n_decisions + 1):
        # --- Sample inputs ---
        uncertainty = rng.uniform(0.0, 1.0)
        impact = rng.choice(impact_population)
        reversible = rng.random() < 0.5
        contested = rng.random() < config.p_contestation

        # --- Route decision (fixed NORMAL_AUTONOMY) ---
        directive = route_decision(
            uncertainty_score=uncertainty,
            impact_class=impact,
            reversibility_flag=reversible,
            contestation_signal=contested,
            governance_mode=governance_mode,
            low_threshold=config.low_threshold,
            high_threshold=config.high_threshold,
        )

        # --- Audit ---
        audit_log.append(
            uncertainty_score=uncertainty,
            impact_class=impact,
            reversibility_flag=reversible,
            contestation_signal=contested,
            governance_mode=governance_mode,
            directive=directive,
        )

        instances.append(
            DecisionInstance(
                decision_id=decision_id,
                uncertainty_score=uncertainty,
                impact_class=impact,
                reversibility_flag=reversible,
                contestation_signal=contested,
                governance_mode=governance_mode,
                directive=directive,
            )
        )

    return SimulationResult(
        config=config,
        instances=instances,
    )


# ---------------------------------------------------------------------------
# Decision trace (illustrative single-instance explanation)
# ---------------------------------------------------------------------------

def _trace_rule(instance: DecisionInstance, low_threshold: float, high_threshold: float) -> str:
    """Return a plain-English explanation of which rule fired for a decision."""
    from .controller import GovernanceMode, ImpactClass, Directive
    gm = instance.governance_mode
    ic = instance.impact_class
    u  = instance.uncertainty_score
    rev = instance.reversibility_flag
    con = instance.contestation_signal
    d   = instance.directive

    if gm == GovernanceMode.SAFE_HALT:
        return "Rule 1 — governance mode is SAFE_HALT"
    if gm == GovernanceMode.HUMAN_OVERSIGHT_REQUIRED:
        return "Rule 2 — governance mode is HUMAN_OVERSIGHT_REQUIRED"
    if con:
        return "Rule 3 — contestation signal is TRUE"
    if ic == ImpactClass.CRITICAL:
        return "Rule 4 — impact class is CRITICAL"
    if ic == ImpactClass.HIGH and u > high_threshold:
        return f"Rule 5 — impact HIGH and uncertainty {u:.3f} > high_threshold {high_threshold}"
    if rev and ic == ImpactClass.LOW and u <= high_threshold:
        return f"Rule 6 — reversible LOW-impact, uncertainty {u:.3f} ≤ high_threshold {high_threshold}"
    if ic == ImpactClass.LOW and u < low_threshold:
        return f"Rule 7 — LOW-impact and uncertainty {u:.3f} < low_threshold {low_threshold}"
    return "Rule 8 — default (no earlier rule matched)"


def print_decision_trace(result: SimulationResult, decision_id: int = 42) -> None:
    """
    Print a single decision trace showing inputs, matched rule, and directive.

    Illustrates the deterministic routing logic of Algorithm 1 on one
    concrete instance — useful for reviewers reading the prototype output.
    """
    instance = next(
        (i for i in result.instances if i.decision_id == decision_id), None
    )
    if instance is None:
        return

    rule = _trace_rule(instance, result.config.low_threshold, result.config.high_threshold)
    sep = "─" * 54

    print(f"  Decision Trace — Instance #{instance.decision_id}")
    print(f"  {sep}")
    print(f"  uncertainty_score  : {instance.uncertainty_score:.4f}")
    print(f"  impact_class       : {instance.impact_class.value}")
    print(f"  reversibility_flag : {instance.reversibility_flag}")
    print(f"  contestation_signal: {instance.contestation_signal}")
    print(f"  governance_mode    : {instance.governance_mode.value}")
    print(f"  {sep}")
    print(f"  Matched            : {rule}")
    print(f"  Directive issued   : {instance.directive.value}")
    print()


# ---------------------------------------------------------------------------
# Pretty-print summary (Table IV equivalent)
# ---------------------------------------------------------------------------

def print_summary(result: SimulationResult) -> None:
    """Print a formatted summary matching Table IV in the IEEE paper."""
    sep = "─" * 54

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║      Legitimacy Layer — Simulation Summary           ║")
    print("║      Table IV: Directive Distribution                ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print(f"  Decisions simulated : {result.config.n_decisions:>6,}")
    print(f"  Random seed         : {result.config.random_seed:>6}")
    print(f"  Governance mode     : NORMAL_AUTONOMY (fixed)")
    print(f"  Impact distribution : LOW {result.config.p_low:.0%} / "
          f"HIGH {result.config.p_high:.0%} / "
          f"CRITICAL {result.config.p_critical:.0%}")
    print(f"  Contestation prob.  : {result.config.p_contestation:.0%}")
    print(f"  Thresholds          : low={result.config.low_threshold} / "
          f"high={result.config.high_threshold}")
    print()
    print(f"  {sep}")
    print(f"  {'Directive':<20} {'Count':>8}   {'Percentage':>10}")
    print(f"  {sep}")

    for directive in Directive:
        count = result.directive_counts[directive.value]
        pct = result.directive_percentages[directive.value]
        bar = "█" * int(pct / 2)
        print(f"  {directive.value:<20} {count:>8}   {pct:>9.2f}%  {bar}")

    print(f"  {sep}")
    total = sum(result.directive_counts.values())
    print(f"  {'TOTAL':<20} {total:>8}   {'100.00%':>10}")
    print()
    print("  Note: elevated ESCALATE rate reflects conservative signal")
    print("  parameters (p_critical=0.2, p_contestation=0.2). In")
    print("  operational deployments these are domain-calibrated.")
    print("  See paper Section V-D and V-G for full discussion.")
    print()
    print(f"  Audit log written to: {result.config.audit_path}")
    print()

    # Decision trace — illustrates Algorithm 1 on one concrete instance
    print_decision_trace(result, decision_id=42)

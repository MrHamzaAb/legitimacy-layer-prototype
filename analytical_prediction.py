"""
analytical_prediction.py

Closed-form analytical prediction of Algorithm 1's routing distribution
under a specified governance signal configuration.

This script derives the expected proportion of decisions routed to each
directive (EXECUTE, EXECUTE_ASYNC, ESCALATE, HALT) from first principles,
traversing the priority-ordered rules of Algorithm 1 exactly as they are
specified in Section IV-C of the paper.

The analytical prediction serves as a verification reference for the
simulation output: under a matched configuration, the simulation's mean
escalation rate across seeds must agree with the analytical prediction
within Monte Carlo noise. Persistent disagreement indicates either a
bug in the simulator, a bug in the analytical model, or a configuration
mismatch between the two.

Reference: Sargent, R. G. (2013). "Verification and validation of
simulation models." Journal of Simulation, 7(1), 12-24.

Usage:
    python analytical_prediction.py

Repository: https://github.com/MrHamzaAb/legitimacy-layer-prototype
"""

from dataclasses import dataclass
from typing import Callable, Dict

from scipy.stats import beta as beta_dist


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """
    Full specification of a governance signal configuration.

    All parameters must be explicit; there are no defaults that could
    silently differ from the simulator's defaults.
    """
    # Impact class probabilities (must sum to 1.0)
    p_low: float
    p_high: float
    p_critical: float

    # Contestation signal probability
    p_contestation: float

    # Reversibility flag probability (independent of impact per paper §V-G)
    p_reversibility: float

    # Uncertainty distribution CDF: u -> P(uncertainty <= u)
    # This encapsulates both uniform[0,1] and Beta(a,b) in a single interface.
    uncertainty_cdf: Callable[[float], float]
    uncertainty_name: str  # human-readable label, e.g. "Uniform[0,1]"

    # Controller thresholds (paper §V-G defaults)
    low_threshold: float = 0.3
    high_threshold: float = 0.6

    def __post_init__(self):
        total = self.p_low + self.p_high + self.p_critical
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Impact probabilities must sum to 1.0, got {total:.6f}"
            )


# ---------------------------------------------------------------------------
# Uncertainty distributions
# ---------------------------------------------------------------------------

def uniform_cdf(u: float) -> float:
    """CDF of Uniform[0,1]: P(U <= u) = u for u in [0,1]."""
    return max(0.0, min(1.0, u))


def make_beta_cdf(a: float, b: float) -> Callable[[float], float]:
    """Return the CDF of Beta(a, b) as a callable."""
    return lambda u: float(beta_dist.cdf(u, a, b))


# ---------------------------------------------------------------------------
# Analytical prediction
# ---------------------------------------------------------------------------

def predict(cfg: Config) -> Dict[str, float]:
    """
    Compute the closed-form routing distribution under `cfg`.

    The derivation traces Algorithm 1's priority-ordered rules in order,
    subtracting the probability mass captured by each rule from the
    surviving pool before evaluating the next rule. This exactly mirrors
    the controller's evaluation order in Section IV-C.

    Returns a dict with keys:
        contestation_escalate, critical_escalate, high_uncertain_escalate,
        fallthrough_high, fallthrough_low, execute_async, execute,
        total_escalate, total
    All values are probabilities in [0,1] representing the expected
    proportion of decisions routed to each outcome.
    """
    # Shorthand
    p_c = cfg.p_contestation
    p_crit = cfg.p_critical
    p_high = cfg.p_high
    p_low = cfg.p_low
    p_rev = cfg.p_reversibility

    p_u_lt_low = cfg.uncertainty_cdf(cfg.low_threshold)       # P(u < 0.3)
    p_u_le_high = cfg.uncertainty_cdf(cfg.high_threshold)     # P(u <= 0.6)
    p_u_gt_high = 1.0 - p_u_le_high                           # P(u > 0.6)

    # --- Rule 3 (line 7 of Algorithm 1): contestation = TRUE -> ESCALATE ---
    contestation_escalate = p_c

    # Surviving pool: not contested
    remaining = 1.0 - p_c

    # --- Rule 4 (line 10): impact = CRITICAL -> ESCALATE ---
    critical_escalate = remaining * p_crit

    # Within the surviving pool, compute absolute HIGH and LOW shares.
    high_pool = remaining * p_high
    low_pool = remaining * p_low

    # --- Rule 5 (line 13): HIGH AND u > high_threshold -> ESCALATE ---
    high_uncertain_escalate = high_pool * p_u_gt_high

    # HIGH with u <= high_threshold is unmatched by Rules 6 and 7
    # (both require impact = LOW), so it falls through to the default.
    fallthrough_high = high_pool * p_u_le_high

    # --- Rule 6 (line 16): reversibility AND LOW AND u <= high_threshold ---
    #     -> EXECUTE_ASYNC
    execute_async = low_pool * p_rev * p_u_le_high

    # --- Rule 7 (line 19): LOW AND u < low_threshold -> EXECUTE ---
    # LOW with u < 0.3 AND rev=T is already caught by Rule 6 (since u<0.3
    # implies u<=0.6). So Rule 7 fires only when rev=F AND u<0.3.
    execute = low_pool * (1.0 - p_rev) * p_u_lt_low

    # --- Rule 8 (line 22): default -> ESCALATE ---
    # LOW cases reaching the default are those caught by neither Rule 6
    # nor Rule 7: equivalent to low_pool - (Rule 6 mass) - (Rule 7 mass).
    fallthrough_low = low_pool - execute_async - execute

    total_escalate = (
        contestation_escalate
        + critical_escalate
        + high_uncertain_escalate
        + fallthrough_high
        + fallthrough_low
    )

    total = total_escalate + execute_async + execute

    # Sanity check: probability mass must sum to 1.0
    assert abs(total - 1.0) < 1e-9, f"Mass leak: total={total}"

    return {
        "contestation_escalate": contestation_escalate,
        "critical_escalate": critical_escalate,
        "high_uncertain_escalate": high_uncertain_escalate,
        "fallthrough_high": fallthrough_high,
        "fallthrough_low": fallthrough_low,
        "execute_async": execute_async,
        "execute": execute,
        "total_escalate": total_escalate,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_report(cfg: Config, result: Dict[str, float]) -> str:
    """Pretty-print a single configuration's prediction."""
    lines = [
        f"Configuration: {cfg.uncertainty_name}, "
        f"p_contestation={cfg.p_contestation}",
        f"  Impact mix: LOW={cfg.p_low}, HIGH={cfg.p_high}, "
        f"CRITICAL={cfg.p_critical}",
        f"  Reversibility: p={cfg.p_reversibility}",
        f"  Thresholds: low={cfg.low_threshold}, high={cfg.high_threshold}",
        "",
        "  Routing breakdown (analytical):",
        f"    Contestation escalate         : "
        f"{100 * result['contestation_escalate']:6.2f}%",
        f"    CRITICAL escalate             : "
        f"{100 * result['critical_escalate']:6.2f}%",
        f"    HIGH + high-uncertainty       : "
        f"{100 * result['high_uncertain_escalate']:6.2f}%",
        f"    Fallthrough (HIGH-fallthrough): "
        f"{100 * result['fallthrough_high']:6.2f}%",
        f"    Fallthrough (LOW-fallthrough) : "
        f"{100 * result['fallthrough_low']:6.2f}%",
        f"    ---",
        f"    Total ESCALATE                : "
        f"{100 * result['total_escalate']:6.2f}%",
        f"    EXECUTE_ASYNC                 : "
        f"{100 * result['execute_async']:6.2f}%",
        f"    EXECUTE                       : "
        f"{100 * result['execute']:6.2f}%",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main: predict all four grid cells
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Shared impact and reversibility parameters (paper §V-G)
    COMMON = dict(
        p_low=0.5,
        p_high=0.3,
        p_critical=0.2,
        p_reversibility=0.5,
    )

    configs = [
        Config(
            uncertainty_cdf=uniform_cdf,
            uncertainty_name="Uniform[0,1]",
            p_contestation=0.2,
            **COMMON,
        ),
        Config(
            uncertainty_cdf=uniform_cdf,
            uncertainty_name="Uniform[0,1]",
            p_contestation=0.02,
            **COMMON,
        ),
        Config(
            uncertainty_cdf=make_beta_cdf(2, 5),
            uncertainty_name="Beta(2,5)",
            p_contestation=0.2,
            **COMMON,
        ),
        Config(
            uncertainty_cdf=make_beta_cdf(2, 5),
            uncertainty_name="Beta(2,5)",
            p_contestation=0.02,
            **COMMON,
        ),
    ]

    print("=" * 70)
    print("Analytical prediction of Algorithm 1 routing distribution")
    print("=" * 70)

    for cfg in configs:
        print()
        print(format_report(cfg, predict(cfg)))

    # Summary grid
    print()
    print("=" * 70)
    print("Summary: Total ESCALATE rate across 2x2 grid")
    print("=" * 70)
    print()
    print(f"{'':25s} {'p_contest=0.20':>18s} {'p_contest=0.02':>18s}")
    for name, cdf in [("Uniform[0,1]", uniform_cdf),
                      ("Beta(2,5)",   make_beta_cdf(2, 5))]:
        row = [f"{name:25s}"]
        for pc in [0.2, 0.02]:
            c = Config(
                uncertainty_cdf=cdf, uncertainty_name=name,
                p_contestation=pc, **COMMON,
            )
            row.append(f"{100 * predict(c)['total_escalate']:17.2f}%")
        print(" ".join(row))

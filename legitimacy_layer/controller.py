"""
controller.py — Core decision-routing algorithm (Algorithm 1).

Implements the Legitimacy Layer routing logic with strict priority ordering
as specified in the IEEE research paper.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------------------------

class ImpactClass(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GovernanceMode(str, Enum):
    NORMAL_AUTONOMY = "NORMAL_AUTONOMY"
    REDUCED_AUTONOMY = "REDUCED_AUTONOMY"
    HUMAN_OVERSIGHT_REQUIRED = "HUMAN_OVERSIGHT_REQUIRED"
    SAFE_HALT = "SAFE_HALT"


class Directive(str, Enum):
    EXECUTE = "EXECUTE"
    EXECUTE_ASYNC = "EXECUTE_ASYNC"
    ESCALATE = "ESCALATE"
    HALT = "HALT"


# ---------------------------------------------------------------------------
# Threshold Constants
# ---------------------------------------------------------------------------

LOW_UNCERTAINTY_THRESHOLD: float = 0.3
HIGH_UNCERTAINTY_THRESHOLD: float = 0.6


# ---------------------------------------------------------------------------
# Algorithm 1 — route_decision
# ---------------------------------------------------------------------------

def route_decision(
    uncertainty_score: float,
    impact_class: ImpactClass,
    reversibility_flag: bool,
    contestation_signal: bool,
    governance_mode: GovernanceMode,
    low_threshold: float = LOW_UNCERTAINTY_THRESHOLD,
    high_threshold: float = HIGH_UNCERTAINTY_THRESHOLD,
) -> Directive:
    """
    Route a decision to the appropriate directive.

    Implements Algorithm 1 from the Legitimacy Layer paper with strict
    priority ordering. Rules are evaluated top-to-bottom; the first
    matching condition wins.

    Parameters
    ----------
    uncertainty_score : float
        Model confidence expressed as uncertainty in [0, 1].
        0 = fully certain, 1 = fully uncertain.
    impact_class : ImpactClass
        Categorical severity of the decision's potential consequences.
    reversibility_flag : bool
        True if the action can be undone after execution.
    contestation_signal : bool
        True if an external agent or subsystem has raised an objection.
    governance_mode : GovernanceMode
        Current operating mode of the governance state machine.
    low_threshold : float
        Uncertainty below which LOW-impact actions may execute autonomously.
    high_threshold : float
        Uncertainty above which HIGH-impact actions must escalate.

    Returns
    -------
    Directive
        One of EXECUTE, EXECUTE_ASYNC, ESCALATE, or HALT.
    """
    # Rule 1 — SAFE_HALT overrides everything
    if governance_mode == GovernanceMode.SAFE_HALT:
        return Directive.HALT

    # Rule 2 — Human oversight mandated by current mode
    if governance_mode == GovernanceMode.HUMAN_OVERSIGHT_REQUIRED:
        return Directive.ESCALATE

    # Rule 3 — External contestation signal
    if contestation_signal:
        return Directive.ESCALATE

    # Rule 4 — Critical impact class always escalates
    if impact_class == ImpactClass.CRITICAL:
        return Directive.ESCALATE

    # Rule 5 — High impact with elevated uncertainty
    if impact_class == ImpactClass.HIGH and uncertainty_score > high_threshold:
        return Directive.ESCALATE

    # Rule 6 — Reversible low-impact action within acceptable uncertainty
    if (
        reversibility_flag
        and impact_class == ImpactClass.LOW
        and uncertainty_score <= high_threshold
    ):
        return Directive.EXECUTE_ASYNC

    # Rule 7 — Low-impact action with low uncertainty → full autonomy
    if impact_class == ImpactClass.LOW and uncertainty_score < low_threshold:
        return Directive.EXECUTE

    # Rule 8 — Default: escalate when no other rule matches
    return Directive.ESCALATE

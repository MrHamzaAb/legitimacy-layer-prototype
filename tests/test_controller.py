"""
Unit tests for Algorithm 1 (route_decision).

Each test corresponds to one rule in the strict priority ordering.
"""

import pytest
from legitimacy_layer.controller import (
    Directive,
    GovernanceMode,
    ImpactClass,
    route_decision,
)


# Convenience alias
def decide(
    uncertainty=0.5,
    impact=ImpactClass.LOW,
    reversible=True,
    contested=False,
    mode=GovernanceMode.NORMAL_AUTONOMY,
) -> Directive:
    return route_decision(uncertainty, impact, reversible, contested, mode)


# ---------------------------------------------------------------------------
# Rule 1 — SAFE_HALT → HALT
# ---------------------------------------------------------------------------

def test_rule1_safe_halt_returns_halt():
    assert decide(mode=GovernanceMode.SAFE_HALT) == Directive.HALT


def test_rule1_safe_halt_overrides_low_uncertainty():
    assert decide(uncertainty=0.0, mode=GovernanceMode.SAFE_HALT) == Directive.HALT


# ---------------------------------------------------------------------------
# Rule 2 — HUMAN_OVERSIGHT_REQUIRED → ESCALATE
# ---------------------------------------------------------------------------

def test_rule2_human_oversight_returns_escalate():
    assert decide(mode=GovernanceMode.HUMAN_OVERSIGHT_REQUIRED) == Directive.ESCALATE


def test_rule2_human_oversight_overrides_low_impact():
    assert (
        decide(
            uncertainty=0.1,
            impact=ImpactClass.LOW,
            mode=GovernanceMode.HUMAN_OVERSIGHT_REQUIRED,
        )
        == Directive.ESCALATE
    )


# ---------------------------------------------------------------------------
# Rule 3 — contestation_signal → ESCALATE
# ---------------------------------------------------------------------------

def test_rule3_contestation_returns_escalate():
    assert decide(uncertainty=0.1, impact=ImpactClass.LOW, contested=True) == Directive.ESCALATE


# ---------------------------------------------------------------------------
# Rule 4 — CRITICAL → ESCALATE
# ---------------------------------------------------------------------------

def test_rule4_critical_returns_escalate():
    assert decide(uncertainty=0.0, impact=ImpactClass.CRITICAL) == Directive.ESCALATE


# ---------------------------------------------------------------------------
# Rule 5 — HIGH + uncertainty > high_threshold → ESCALATE
# ---------------------------------------------------------------------------

def test_rule5_high_uncertain_returns_escalate():
    assert decide(uncertainty=0.7, impact=ImpactClass.HIGH) == Directive.ESCALATE


def test_rule5_high_certain_does_not_escalate_via_rule5():
    # Uncertainty below threshold — should not escalate via rule 5
    # Falls through to rule 8 (default ESCALATE) because not LOW
    result = decide(uncertainty=0.4, impact=ImpactClass.HIGH)
    assert result == Directive.ESCALATE  # rule 8 default


# ---------------------------------------------------------------------------
# Rule 6 — reversible LOW within threshold → EXECUTE_ASYNC
# ---------------------------------------------------------------------------

def test_rule6_reversible_low_returns_execute_async():
    assert decide(uncertainty=0.5, impact=ImpactClass.LOW, reversible=True) == Directive.EXECUTE_ASYNC


def test_rule6_irreversible_low_does_not_trigger():
    # Irreversible + uncertainty between thresholds → default ESCALATE
    assert decide(uncertainty=0.5, impact=ImpactClass.LOW, reversible=False) == Directive.ESCALATE


# ---------------------------------------------------------------------------
# Rule 7 — LOW + uncertainty < low_threshold → EXECUTE
# ---------------------------------------------------------------------------

def test_rule7_low_certain_returns_execute():
    assert decide(uncertainty=0.1, impact=ImpactClass.LOW, reversible=False) == Directive.EXECUTE


def test_rule7_boundary_below_low_threshold():
    assert decide(uncertainty=0.29, impact=ImpactClass.LOW, reversible=False) == Directive.EXECUTE


def test_rule7_boundary_at_low_threshold_does_not_execute():
    # uncertainty == low_threshold is NOT < low_threshold
    assert decide(uncertainty=0.3, impact=ImpactClass.LOW, reversible=False) != Directive.EXECUTE


# ---------------------------------------------------------------------------
# Rule 8 — default → ESCALATE
# ---------------------------------------------------------------------------

def test_rule8_default_escalate_high_low_uncertainty():
    # HIGH impact with uncertainty below high_threshold but not LOW → default
    assert decide(uncertainty=0.4, impact=ImpactClass.HIGH, reversible=False) == Directive.ESCALATE


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

def test_safe_halt_beats_human_oversight():
    assert (
        decide(mode=GovernanceMode.SAFE_HALT) == Directive.HALT
    )


def test_contestation_beats_low_uncertainty():
    assert decide(uncertainty=0.05, impact=ImpactClass.LOW, contested=True) == Directive.ESCALATE


def test_critical_beats_reversibility():
    assert decide(impact=ImpactClass.CRITICAL, reversible=True) == Directive.ESCALATE

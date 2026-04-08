"""Unit tests for the GovernanceStateMachine."""

import pytest
from legitimacy_layer.controller import GovernanceMode
from legitimacy_layer.state_machine import GovernanceStateMachine


def fresh() -> GovernanceStateMachine:
    return GovernanceStateMachine()


def test_initial_mode_is_normal_autonomy():
    sm = fresh()
    assert sm.mode == GovernanceMode.NORMAL_AUTONOMY


def test_halt_signal_transitions_to_safe_halt():
    sm = fresh()
    sm.update(halt_signal=True)
    assert sm.mode == GovernanceMode.SAFE_HALT


def test_safe_halt_is_absorbing_without_reset():
    sm = fresh()
    sm.update(halt_signal=True)
    sm.update(escalation_occurred=False)  # no reset
    assert sm.mode == GovernanceMode.SAFE_HALT


def test_operator_reset_lifts_safe_halt():
    sm = fresh()
    sm.update(halt_signal=True)
    assert sm.mode == GovernanceMode.SAFE_HALT
    sm.operator_reset()
    assert sm.mode == GovernanceMode.NORMAL_AUTONOMY


def test_escalation_accumulation_to_reduced():
    sm = fresh()
    for _ in range(GovernanceStateMachine.ESCALATION_TO_REDUCED):
        sm.update(escalation_occurred=True)
    assert sm.mode == GovernanceMode.REDUCED_AUTONOMY


def test_escalation_accumulation_to_oversight():
    sm = fresh()
    for _ in range(GovernanceStateMachine.ESCALATION_TO_OVERSIGHT):
        sm.update(escalation_occurred=True)
    assert sm.mode == GovernanceMode.HUMAN_OVERSIGHT_REQUIRED


def test_critical_signal_jumps_to_human_oversight():
    sm = fresh()
    sm.update(critical_signal=True)
    assert sm.mode == GovernanceMode.HUMAN_OVERSIGHT_REQUIRED


def test_halt_overrides_critical():
    sm = fresh()
    sm.update(halt_signal=True, critical_signal=True)
    assert sm.mode == GovernanceMode.SAFE_HALT


def test_non_escalation_reduces_counter():
    sm = fresh()
    # Build up escalation count to ESCALATION_TO_REDUCED - 1
    for _ in range(GovernanceStateMachine.ESCALATION_TO_REDUCED - 1):
        sm.update(escalation_occurred=True)
    assert sm.mode == GovernanceMode.NORMAL_AUTONOMY
    # One success — counter decreases
    sm.update(escalation_occurred=False)
    assert sm.mode == GovernanceMode.NORMAL_AUTONOMY


def test_history_records_transitions():
    sm = fresh()
    sm.update(halt_signal=True)
    sm.operator_reset()
    assert len(sm.history) == 2
    assert sm.history[0].to_mode == GovernanceMode.SAFE_HALT
    assert sm.history[1].to_mode == GovernanceMode.NORMAL_AUTONOMY


def test_status_dict_keys():
    sm = fresh()
    status = sm.status()
    assert "mode" in status
    assert "consecutive_escalations" in status
    assert "transition_count" in status
    assert "last_transition" in status

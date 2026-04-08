"""
state_machine.py — Governance Mode State Machine.

Implements a deterministic finite-state machine that tracks and transitions
the system's governance mode based on observed signals and thresholds.

Design invariants
-----------------
* SAFE_HALT is a terminal absorbing state; no automatic recovery.
* All transitions are explicit and logged.
* Operator acknowledgement is required to exit SAFE_HALT.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

from .controller import GovernanceMode


# ---------------------------------------------------------------------------
# Transition record
# ---------------------------------------------------------------------------

@dataclass
class Transition:
    from_mode: GovernanceMode
    to_mode: GovernanceMode
    reason: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class GovernanceStateMachine:
    """
    Deterministic governance mode state machine.

    State diagram
    -------------
    NORMAL_AUTONOMY
        ↓  escalation_count > escalation_threshold
    REDUCED_AUTONOMY
        ↓  critical_signal or halt_signal
    HUMAN_OVERSIGHT_REQUIRED
        ↓  halt_signal
    SAFE_HALT  (terminal — operator reset required)

    Any state → SAFE_HALT on halt_signal (highest priority).
    """

    # Thresholds
    ESCALATION_TO_REDUCED: int = 3     # consecutive escalations before reducing autonomy
    ESCALATION_TO_OVERSIGHT: int = 6   # consecutive escalations before requiring oversight

    def __init__(self) -> None:
        self._mode: GovernanceMode = GovernanceMode.NORMAL_AUTONOMY
        self._consecutive_escalations: int = 0
        self._history: List[Transition] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> GovernanceMode:
        return self._mode

    @property
    def history(self) -> List[Transition]:
        return list(self._history)

    def update(
        self,
        *,
        halt_signal: bool = False,
        critical_signal: bool = False,
        escalation_occurred: bool = False,
        operator_reset: bool = False,
    ) -> GovernanceMode:
        """
        Evaluate transition conditions and advance the state machine.

        Parameters
        ----------
        halt_signal : bool
            Immediate stop signal (e.g., safety subsystem trigger).
        critical_signal : bool
            A critical-impact event was detected.
        escalation_occurred : bool
            The last routing decision resulted in ESCALATE.
        operator_reset : bool
            Explicit operator action to recover from SAFE_HALT.

        Returns
        -------
        GovernanceMode
            The mode after evaluating all conditions.
        """
        # SAFE_HALT is absorbing — only operator reset can lift it
        if self._mode == GovernanceMode.SAFE_HALT:
            if operator_reset:
                self._transition(GovernanceMode.NORMAL_AUTONOMY, "Operator reset")
            return self._mode

        # Operator reset outside SAFE_HALT resets escalation counters
        if operator_reset:
            self._consecutive_escalations = 0

        # Priority 1 — halt signal overrides everything
        if halt_signal:
            self._consecutive_escalations = 0
            self._transition(GovernanceMode.SAFE_HALT, "Halt signal received")
            return self._mode

        # Priority 2 — critical signal forces human oversight
        if critical_signal and self._mode != GovernanceMode.HUMAN_OVERSIGHT_REQUIRED:
            self._consecutive_escalations = 0
            self._transition(
                GovernanceMode.HUMAN_OVERSIGHT_REQUIRED,
                "Critical signal detected",
            )
            return self._mode

        # Track consecutive escalations
        if escalation_occurred:
            self._consecutive_escalations += 1
        else:
            # Non-escalation resets counter (autonomous execution succeeded)
            self._consecutive_escalations = max(0, self._consecutive_escalations - 1)

        # Progressive autonomy reduction
        if self._consecutive_escalations >= self.ESCALATION_TO_OVERSIGHT:
            if self._mode != GovernanceMode.HUMAN_OVERSIGHT_REQUIRED:
                self._transition(
                    GovernanceMode.HUMAN_OVERSIGHT_REQUIRED,
                    f"Escalation count reached {self._consecutive_escalations}",
                )
        elif self._consecutive_escalations >= self.ESCALATION_TO_REDUCED:
            if self._mode == GovernanceMode.NORMAL_AUTONOMY:
                self._transition(
                    GovernanceMode.REDUCED_AUTONOMY,
                    f"Escalation count reached {self._consecutive_escalations}",
                )

        return self._mode

    def operator_reset(self) -> None:
        """
        Explicit operator action to recover from any non-NORMAL state.
        Required for SAFE_HALT exit; also clears escalation counters.
        """
        self.update(operator_reset=True)

    def status(self) -> dict:
        """Return a snapshot of the current machine state."""
        return {
            "mode": self._mode.value,
            "consecutive_escalations": self._consecutive_escalations,
            "transition_count": len(self._history),
            "last_transition": (
                {
                    "from": self._history[-1].from_mode.value,
                    "to": self._history[-1].to_mode.value,
                    "reason": self._history[-1].reason,
                    "timestamp": self._history[-1].timestamp,
                }
                if self._history
                else None
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, new_mode: GovernanceMode, reason: str) -> None:
        t = Transition(
            from_mode=self._mode,
            to_mode=new_mode,
            reason=reason,
        )
        self._history.append(t)
        self._mode = new_mode

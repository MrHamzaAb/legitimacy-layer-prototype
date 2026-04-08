"""
Legitimacy Layer — Runtime Governance Architecture
A research prototype for IEEE publication.
"""

from .controller import route_decision, Directive, ImpactClass, GovernanceMode
from .state_machine import GovernanceStateMachine
from .audit import AuditLog

__all__ = [
    "route_decision",
    "Directive",
    "ImpactClass",
    "GovernanceMode",
    "GovernanceStateMachine",
    "AuditLog",
]

# Legitimacy Layer — Runtime Governance Architecture

> **This is a prototype implementation for research purposes.**  
> Developed to accompany an IEEE research paper on runtime governance
> architectures for autonomous AI systems.

**This prototype demonstrates execution-time governance of AI decisions, not model lifecycle governance.**

---

## Overview

The **Legitimacy Layer** is a runtime governance framework that operates as
model-agnostic middleware between an AI decision system and its operational
environment. It addresses the *legitimacy gap* — the interval between
AI decision generation and operational execution during which no active
governance mechanism evaluates whether a decision should proceed, be
escalated, or be contested.

Rather than modifying the upstream AI model, the architecture evaluates
four runtime governance signals at the point of execution and routes each
decision to one of four directives.

The framework operates on four inputs per decision:

| Signal | Type | Description |
|---|---|---|
| `uncertainty_score` | float ∈ [0, 1] | Model-reported epistemic uncertainty |
| `impact_class` | {LOW, HIGH, CRITICAL} | Categorical consequence severity |
| `reversibility_flag` | bool | Whether the action can be undone |
| `contestation_signal` | bool | External objection raised by a subsystem or operator |

It produces a single **directive**:

| Directive | Meaning |
|---|---|
| `EXECUTE` | Proceed autonomously |
| `EXECUTE_ASYNC` | Proceed, but log for deferred human review |
| `ESCALATE` | Pause and transfer control to a human operator |
| `HALT` | Stop immediately; require explicit operator reset |

---

## Mapping to the IEEE Paper

### Algorithm 1 — `route_decision`

Implemented in [`legitimacy_layer/controller.py`](legitimacy_layer/controller.py).

The routing function applies eight rules in strict priority order:

```
1. governance_mode == SAFE_HALT          → HALT
2. governance_mode == HUMAN_OVERSIGHT    → ESCALATE
3. contestation_signal == TRUE           → ESCALATE
4. impact_class == CRITICAL              → ESCALATE
5. impact_class == HIGH AND
       uncertainty > HIGH_THRESHOLD      → ESCALATE
6. reversibility == TRUE AND
       impact_class == LOW AND
       uncertainty ≤ HIGH_THRESHOLD      → EXECUTE_ASYNC
7. impact_class == LOW AND
       uncertainty < LOW_THRESHOLD       → EXECUTE
8. default                               → ESCALATE
```

Default thresholds: `LOW_THRESHOLD = 0.3`, `HIGH_THRESHOLD = 0.6`.

### Table IV — Directive Distribution

Reproduced by running `python main.py`. All 1,000 decisions are evaluated
under fixed `NORMAL_AUTONOMY` mode, matching Section V-G of the paper exactly.

| Directive | Count | Percentage |
|---|---|---|
| EXECUTE | 53 | 5.3% |
| EXECUTE_ASYNC | 118 | 11.8% |
| ESCALATE | 829 | 82.9% |
| HALT | 0 | 0.0% |

**On the escalation rate.** The 82.9% ESCALATE rate is a direct consequence
of the conservative signal parameters used in the simulation: CRITICAL impact
at 20% of decisions (always escalates via Rule 4) and contestation probability
at 20% (always escalates via Rule 3). Together these two rules alone account
for the majority of escalations before uncertainty-based rules are even reached.

This reflects a deliberate Type II error-averse design posture: the architecture
is tuned to minimise missed escalations (false negatives) at the cost of
producing unnecessary escalations (false positives). In safety-critical systems,
the asymmetry between these error types justifies conservative defaults — an
unnecessary escalation imposes operator workload; a missed escalation may
produce irreversible harm. As noted in Section V-D of the paper, operational
deployments would configure contestation frequency and impact class distributions
to reflect domain-specific decision volumes and risk profiles. The routing
thresholds (`low_threshold`, `high_threshold`) are exposed as parameters in
`SimulationConfig` precisely to support this domain-specific calibration.

Escalation rates are therefore not fixed properties of the architecture, but outcomes of parameter calibration — allowing the system to balance safety (Type II error avoidance) against operational workload (Type I error cost) according to domain-specific governance requirements.

**HALT = 0** is correct and expected. The HALT directive is only issued when
`governance_mode == SAFE_HALT`, which is a state machine condition — not a
signal-level routing outcome. Under fixed `NORMAL_AUTONOMY` throughout the
simulation, HALT cannot be produced. This is consistent with the paper's
specification in Section IV-E.

---

## Project Structure

```
legitimacy_layer/
├── __init__.py          # Public API surface
├── controller.py        # Algorithm 1 — route_decision
├── state_machine.py     # Governance mode state machine (Fig. 2)
├── simulation.py        # 1 000-decision reproducible simulation (Table IV)
└── audit.py             # Append-only audit log (JSONL + CSV)
main.py                  # Simulation entry point
requirements.txt         # No third-party deps; pytest for tests
README.md
```

| Paper element | Implementation |
|---|---|
| Algorithm 1 | `legitimacy_layer/controller.py` → `route_decision()` |
| Fig. 2 — State machine | `legitimacy_layer/state_machine.py` → `GovernanceStateMachine` |
| Table IV — Simulation | `legitimacy_layer/simulation.py` → `run_simulation()` |
| Audit trail | `legitimacy_layer/audit.py` → `AuditLog` |

---

## How to Run

**Requirements:** Python 3.10 or later. No third-party packages required.

```bash
# Clone / download the repository, then:
python main.py
```

This runs the full 1 000-decision simulation with `random_seed=42` and
prints the directive distribution table. It also writes an audit log to
`simulation_audit.jsonl`.

### Use the API directly

```python
from legitimacy_layer import route_decision, ImpactClass, GovernanceMode

directive = route_decision(
    uncertainty_score=0.72,
    impact_class=ImpactClass.HIGH,
    reversibility_flag=False,
    contestation_signal=False,
    governance_mode=GovernanceMode.NORMAL_AUTONOMY,
)
print(directive)  # Directive.ESCALATE
```

### Use the state machine

```python
from legitimacy_layer import GovernanceStateMachine

sm = GovernanceStateMachine()
sm.update(escalation_occurred=True)   # accumulates
sm.update(escalation_occurred=True)
sm.update(escalation_occurred=True)
print(sm.mode)                         # REDUCED_AUTONOMY

sm.update(halt_signal=True)
print(sm.mode)                         # SAFE_HALT

sm.operator_reset()
print(sm.mode)                         # NORMAL_AUTONOMY
```

### Use the audit log

```python
from legitimacy_layer import AuditLog, ImpactClass, GovernanceMode, Directive

log = AuditLog(path="my_audit.jsonl")
log.append(
    uncertainty_score=0.45,
    impact_class=ImpactClass.LOW,
    reversibility_flag=True,
    contestation_signal=False,
    governance_mode=GovernanceMode.NORMAL_AUTONOMY,
    directive=Directive.EXECUTE_ASYNC,
)
log.export_csv("my_audit.csv")
```

---

## Example Output

```
╔══════════════════════════════════════════════════════╗
║      Legitimacy Layer — Simulation Summary           ║
║      Table IV: Directive Distribution                ║
╚══════════════════════════════════════════════════════╝

  Decisions simulated :  1,000
  Random seed         :     42
  Governance mode     : NORMAL_AUTONOMY (fixed)
  Impact distribution : LOW 50% / HIGH 30% / CRITICAL 20%
  Contestation prob.  : 20%
  Thresholds          : low=0.3 / high=0.6

  ──────────────────────────────────────────────────────
  Directive               Count   Percentage
  ──────────────────────────────────────────────────────
  EXECUTE                    53        5.30%  ██
  EXECUTE_ASYNC             118       11.80%  █████
  ESCALATE                  829       82.90%  █████████████████████████████████████████
  HALT                        0        0.00%
  ──────────────────────────────────────────────────────
  TOTAL                    1000      100.00%

  Note: elevated ESCALATE rate reflects conservative signal
  parameters (p_critical=0.2, p_contestation=0.2). In
  operational deployments these are domain-calibrated.
  See paper Section V-D and V-G for full discussion.

  Audit log written to: simulation_audit.jsonl

  Decision Trace — Instance #42
  ──────────────────────────────────────────────────────
  uncertainty_score  : 0.6499
  impact_class       : HIGH
  reversibility_flag : False
  contestation_signal: False
  governance_mode    : NORMAL_AUTONOMY
  ──────────────────────────────────────────────────────
  Matched            : Rule 5 — impact HIGH and uncertainty 0.650 > high_threshold 0.6
  Directive issued   : ESCALATE
```

Exact values are deterministic for `seed=42`. Re-running always produces identical output.

---

## Design Decisions

- **Standard library only.** No external dependencies beyond `pytest`.
- **Deterministic.** The same seed always produces the same output.
- **Append-only audit.** Each record is written immediately; the log
  cannot be modified retroactively.
- **No automatic recovery from SAFE_HALT.** Operator reset is required,
  enforcing human-in-the-loop for the most severe failure mode.
- **Strict priority ordering.** Rules are evaluated top-to-bottom with
  no ambiguity; the first matching condition wins.

---

## Citation

If you use this prototype in academic work, please cite the accompanying
IEEE paper. This repository provides a fully reproducible reference
implementation of Algorithm 1 and the simulation described in Table IV.

---

## License

MIT License. See `LICENSE` for details.

---

*This is a prototype implementation for research purposes.*

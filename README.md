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
| --- | --- | --- |
| `uncertainty_score` | float ∈ [0, 1] | Model-reported epistemic uncertainty |
| `impact_class` | {LOW, HIGH, CRITICAL} | Categorical consequence severity |
| `reversibility_flag` | bool | Whether the action can be undone |
| `contestation_signal` | bool | External objection raised by a subsystem or operator |

It produces a single **directive**:

| Directive | Meaning |
| --- | --- |
| `EXECUTE` | Proceed autonomously |
| `EXECUTE_ASYNC` | Proceed, but log for deferred human review |
| `ESCALATE` | Pause and transfer control to a human operator |
| `HALT` | Stop immediately; require explicit operator reset |

---

## Mapping to the IEEE Paper

### Algorithm 1 — `route_decision`

Implemented in [`legitimacy_layer/controller.py`](https://github.com/MrHamzaAb/legitimacy-layer-prototype/blob/main/legitimacy_layer/controller.py).

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
| --- | --- | --- |
| EXECUTE | 53 | 5.3% |
| EXECUTE_ASYNC | 118 | 11.8% |
| ESCALATE | 829 | 82.9% |
| HALT | 0 | 0.0% |

**On the escalation rate.** The 82.9% ESCALATE rate under the paper's baseline
parameters decomposes analytically across four routing sources:

| Source | Contribution |
| --- | --- |
| Rule 3 — contestation signal | 20.0 pp |
| Rule 4 — CRITICAL impact | 16.0 pp |
| Rule 5 — HIGH impact + uncertainty > high threshold | 9.6 pp |
| Rule 8 — default fallthrough (unmatched signal combinations) | 36.4 pp |
| **Total (analytical)** | **82.0%** |
| Simulation (seed=42, `main.py`) | 82.9% |

The default fallthrough (Rule 8) is the largest single contributor. It
captures two classes of unmatched signal combinations: HIGH-impact
decisions with uncertainty at or below the high threshold (14.4 pp),
and LOW-impact decisions that fail either the reversibility precondition
for EXECUTE_ASYNC or the low-uncertainty precondition for EXECUTE (22.0 pp).
This reflects the architecture's conservative failure posture specified in
Section IV-C of the paper: signal combinations not explicitly authorised
for autonomous or asynchronous execution are routed to human oversight
rather than resolved by a permissive default.

The escalation rate is therefore a controllable function of input regime
and rule-set design rather than a fixed property of the architecture.
Section V-G and Table VI of the paper characterise how the rate varies
across a 2×2 grid of uncertainty distributions and contestation
probabilities; the validation scripts below reproduce these results.

**HALT = 0** is correct and expected. The HALT directive is only issued when
`governance_mode == SAFE_HALT`, which is a state machine condition — not a
signal-level routing outcome. Under fixed `NORMAL_AUTONOMY` throughout the
simulation, HALT cannot be produced. This is consistent with the paper's
specification in Section IV-E.

---

## Validation Scripts

Three validation scripts at the repo root support the analytical and
verification claims made in the ICHCAI 2026 revision of the paper.

| Script | Purpose |
| --- | --- |
| `analytical_prediction.py` | Closed-form derivation of Algorithm 1's routing distribution across the 2×2 grid of configurations in Table VI. Does not run any simulation. |
| `grid_verification.py` | Runs the simulator at 20 seeds per cell across all four grid cells and asserts agreement with the analytical prediction within ±1.5 percentage points. |
| `seed_stability.py` | Reports mean, stdev, min, max, and range of the ESCALATE rate across 20 seeds per cell, establishing seed stability. |

Run all three:

```
python analytical_prediction.py
python grid_verification.py
python seed_stability.py
```

Expected result: `grid_verification.py` prints `PASS` for all four cells.
The worst-case observed difference between simulation and analytical
prediction is under 0.5 percentage points; the 1.5 pp tolerance is a
conservative bound.

---

## Project Structure

```
legitimacy_layer/
├── __init__.py             # Public API surface
├── controller.py           # Algorithm 1 — route_decision
├── state_machine.py        # Governance mode state machine (Fig. 2)
├── simulation.py           # 1,000-decision reproducible simulation (Table IV)
└── audit.py                # Append-only audit log (JSONL + CSV)
main.py                     # Simulation entry point (Table IV)
analytical_prediction.py    # Closed-form Table VI predictions
grid_verification.py        # Simulator vs analytical across Table VI grid
seed_stability.py           # Per-cell seed-stability analysis
requirements.txt            # scipy for validation scripts; pytest for unit tests
README.md
```

| Paper element | Implementation |
| --- | --- |
| Algorithm 1 | `legitimacy_layer/controller.py` → `route_decision()` |
| Fig. 2 — State machine | `legitimacy_layer/state_machine.py` → `GovernanceStateMachine` |
| Table IV — Simulation | `legitimacy_layer/simulation.py` → `run_simulation()` |
| Table VI — Grid predictions | `analytical_prediction.py` |
| Table VI — Grid verification | `grid_verification.py` |
| Audit trail | `legitimacy_layer/audit.py` → `AuditLog` |

---

## How to Run

**Requirements:** Python 3.10 or later. Install dependencies with:

```
pip install -r requirements.txt
```

The core prototype (`main.py`, `legitimacy_layer/`) uses only the Python
standard library. `scipy` is required only for the validation scripts.

### Reproduce Table IV

```
python main.py
```

This runs the full 1,000-decision simulation with `random_seed=42` and
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

### Select an alternative uncertainty distribution

The `uncertainty_dist` config parameter added for the ICHCAI 2026 revision
selects between Uniform[0,1] (paper default, preserves Table IV) and
Beta(2,5) (operational regime used in Table VI):

```python
from legitimacy_layer import SimulationConfig, UncertaintyDist, run_simulation

cfg = SimulationConfig(
    p_contestation=0.02,
    uncertainty_dist=UncertaintyDist.BETA_2_5,
)
result = run_simulation(cfg)
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

  Note: the 82.9% escalation rate decomposes as 20.0 pp contestation +
  16.0 pp CRITICAL + 9.6 pp HIGH+uncertainty + 36.4 pp default
  fallthrough. See paper Section V-G and Table VI for the analytical
  decomposition and operational-regime comparisons.

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

* **Minimal dependencies.** Core prototype uses the Python standard library
  only; `scipy` required only for validation scripts.
* **Deterministic.** The same seed always produces the same output.
* **Append-only audit.** Each record is written immediately; the log
  cannot be modified retroactively.
* **No automatic recovery from SAFE_HALT.** Operator reset is required,
  enforcing human-in-the-loop for the most severe failure mode.
* **Strict priority ordering.** Rules are evaluated top-to-bottom with
  no ambiguity; the first matching condition wins.
* **Conservative failure posture.** The rule set is deliberately
  non-exhaustive over the joint signal space; unmatched combinations
  route to the default (ESCALATE), failing toward human oversight
  rather than autonomous action.

---

## Citation

If you use this prototype in academic work, please cite the accompanying
IEEE paper. This repository provides a fully reproducible reference
implementation of Algorithm 1, the simulation described in Table IV,
and the analytical and simulation verification underlying Table VI.

---

## License

MIT License. See `LICENSE` for details.

---

*This is a prototype implementation for research purposes.*

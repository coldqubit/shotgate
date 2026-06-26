# ADR-0012: Structural oracles and circuit metrics in the assertion contract

- **Status:** Accepted
- **Date:** 2026-06-26

## Context

The nine assertion oracles all gate on the measured output distribution. Validating the
*circuit itself* (its depth, its gate set) was deferred in ADR-0008 because the assertion
contract, `evaluate(counts, shots)`, never received the circuit. Yet `telemetry.py` already
computes depth, size, and per-gate operation counts on every run, and circuit-structure
regressions are a real DevOps pain that distribution oracles cannot catch: a transpiler or
optimizer change that inflates the two-qubit gate count, an unexpected gate slipping in, or
a circuit that grew past a complexity budget.

## Decision

1. **Extend the assertion contract** to `evaluate(counts, shots, circuit_metrics=None)`. The
   nine distribution oracles ignore the new argument; the runner passes the circuit's
   telemetry (`depth`, `size`, `operations`, ...).
2. **Add two structural oracles:** `circuit_depth` (bound the authored circuit's depth via a
   `min`/`max` window) and `gate_set` (require the circuit to use only an `allowed` set of
   gate names; measurement, barrier, and similar structural operations are always permitted).
3. **Structural oracles set `needs_counts = False`.** A job whose assertions are all
   structural is gated with **no execution**: the runner skips the backend entirely, so the
   check runs with no shots, no QPU time, and no backend dependency.

## Consequences

- **+** A new, faster gating tier: static circuit-property checks that run on every commit,
  deterministically and free, below the simulation tier. A structural-only job needs only
  circuit parsing, not a simulator or QPU.
- **+** Reuses telemetry already collected, and catches complexity or basis regressions
  before execution. This extends the DevOps story (gate the artifact, not just the output)
  rather than chasing distribution-oracle breadth.
- **+** The `evaluate` contract change is backward compatible: the new argument is optional
  and the existing oracles and their callers are unaffected.
- **-** The metrics describe the **authored** circuit (as loaded), not the
  device-transpiled circuit, so the gate bounds what you wrote, not what the device runs.
  Gating the transpiled circuit would require the backend to expose it; deferred.
- **-** `gate_set` auto-allows `measure`/`barrier`/`snapshot`/`delay`; list only logical
  gates. An empty gate still executes (it may exist to capture counts under `--allow-empty`).

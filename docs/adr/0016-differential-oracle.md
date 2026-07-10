# ADR-0016: `differential` assertion, an oracle needing no declared expected distribution

- **Status:** Accepted
- **Date:** 2026-07-11

## Context

Every oracle shipped through v0.7.0 (`distribution_tvd`, `hellinger_fidelity`, `chi_square`,
`kl_divergence`, `state_probability`, `allowed_states`, `most_frequent_outcome`) compares the
measured counts against a declared, static `expected` distribution or a small set of allowed
states. That covers the common case (Bell, GHZ, Grover) where the correct output is known in
closed form, but it does not cover the case that motivates running a quantum circuit in the
first place: a circuit whose answer is exactly what is being computed has no `expected` to
write down. It also cannot catch a regression where the *implementation* changes (a different
backend, a different optimization level, a transpiler update) but no single run's distance to a
fixed ideal moves enough to trip a threshold, because both the old and new implementation are
being compared to the same static target rather than to each other.

The classical analogue is differential testing (also golden-master testing): run the same input
through two implementations, or two versions of one implementation, and assert they agree,
needing no independent oracle of truth. A feasibility spike confirmed the mechanism transfers
directly: two Aer simulation methods (statevector and matrix_product_state) on the same Bell
circuit agreed at TVD 0.0006, while a circuit with an injected bug (`cx` replaced by `cz`)
diverged from the correct one at TVD 0.502, an unambiguous separation.

## Decision

Add a `differential` assertion type. It has no `expected` field: instead, `against_job` names
another job **declared earlier** in the same workflow's job list, and the oracle bounds the
total variation distance between the current job's counts and that job's already-measured
counts (`max_distance`, default 0.05, same semantics as `distribution_tvd`).

Mechanically, this needs the runner (not just the oracle) to change, because every existing
oracle is a pure function of one job's own counts. `Runner.run()` now keeps a `name -> JobReport`
map of jobs already executed, in declaration order; when evaluating an assertion that has an
`against_job` attribute, the runner looks up that name in the map and passes its counts to
`evaluate()` as two new, generically-named, optional keyword arguments (`reference_counts`,
`reference_shots`) that only `DifferentialAssertion` consumes; every other oracle's call site
is unaffected. A reference that does not resolve (the name does not exist, names the same job,
or names a job declared *later*, since only already-completed jobs are in the map) is not a
schema error: `evaluate()` receives `reference_counts=None` and fails closed with a message
naming the missing job, exactly like a structural oracle fails closed on missing circuit
metrics (ADR-0007's fail-closed policy, extended to a new failure mode).

## Consequences

- **+** Tests circuits with no closed-form expected output, and catches an implementation
  regression (backend, optimization level, transpiler) that a static-expected oracle would not,
  since both sides of the comparison come from actually running the circuit.
- **+** No schema growth in `config.py`: `against_job` is a plain string naming a sibling job, not
  a second `BackendSpec`, so there is no circular import between `assertions.py` (which
  `config.py` imports) and `config.py`'s `BackendSpec`, and no new top-level schema section.
- **+** Composable with the existing example style: `examples/bell-state-differential` runs one
  circuit through two Aer methods (`statevector` vs `matrix_product_state`) with no `expected`
  anywhere in the workflow, measured at TVD 0.0006 on the shipped example.
- **-** Ordering-dependent: `against_job` must be declared earlier in the `jobs:` list. This is
  enforced at runtime (fail-closed), not at schema-parse time, because a `JobSpec` does not see
  its siblings during validation; a forward or self reference is caught at evaluation, not load.
- **-** Doubles the execution cost of whatever it is compared against (both jobs run for real),
  unlike a static-expected oracle that only executes the job under test.
- **-** Only bounds agreement between two measured distributions; it says nothing about whether
  either distribution is *correct*. It complements, and does not replace, the expected-distribution
  oracles where a known answer exists.

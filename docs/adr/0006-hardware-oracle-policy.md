# ADR-0006: chi_square is simulator-only; hardware gates use distance, fidelity, and structural oracles

- **Status:** Accepted
- **Date:** 2026-06-11

## Context

The v0.2 milestone ran the example gates on a real quantum processing unit (QPU)
for the first time (`ibm_fez`, 156-qubit Heron r2, 4096 shots per job). Two facts
came out of those runs:

1. Simulator-tight thresholds (total variation distance (TVD) ≤ 0.03, Hellinger
   fidelity ≥ 0.99, leakage ≤ 0.005) fail on a healthy device: the measured Bell
   TVD was 0.1284 and the GHZ-3 TVD 0.1536.
2. `chi_square` fails on hardware for a mechanical reason, not a tuning one. The
   non-gating diagnostic Bell job (`d8l592rqv2lc738621eg`) returned statistic
   1.5e17, dof 3, p-value 0.0000, while the four distance/structural oracles passed
   on the same counts (TVD 0.1350, fidelity 0.8650, leakage 0.1350, P(`00`) 0.4343).
   The ideal expected distribution `{00: 0.5, 11: 0.5}` assigns probability 0 to
   the error states `01`/`10`; the implementation floors expected counts at
   `_MIN_EXPECTED = 1e-12` to keep the statistic finite, so each of the 553 leaked
   shots contributes on the order of `observed^2 / 1e-12`. Against an ideal support,
   any device leakage forces rejection regardless of thresholds.

## Decision

1. **Hardware gates use the distance, fidelity, marginal, and structural oracles**
   (`distribution_tvd`, `hellinger_fidelity`, `state_probability`,
   `allowed_states`) with noise-aware thresholds (Bell: TVD ≤ 0.15, fidelity
   ≥ 0.85, leakage ≤ 0.15; full table in `docs/hardware-validation.md` section 4),
   encoded in the `examples/*-hardware` workflows.
2. **`chi_square` stays simulator-only** until a gate can declare a noise-aware
   expected distribution (a device error model with nonzero mass on the error
   states), which is out of scope for v0.2.
3. A **non-gating oracle-coverage diagnostic**
   (`examples/bell-state-hardware-oracle-coverage`) keeps measuring all five
   oracles on hardware so the exclusion stays evidence-based run over run.

## Consequences

- **+** The hardware gates pass a healthy device with measured margins of 0.0216
  (Bell TVD, the tightest) to 0.1357 (Grover P(`11`)) while still bounding leakage
  and fidelity, so they catch a broken circuit or mis-mapped qubits.
- **−** The formal hypothesis test is unavailable on hardware, so hardware gating
  loses the goodness-of-fit (GoF) guarantee and relies on distance bounds instead.
- Revisit when an error-model expected distribution exists (candidate for the v0.3
  error-mitigation work); the diagnostic's measurements will show when `chi_square`
  becomes viable on devices.

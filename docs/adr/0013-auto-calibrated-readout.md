# ADR-0013: Auto-calibrated readout error for chi_square / kl_divergence

- **Status:** Superseded by [ADR-0015](0015-chi-square-simulator-only.md)
- **Date:** 2026-06-27

## Context

ADR-0010 made `chi_square` and `kl_divergence` gateable on hardware by transforming the ideal
`expected` distribution through a per-qubit readout-error model (`readout_error: { p0, p1 }`).
But the parameters had to be supplied by hand, and a fixed guess is wrong: the 2026-06-26 QPU
run showed a hard-coded `0.07` over-predicting a cleaner device's error (~0.03 that day), so
the noise-aware `chi_square` still rejected (`docs/hardware-validation.md` section 10). The
readout error is not a free parameter, though: every device publishes it.

## Decision

Add `readout_error: auto`. When set, the oracle uses the readout calibration the **execution
actually had**, which the backend attaches to its result metadata as `readout_calibration`:

- The `ibm` backend reads `prob_meas1_prep0` / `prob_meas0_prep1` from `backend.properties()`,
  averaged over the circuit's active physical qubits (the device-average, v1).
- `local-aer` attaches its `noise` block's readout parameters when one is set.
- A noiseless simulator reports no calibration, so `auto` falls back to the ideal `expected`,
  i.e. the **plain** `chi_square`.

So a single workflow gates with the plain `chi_square` on a simulator and the
device-calibrated one on a QPU, with no per-device editing. The `evaluate` contract gains an
optional `backend_metadata` argument, which the runner passes from the result metadata.

## Consequences

- **+** No guessing: the gate uses the device's own published readout numbers, and the same
  workflow works on both a simulator (ideal expected) and hardware (calibrated).
- **+** Backward compatible: `readout_error` still accepts an explicit `{ p0, p1 }`; `auto`
  is opt-in; the other oracles ignore the new `backend_metadata` argument.
- **-** v1 averages the readout error over the active qubits into one `(p0, p1)`; per-qubit
  modelling using the transpile layout (mapping each counts bit to its physical qubit) is
  future work.
- **-** Readout error is only one error source; gate infidelity, decoherence, and crosstalk
  are not modelled, so a calibrated `chi_square` can still reject when non-readout error
  dominates. The distance and divergence oracles (TVD, fidelity, KL) remain the more robust
  hardware gates.
- **-** A calibrated gate's verdict depends on the day's calibration, so it is slightly less
  reproducible than a fixed threshold. Acceptable, and expected, for a hardware gate.

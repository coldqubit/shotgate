# ADR-0009: Declarative noise-model simulation on the local Aer backend

- **Status:** Accepted
- **Date:** 2026-06-26

## Context

The `*-hardware` example gates carry noise-aware thresholds (Bell: TVD <= 0.15, fidelity
>= 0.85, leakage <= 0.15; full table in `docs/hardware-validation.md` section 4). Until now
those thresholds could only be exercised against a real QPU, which is queued and metered:
there was no way to regression-test the noise-aware profiles in ordinary CI, and a profile
could silently rot (become too loose or too tight) between hardware runs.

A measurement on this codebase showed that an Aer noise model with a per-gate depolarizing
error plus a readout error reproduces the measured `ibm_fez` Bell regime closely (simulated
TVD 0.1223 against a measured 0.1284), so a simulated device is a faithful enough proxy to
gate the noise-aware thresholds offline.

## Decision

Add an optional, declarative `noise` block to a backend spec, consumed by the `local-aer`
backend:

```yaml
backend:
  provider: local-aer
  noise:
    depolarizing_1q: 0.004   # per single-qubit gate
    depolarizing_2q: 0.012   # per two-qubit gate
    readout_p0: 0.06         # P(measure 1 | prepared 0)
    readout_p1: 0.07         # P(measure 0 | prepared 1)
```

- `NoiseSpec` is a strict (`extra="forbid"`) pydantic model with each parameter bounded in
  `[0, 1]`; an all-zero spec is identical to the noiseless simulator.
- The spec rides through the backend `options` dict (set by the registry) so the `Backend`
  ABC stays minimal. The `local-aer` backend separates it out, builds a Qiskit Aer
  `NoiseModel` (uniform depolarizing on common 1- and 2-qubit gates, plus an assignment
  readout error), and records a `noisy` flag in the result metadata.
- Real-hardware backends ignore `noise` (a device carries its own noise).

## Consequences

- **+** The noise-aware `*-hardware` thresholds become testable in CI with zero QPU time; a
  `bell-state-noisy-sim` example gates a simulated-noisy Bell pair against hardware-profile
  bounds.
- **+** Contributors can develop and tune noise-aware thresholds offline before spending a
  hardware run.
- **-** The model is an approximate, uniform device proxy, not a calibration: it applies one
  depolarizing rate per gate class and one readout matrix to every qubit, and only to the
  enumerated gate names (others stay noiseless). It does not capture crosstalk, coherent
  errors, or qubit-specific calibration. It is a threshold-exercising tool, not a device
  digital twin.
- **-** `noise` is meaningful only for the `local-aer` backend; setting it on `ibm` is a
  silent no-op (documented).

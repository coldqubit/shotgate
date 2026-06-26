# ADR-0010: Noise-aware expected distributions for chi_square / kl_divergence on hardware

- **Status:** Accepted
- **Date:** 2026-06-26

## Context

ADR-0006 made `chi_square` simulator-only: against an ideal expected distribution that
assigns probability 0 to a device's error states, any hardware leakage drives the statistic
to ~1e17 and the p-value to 0, so it always rejects. ADR-0006 deferred the fix to "when a
gate can declare a noise-aware expected distribution (a device error model with nonzero
mass on the error states)". The same zero-support pathology applies to `kl_divergence`
(ADR-0008), which returns infinity.

A measurement on the real `ibm_fez` Bell diagnostic counts (`00`: 1779, `11`: 1764, `10`:
304, `01`: 249) confirmed the fix is tractable: transforming the ideal `{00: 0.5, 11: 0.5}`
through a per-qubit readout (assignment) error model with `P(1|0) = 0.07`, `P(0|1) = 0.075`
drops the chi-square statistic from `1.5e17` (p = 0) to `5.51` (dof 3, p = 0.138), so the
gate passes at alpha = 0.01. The readout parameters are a declared device characteristic,
not fit to the test counts, so the gate stays an honest hypothesis test.

## Decision

Add an optional `readout_error` block to `chi_square` and `kl_divergence`:

```yaml
- type: chi_square
  expected: { "00": 0.5, "11": 0.5 }   # the ideal, noiseless distribution
  readout_error: { p0: 0.07, p1: 0.075 }  # per-qubit assignment error, from calibration
  significance: 0.01
```

When `readout_error` is set, the oracle first transforms `expected` through an independent
per-qubit readout channel (`metrics.apply_readout_error`), producing a distribution with
nonzero mass on the error states, and tests the observed counts against *that*. The result
message is tagged `[noise-aware expected]`.

This partially lifts ADR-0006: `chi_square` (and `kl_divergence`) **can** gate on hardware
when given a calibration-derived readout model. The default remains the ideal expected, so
the simulator-only behaviour is unchanged unless `readout_error` is supplied.

## Consequences

- **+** Restores the goodness-of-fit and divergence oracles as hardware gates, backed by a
  measured result (chi-square p 0 -> 0.138 on real device counts).
- **+** The readout model is declared from device calibration, independent of the counts
  under test, so the gate does not "fit to pass": a genuinely broken run still rejects.
- **-** Only a readout (assignment) error channel is modelled, not depolarizing, coherent,
  or crosstalk error; for circuits whose hardware deviation is not readout-dominated, the
  noise-aware expected is incomplete and the gate may still reject. Distance and structural
  oracles remain the simplest hardware gates (ADR-0006).
- **-** The transform is `O(|support| * 2^n)` in the qubit count `n` and is guarded at 16
  qubits; it targets the small circuits typical of these gates.
- The simulated `noise` block (ADR-0009) and this `readout_error` block are independent: the
  former injects noise into a simulation, the latter shapes an expected distribution for a
  hypothesis test. They can be combined to validate the whole path offline.

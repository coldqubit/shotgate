# ADR-0014: Digital-twin (full noise-model) expected distribution for chi_square / kl_divergence

- **Status:** Accepted
- **Date:** 2026-06-30

## Context

ADR-0013 added `readout_error: auto`, transforming the ideal `expected` through the device's
published readout (assignment) calibration. It noted its own ceiling: readout error is only
one error source. On a real `ibm_fez` Bell run (4096 shots, 2026-06-27), the device-average
readout was p0 = 0.0066, p1 = 0.0214, predicting per-state leakage 0.0275, but the device
actually leaked 0.0530 into the |01>/|10> states. The readout-only expected therefore still
rejected: chi-square statistic 114.4, p-value 1.35e-24 against alpha = 0.01
(`docs/hardware-validation.md` section 11). The unmodelled mass is gate and decoherence
error, which a readout matrix cannot represent.

A reference simulation under the device's *full* calibrated noise model does represent it.
A spike on the same section-11 counts confirmed the direction: a noise model whose predicted
leakage matches the device (0.0511 vs the observed 0.0530) passes (statistic 8.32,
p-value 0.040), while a readout-only model (leakage 0.0275) and an over-noised model
(leakage 0.0747) both reject. So the expected has to carry the device's *actual* error
profile, not a guess and not readout alone.

## Decision

Add `noise_model: auto`. When set on `chi_square` or `kl_divergence`, the oracle compares the
measured counts against a **digital twin**: the same circuit simulated through the device's
full calibrated noise model (gate + readout + thermal relaxation). The backend builds the twin
and attaches it to result metadata as `noise_model_expected.distribution`:

- The `ibm` backend builds `NoiseModel.from_backend(device)` from the device's published
  properties and simulates the ISA circuit on Aer. This needs Qiskit Aer, which the `ibm`
  extra does not pull in, so the import is guarded: without Aer (or a usable model) the twin
  is absent and `auto` falls back to the ideal expected.
- `local-aer` reuses the `NoiseModel` it already built from the workflow's `noise` block.
- A noiseless run carries no twin, so `auto` falls back to the ideal `expected`, i.e. the
  plain test, exactly as `readout_error: auto` does.

The twin is computed by **sampling** the noise model at a high, fixed shot count
(`DEFAULT_TWIN_SHOTS = 200000`, overridable via `backend.options.twin_shots`), not by analytic
density-matrix marginalisation. Sampling returns the distribution in the circuit's own
classical-register format via `get_counts()`, keyed identically to the observed counts with no
manual marginalisation, qubit-to-clbit mapping, or bit-order handling, and includes readout
error exactly as applied at measurement. At 200000 shots the per-bin standard error is
<= 0.0011, an order of magnitude below the shot noise of a 4096-8192-shot hardware run, so the
twin perturbs the statistic negligibly. The twin simulator is seeded for reproducibility.
`noise_model` and `readout_error` are mutually exclusive on the same assertion (the schema
rejects setting both); the twin is the richer model. The expected-distribution computation is
the only place that needs Aer to *build* an expected, so it lives in the backends; the
validation core consumes the twin as plain probabilities and stays SDK-free.

## Consequences

- **+** Captures the gate and decoherence leakage `readout_error: auto` cannot, lowering the
  goodness-of-fit statistic toward the gateable range. On a real `ibm_marrakesh` run
  (2026-06-30) the statistic fell monotonically with model richness: ideal 4.54e15 ->
  readout-only 47.56 -> twin 32.40. In simulation, where the device *is* its model, the twin
  passes: on a fake IBM device a healthy run passes against its twin (p-value 0.70) while
  rejecting the ideal (p-value 0), and a drifted device (2-qubit depolarizing inflated to 0.10)
  is rejected against the twin (statistic 57.2, p-value 0).
- **-** On a real QPU `NoiseModel.from_backend` is an approximation of the device, not the
  device, so `chi_square` against the twin is not guaranteed to pass. On the `ibm_marrakesh`
  run the model under-predicted the leakage (0.0183 modelled vs 0.0208 observed) and modelled
  it as near-symmetric where the device was asymmetric, so the test still rejected at 4096
  shots even at statistic 32.40. That is the device-health reading working (the device deviates
  from its published calibration); the distance and divergence oracles (TVD 0.0254, fidelity
  0.9790, KL 0.0064 on the same run) remain the robust "close to ideal" hardware gates.
- **+** Backward compatible and opt-in: `readout_error` (fixed or `auto`) is unchanged, the
  other oracles ignore `noise_model`, and the schema field is additive (no `v1alpha1` bump).
- **-** It changes what the test *means*. `noise_model: auto` asks "does the device match its
  own calibrated model?", not "does it match the ideal?". That is a calibration-drift /
  device-health check: it passes a device behaving as calibrated and fails one that has
  drifted, which is useful but is a different question from algorithmic correctness. Document
  it as such; keep TVD/fidelity for "is the output close to ideal".
- **-** It pulls Aer into the expected. On the `ibm` backend the twin needs
  `shotgate[ibm,aer]` (or the `:latest-ibm` image, which bakes Aer in); without Aer the gate
  silently falls back to the ideal expected and rejects, so the dependency must be present for
  the feature to engage.
- **-** Mild circularity: a device is tested against its self-reported calibration, so a model
  that is itself miscalibrated could mask a real fault or flag a healthy device. The twin is an
  approximation of the device, not ground truth.
- **-** Heavier than a readout transform: it runs a high-shot simulation per twinned job.
  Negligible at the 5-8 qubit MVP scale; for large circuits the twin sampling cost (and Aer's
  noisy-simulation method) grows like the simulator itself.

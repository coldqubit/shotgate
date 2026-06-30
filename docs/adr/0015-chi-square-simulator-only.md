# ADR-0015: Limit chi_square to simulation; kl_divergence auto-readout; drop the noise-aware/twin modes

- **Status:** Accepted
- **Date:** 2026-06-30
- **Supersedes:** ADR-0010, ADR-0013, ADR-0014 (reaffirms ADR-0006)

## Context

Three successive attempts tried to make the goodness-of-fit oracles (`chi_square`,
`kl_divergence`) gate on real hardware against the *ideal* expected distribution, which
assigns zero probability to the device's error states:

- **ADR-0010** transformed the ideal through a hand-written per-qubit readout (assignment)
  error model (`readout_error: {p0, p1}`). A fixed guess is wrong for any given device-day.
- **ADR-0013** made it automatic (`readout_error: auto`), reading the device's published
  readout calibration. Readout error is only one source: on `ibm_fez` it predicted leakage
  0.0275 against an observed 0.0530, so `chi_square` still rejected (statistic 114).
- **ADR-0014** built a digital twin (`noise_model: auto`, `NoiseModel.from_backend`), the
  device's full calibrated noise model (gate + readout + thermal relaxation) simulated on the
  circuit. It captured the gate leakage the readout transform missed and dropped the statistic
  monotonically (on `ibm_marrakesh`: ideal 4.54e15 -> readout-only 47.56 -> twin 32.40), but
  still rejected: `from_backend` under-predicted the leakage (0.0183 modelled vs 0.0208
  observed) and modelled it as near-symmetric where the device was asymmetric.

The conclusion across all three: `chi_square` against an exact expected is a simulator
instrument. On hardware it either rejects on zero support or, once you bend the expected to
match the device, stops testing "did the circuit compute the right answer" and becomes a
fragile, model-dependent calibration check. The added schema surface (`readout_error`,
`noise_model`, twin shots) was complexity without a reliable hardware gate. `kl_divergence`,
by contrast, stays genuinely useful on hardware when its expected is readout-transformed: it
measures overlap and stayed finite and passing on the same runs (0.0064 bits on
`ibm_marrakesh`).

## Decision

- **`chi_square` is simulator-only.** It compares against the exact `expected` and fails
  closed on real hardware (`backend_metadata['simulator'] is False`) with guidance toward the
  noise-tolerant oracles. On a simulator it is unchanged.
- **`kl_divergence` is automatically readout-aware.** It transforms the ideal `expected`
  through the run's device readout calibration when the backend attaches one (a QPU) and uses
  the plain ideal otherwise (a simulator). No per-assertion configuration: the explicit
  `readout_error` knob is gone, the behaviour is automatic.
- **The `readout_error` and `noise_model` fields and the digital-twin machinery are removed**
  (`backends/digital_twin.py`, the `NoiseModel.from_backend` twin, twin-shot options). Setting
  either field raises a migration error pointing at this ADR and at pinning `shotgate==0.6.x`
  for anyone who wants to keep experimenting with the noise-aware/twin modes.
- Each backend reports `metadata['simulator']` (local-aer and Braket local / on-demand
  simulators `True`; a real IBM QPU and an unrecognised Braket cloud device `False`).
- The `shotgate.dev/v1alpha1` schema version is unchanged: this is a removal within an alpha
  API, surfaced as a clear validation error rather than a migration shim.

## Consequences

- **+** Smaller, honest surface: `chi_square` is the formal hypothesis test where it is exact
  (simulators), and hardware quality is gated by the oracles that tolerate device error
  (`distribution_tvd`, `hellinger_fidelity`, `allowed_states`, `expectation_value`, and the
  now-automatic readout-aware `kl_divergence`).
- **+** No dead-end knobs: the readout/twin options that never produced a reliable hardware
  gate are gone, and `kl_divergence` needs no configuration to work on a QPU.
- **+** Fail-closed (ADR-0007) on hardware gives a clear, actionable message instead of a
  guaranteed, mysterious rejection.
- **-** Breaking change: workflows that set `readout_error` or `noise_model` no longer parse.
  Mitigated by an explicit migration error and the permanent `0.6.x` release for the removed
  modes. Flagged `BREAKING` in the changelog; pre-1.0 so it bumps the MINOR (0.7.0).
- **-** The digital-twin code and its real-QPU validation are retired from the maintained
  surface. The evidence trail stays in `docs/hardware-validation.md` sections 9-12 and in the
  superseded ADRs, so the negative result is on record rather than re-litigated.
- **-** `Aer` is no longer pulled into any expected computation, so the `ibm` backend's
  hardware diagnostics no longer need `shotgate[ibm,aer]`; `kl_divergence`'s readout transform
  is pure-Python in the validation core.

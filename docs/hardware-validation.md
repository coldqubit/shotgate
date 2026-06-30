# Hardware Validation Plan (v0.2)

> **Goal of this milestone:** *validate the statistical gates against real quantum
> hardware.* shotgate's oracles are proven against the Aer simulator; this plan
> exercises them end-to-end on a real IBM quantum processing unit (QPU) through the
> hardened `ibm` backend.
>
> **Status: VALIDATED on real hardware.** On 2026-06-11 the three hardware gates ran
> on `ibm_fez` (156-qubit Heron r2, Open Plan instance) at 4096 shots each, via the
> `hardware-validation` GitHub workflow installing `shotgate[ibm]==0.1.1` from PyPI.
> All gates passed; measured values in [section 9](#9-measured-baseline-ibm_fez-2026-06-11),
> where all five oracles available at the v0.2 milestone (including a non-gating `chi_square`
> measurement) have a hardware data point. The oracles added since (`kl_divergence`,
> `shannon_entropy`, `expectation_value`, `most_frequent_outcome`, and the noise-aware
> `readout_error` variants) were exercised on hardware in the 2026-06-26 re-run,
> [section 10](#10-second-hardware-run-2026-06-26-the-v03-oracles-on-a-qpu).
> This document remains the runbook for re-running the validation on any device.

---

## 0. Why a separate plan

A noiseless simulator passes simulator-tight bounds (χ² p ≥ 0.01, total variation
distance (TVD) ≤ 0.03, fidelity ≥ 0.99). A real device will **not**: readout error, gate infidelity, decoherence,
and crosstalk shift the distribution. Validating on hardware therefore means two things:

1. The **plumbing** works: submit, transpile to the device ISA, retrieve counts from the
   right classical register, and surface them through the JUnit/JSON reports.
2. The **thresholds** are calibrated: gates pass on a healthy device and fail on a broken
   one, using noise-aware bounds (see [§4](#4-noise-aware-acceptance-criteria)).

## 1. Obtain access and a token

1. Create an account at the [IBM Quantum Platform](https://quantum.cloud.ibm.com/).
2. Create an API key from the dashboard (it is shown once: store it in a password
   manager). This is a 44-character IBM Cloud API key.
3. Copy your **instance CRN** from the [Instances](https://quantum.cloud.ibm.com/instances)
   page (format `crn:v1:bluemix:public:quantum-computing:<region>:a/<account>:<id>::`).
   On the Open Plan you have exactly one instance; the CRN pins the service to it and
   avoids any account-default ambiguity.
4. Export the key for shotgate (never commit it) and put the CRN in the workflow:

   ```bash
   export SHOTGATE_IBM_TOKEN="<your API key>"
   ```

   ```yaml
   defaults:
     backend:
       provider: ibm
       shots: 4096
       options:
         instance: "crn:v1:bluemix:public:quantum-computing:us-east:a/...::"
   ```

   The backend reads the token, in order, from: `backend.options.token`,
   `SHOTGATE_IBM_TOKEN`, `QISKIT_IBM_TOKEN`. The instance comes from
   `backend.options.instance` (omit it to let the service auto-select among the
   instances visible to the key). The current Runtime channel is
   `ibm_quantum_platform` (the legacy `ibm_quantum` channel was removed); override via
   `backend.options.channel` if needed.

## 2. Select a backend (device)

| Strategy | How | When |
| --- | --- | --- |
| **Least busy** | omit `backend.name` → `least_busy(operational=True, simulator=False)` | first runs; minimize queue |
| **Pinned device** | `backend: { name: ibm_brisbane }` (or another available device) | reproducibility; tracking one device over time |
| **Cloud simulator** | a simulator backend name | plumbing test without real-device noise |

Use the IBM-enabled image so the SDK is present:

```bash
podman run --rm -e SHOTGATE_IBM_TOKEN -v "$PWD:/work:Z" -w /work \
  ghcr.io/coldqubit/shotgate:latest-ibm \
  run examples/bell-state-hardware/workflow.yaml --backend ibm --junit report.xml --json report.json
```

## 3. Expected queue and cost

- **Queue:** shared devices can queue from seconds to hours. Pick `least_busy` and run
  small shot counts first. Keep circuits ≤ 3 qubits for these examples.
- **Cost:** under the IBM Quantum open plan, usage is metered in execution time and
  subject to a monthly allotment; small jobs (2–3 qubits, ≤ 4096 shots) are cheap but not
  free of quota. Budget a handful of jobs for the full section-5 matrix. Confirm current
  plan limits on the IBM dashboard before a batch run.

## 4. Noise-aware acceptance criteria

Per example, the simulator profile is tight; the **hardware profile** is what should pass
on a healthy current-generation device. Treat these as starting points and tighten once a
device baseline is measured. `chi_square` is intentionally **dropped on hardware**: the
ideal expected distribution assigns zero probability to the device's error states, so any
leakage forces rejection (mechanism in section 9); use distance/fidelity/structural
oracles instead.

| Example | Oracle | Simulator (tight) | Hardware (noise-aware) |
| --- | --- | --- | --- |
| **Bell** (`bell-state-hardware`) | TVD ≤ | 0.03 | **0.15** |
| | Hellinger fidelity ≥ | 0.99 | **0.85** |
| | leakage (`01`,`10`) ≤ | 0.0 | **0.15** |
| **GHZ-3** | TVD ≤ | 0.03 | **0.20** |
| | fidelity ≥ | 0.99 | **0.80** |
| | leakage ≤ | 0.005 | **0.20** |
| **Grover-2** | P(`11`) ≥ | 0.99 | **0.70** |
| | leakage ≤ | 0.01 | **0.30** |

These bounds assume that a 2-qubit Bell pair on a good device typically lands at
fidelity ≈ 0.9–0.98, and that GHZ-3 and Grover-2 add depth and two-qubit gates and
degrade further. They aim to pass a healthy device while still catching a genuinely
broken circuit or mis-mapped qubits.

The three `*-hardware` examples (`examples/bell-state-hardware`,
`examples/ghz-state-hardware`, `examples/grover-2q-hardware`) encode these hardware
profiles; they shipped with v0.2.0 and are the workflows the `hardware-validation`
CI job runs.

## 5. Validation matrix

Run the cartesian product and record the JSON report for each cell:

| Circuit | Backend | Shots |
| --- | --- | --- |
| Bell | `least_busy`, one pinned device | 1024, 4096 |
| GHZ-3 | same | 4096 |
| Grover-2 | same | 4096 |

For each cell capture: device name, `job_id` (in `report.json` under
`jobs[].metrics.backend_metadata`), per-oracle metric values, and pass/fail.

## 6. Pass/fail rubric

A device run **passes validation** when, for every example:

1. **Plumbing:** the job completes, counts are retrieved (no register-extraction error),
   and `report.json` / `report.xml` are produced with the expected per-assertion entries.
2. **Gates:** all assertions in the example's **hardware profile** pass.
3. **Sanity:** the dominant outcomes match theory (e.g. Bell mass concentrated on `00`/`11`;
   Grover's `11` is the modal outcome).

A run is **informative-fail** (expected, not a shotgate bug) when plumbing succeeds but a
gate fails *because the device is noisier than the profile*: this calibrates thresholds.
A run is a **defect** when plumbing fails (extraction error, wrong register, crash): file
an issue with the `job_id` and `report.json`.

## 7. Reading results back

- **JUnit** (`report.xml`): each assertion is a `<testcase>`; failures carry the metric in
  the message. Your CI test UI renders pass/fail per oracle.
- **JSON** (`report.json`): `jobs[].assertions[].metrics` holds the raw numbers
  (`tvd`, `fidelity`, `leakage`, `probability`), and `jobs[].metrics.backend_metadata`
  holds `backend_name`, `job_id`, and `channel` for traceability and cost attribution.
- **Counts**: `jobs[].counts` carries the raw device histogram for offline analysis.

## 8. Definition of done for v0.2

- [x] Bell / GHZ / Grover each run on at least one real IBM device and produce reports.
- [x] Hardware-profile thresholds calibrated so healthy-device runs pass reproducibly
      (all three section-4 profiles passed on first run; margins in section 9).
- [x] A documented device baseline (fidelity per example) committed for regression tracking
      (section 9).
- [x] The `ibm` backend label updated from "not yet validated" to "validated on `ibm_fez`,
      2026-06-11" in the README backends table and `CHANGELOG.md`.

## 9. Measured baseline (ibm_fez, 2026-06-11)

Device: `ibm_fez` (156-qubit Heron r2), Open Plan instance, channel
`ibm_quantum_platform`, transpilation `optimization_level=1`, 4096 shots per job,
package `shotgate[ibm]==0.1.1` installed from PyPI on a clean CI runner
([`hardware-validation` workflow](../.github/workflows/hardware-validation.yml)).
Each job consumed 3 s of QPU time (9 s total, against the Open Plan allotment of
10 min/month). Wall-clock per gate is queue-dominated: 1003 s (Bell), 303 s (GHZ),
18 s (Grover).

| Gate | Oracle | Measured | Threshold | Margin |
| --- | --- | --- | --- | --- |
| Bell (`d8l4labnn5bs738rk2s0`) | TVD | **0.1284** | <= 0.15 | 0.0216 |
| | Hellinger fidelity | **0.8716** | >= 0.85 | 0.0216 |
| | support leakage | **0.1284** | <= 0.15 | 0.0216 |
| GHZ-3 (`d8l4t5032u0s73f9gmn0`) | TVD | **0.1536** | <= 0.20 | 0.0464 |
| | Hellinger fidelity | **0.8463** | >= 0.80 | 0.0463 |
| | support leakage | **0.1536** | <= 0.20 | 0.0464 |
| Grover-2 (`d8l4vgj2d42s73cavamg`) | P(`11`) | **0.8357** | >= 0.70 | 0.1357 |
| | support leakage | **0.1643** | <= 0.30 | 0.1357 |

Raw counts (sanity check: dominant outcomes match theory in every case):

- **Bell:** `00`: 1793, `11`: 1777, `10`: 318, `01`: 208. Valid-state mass 0.8716;
  the `10` excess over `01` (318 vs 208) is consistent with asymmetric readout error.
- **GHZ-3:** `000`: 1784, `111`: 1683, `110`: 319, `001`: 236, rest < 25 each.
  Valid-state mass 0.8464. The two dominant error states differ from `000`/`111` by
  one bit flip, as expected from single-qubit readout/decay error; the
  two-or-more-bit-flip states are an order of magnitude rarer.
- **Grover-2:** `11`: 3423 (P = 0.8357), `10`: 425, `01`: 190, `00`: 58. The marked
  state is the modal outcome by a factor of 8 over the next state.

Observations for threshold tuning: the Bell TVD margin (0.0216) is the tightest of
the matrix. On a noisier device or a bad calibration day the Bell gate is the most
likely informative-fail; GHZ and Grover have comfortable headroom. No defect-class
failures occurred: counts extraction, register selection, and all three report
formats worked on the first hardware contact.

### Oracle coverage and the chi_square measurement

All five assertion oracles available at the v0.2 milestone were exercised on `ibm_fez`
(the four oracles added in later versions are simulator-tested only so far). Four are in
the gating hardware examples: `distribution_tvd` and `hellinger_fidelity` (Bell, GHZ),
`allowed_states` (all three), `state_probability` (Grover, on `11`). The fifth,
`chi_square`, is excluded from the gating examples and was instead measured by the
non-gating `bell-state-hardware-oracle-coverage` diagnostic (job
`d8l592rqv2lc738621eg`, 4096 shots, counts `00`: 1779, `11`: 1764, `10`: 304,
`01`: 249). On that single run the four distance/structural oracles passed
(TVD 0.1350, fidelity 0.8650, leakage 0.1350, P(`00`) 0.4343) while `chi_square`
returned statistic 1.5e17, dof 3, p-value 0.0000.

That divergence is the reason `chi_square` is simulator-only, and it is mechanical,
not a tuning artifact. The ideal Bell expected distribution `{00: 0.5, 11: 0.5}`
assigns probability 0 to the error states `01` and `10`. Pearson's statistic sums
`(observed - expected)^2 / expected` per basis state; `chi_square_statistic` floors
the expected count at `_MIN_EXPECTED = 1e-12` to stay finite, so each error state
contributes `observed^2 / 1e-12`: the `10` and `01` outcomes (304 and 249 counts, 553
of 4096 shots) contribute `(304^2 + 249^2) / 1e-12`, about 1.5e17, driving the p-value
to 0. That magnitude is set by the `1e-12` floor, not by the data; the rejection itself
is floor-independent, since 553 shots landing on outcomes the ideal model forbids send
the p-value to 0 for any reasonable floor. TVD, Hellinger fidelity, and support
leakage degrade gracefully on the
same counts because they measure distance or overlap, not a variance-normalised
deviation with a near-zero denominator. The fix for a chi_square hardware gate would
be a noise-aware expected distribution with nonzero mass on the error states (a
device error model), which is out of scope for v0.2; the distance and structural
oracles are the correct hardware gates.

## 10. Second hardware run (2026-06-26): the v0.3 oracles on a QPU

A re-run on 2026-06-26 with `shotgate[ibm]==0.3.0` from PyPI, `least_busy` selection,
4096 shots per job, channel `ibm_quantum_platform`. `least_busy` placed the Bell gate
on `ibm_kingston` (job `d8v7lp0pknjs73a0eomg`) and the GHZ, Grover, and oracle-coverage
jobs on `ibm_fez` (jobs `d8v7lsmmvj5c73eh963g`, `d8v7m31ropqc738bqisg`,
`d8v7mapropqc738bqjf0`). The three gating examples passed with more margin than the
2026-06-11 run, the devices being cleaner that day:

| Gate | Oracle | Measured | Threshold |
| --- | --- | --- | --- |
| Bell (`ibm_kingston`) | TVD | **0.0547** | <= 0.15 |
| | Hellinger fidelity | **0.9453** | >= 0.85 |
| | support leakage | **0.0547** | <= 0.15 |
| GHZ-3 (`ibm_fez`) | TVD | **0.0737** | <= 0.20 |
| | Hellinger fidelity | **0.9261** | >= 0.80 |
| | support leakage | **0.0737** | <= 0.20 |
| Grover-2 (`ibm_fez`) | P(`11`) | **0.9097** | >= 0.70 |
| | support leakage | **0.0903** | <= 0.30 |
| | most-frequent outcome | **`11`** (P 0.9097) | == `11` |

The `most_frequent_outcome` oracle (added after v0.2) is validated on hardware here:
the marked state is the modal outcome, as it must be whenever the P(`11`) gate holds.

### The oracles added after v0.2, measured on `ibm_fez`

The oracle-coverage diagnostic (Bell, counts `00`: 1897, `11`: 1948, `10`: 165, `01`: 86;
valid-state mass 0.9387) exercised the newer oracles:

| Oracle | Measured | Reading |
| --- | --- | --- |
| `expectation_value` `<Z0 Z1>` | **0.8774** | Z-correlation, degraded from the ideal 1 by leakage. Passed `>= 0.5`. |
| `shannon_entropy` | **1.328 bits** | Above the ideal 1 bit: leakage into `01`/`10` spreads the distribution. |
| `kl_divergence` (noise-aware) | **0.0412 bits** | With a `readout_error` model, passed `<= 0.1`. |
| `chi_square` (plain) | statistic **3.46e16**, p 0 | Rejects, as in section 9: the ideal expected forbids `01`/`10`. |
| `chi_square` (noise-aware) | statistic **184.2**, p 0 | See below. |

The noise-aware `chi_square` is the informative case. A fixed `readout_error` of
`p0 = p1 = 0.07` (representative, from the 2026-06-11 run) cut the statistic from
`3.46e16` to `184.2`, about 14 orders of magnitude (a factor of ~2e14), but it still
rejected: `ibm_fez` that day
was cleaner than 0.07 implies (valid-state mass 0.9387, so roughly 0.03 leakage per
qubit), so the 0.07 model over-predicted the error and, at 4096 shots, the mismatch is
still rejected. This confirms ADR-0010's condition that the readout parameters must come
from the device's own calibration, not a fixed guess. `kl_divergence` passed on the same
counts with the same model because it measures overlap, not a variance-normalised
deviation, so it tolerates an approximate error model where `chi_square` does not.

## 11. Auto-calibrated chi_square on a QPU (2026-06-27)

A re-run on 2026-06-27 with `shotgate[ibm]==0.5.0` validated `readout_error: auto` end to end
on `ibm_fez` (`least_busy`). The `ibm` backend read the device's published readout calibration
and averaged it over the two active qubits: `p0 = 0.0066` (P(read 1 | prep 0)), `p1 = 0.0214`
(P(read 0 | prep 1)). The oracle used those numbers rather than a guess (the message is tagged
`[noise-aware: device-average p0=0.007 p1=0.021]`), confirming the calibration plumbing works
on real hardware.

Diagnostic counts `00`: 1968, `11`: 1911, `10`: 129, `01`: 88 (valid-state mass 0.9470):

| Oracle | Measured | Reading |
| --- | --- | --- |
| `expectation_value` `<Z0 Z1>` | 0.8940 | Passed `>= 0.5`. |
| `shannon_entropy` | 1.2974 bits | Passed the 0.8-1.5 window. |
| `kl_divergence` (auto) | 0.0153 bits | Passed `<= 0.1` with the device calibration. |
| `chi_square` (plain) | statistic 2.44e16, p 0 | Rejects (zero-support). |
| `chi_square` (auto) | statistic 114.9, p 0 | Used the real calibration but still rejected. |

The auto `chi_square` is again the honest case, and now the cause is unambiguous: the device's
measured leakage is ~5.3% (TVD 0.053), but its readout error is only ~0.7% + 2.1% = ~2.8%. The
extra leakage is gate and decoherence error, which the readout-only model does not capture, so
the noise-aware expected still under-predicts the error states and `chi_square`, at 4096 shots,
rejects. This is exactly the limitation ADR-0013 states: a calibrated `chi_square` is usable
only when the device error is readout-dominated. `kl_divergence` passed on the same counts and
calibration because it measures overlap, not a variance-normalised deviation. The guidance
holds: gate hardware with the distance and divergence oracles; auto `chi_square` is a correct,
automatic refinement, not a universal hardware gate.

## 12. Digital-twin chi_square validation (2026-06-30)

Section 11 isolated the cause of the auto `chi_square` rejection: the readout-only expected
under-predicts the device's leakage because gate and decoherence error are unmodelled. ADR-0014
closes that gap with `noise_model: auto`, which compares the counts against a digital twin: the
same circuit simulated through the device's *full* calibrated noise model (gate + readout +
thermal relaxation). The mechanism is validated below; the numbers are reproducible.

On the section-11 `ibm_fez` counts (`00`: 1968, `11`: 1911, `10`: 129, `01`: 88; observed
leakage 0.0530), holding the expected against three error models:

| Expected model | Predicted leakage | chi-square | p-value | Verdict (alpha = 0.01) |
| --- | --- | --- | --- | --- |
| ideal (zero-support) | 0 | 2.44e16 | 0 | reject |
| readout-only auto (p0 0.0066, p1 0.0214) | 0.0275 | 114.4 | 1.35e-24 | reject |
| full noise model (2-qubit depolarizing 0.05) | 0.0511 | 8.32 | 0.040 | pass |

The test passes only when the model's predicted leakage matches the device's actual leakage
(0.0511 vs 0.0530); a readout-only model under-predicts and an over-noised model (2-qubit
depolarizing 0.10, predicted leakage 0.0747) rejects in the other direction (statistic 33.5).
So the twin has to carry the device's true error profile, which `NoiseModel.from_backend`
supplies from the device's published per-gate and readout properties.

End-to-end on a fake IBM device (`FakeManilaV2`, Bell, 4096 shots, twin sampled at 200000
shots, `NoiseModel.from_backend`), which exercises the full backend path the `ibm` backend
takes on real hardware:

- The twin distribution is `00`: 0.4842, `01`: 0.0170, `10`: 0.0169, `11`: 0.4819: it
  reproduces the device's ~3.4% leakage that the ideal assigns zero.
- A healthy run (the device behaving as its model) passes against the twin (statistic 1.41,
  p-value 0.70) while rejecting the ideal (statistic 1.13e16, p-value 0).
- A drifted device (2-qubit depolarizing inflated to 0.10) is rejected against the twin
  (statistic 57.2, p-value 0). The gate detects the drift, which is its purpose: `noise_model:
  auto` is a calibration-drift / device-health check, passing a device that matches its
  calibration and failing one that has degraded past it.

In simulation, where the device *is* its model, this confirms `noise_model: auto` passes where
`readout_error: auto` rejects, at the cost of changing the question from "matches the ideal?"
to "matches its own calibrated model?".

### On a real QPU (`ibm_marrakesh`, 2026-06-30)

The same diagnostic ran on `ibm_marrakesh` (`least_busy`) with `shotgate[ibm,aer]==0.6.0`, which
built the twin from the live device via `NoiseModel.from_backend` and simulated it at 200000
shots. The plumbing works end to end on real hardware: the twin was attached and the oracle used
it (the message is tagged `[noise-aware: twin device-noise-model:ibm_marrakesh]`). Diagnostic
counts `00`: 2067, `11`: 1944, `10`: 64, `01`: 21 (observed leakage 0.0208), twin distribution
`00`: 0.4911, `01`: 0.0094, `10`: 0.0089, `11`: 0.4906 (modelled leakage 0.0183):

| chi_square expected | statistic | p-value | Verdict (alpha = 0.01) |
| --- | --- | --- | --- |
| ideal (zero-support) | 4.54e15 | 0 | reject |
| readout-only auto (p0 0.0029, p1 0.0112) | 47.56 | 0 | reject |
| digital twin (`NoiseModel.from_backend`) | 32.40 | 0 | reject |

The statistic falls monotonically as the expected model gets richer (4.54e15 -> 47.56 -> 32.40):
the twin does capture gate leakage the readout transform misses, dropping the statistic ~14
orders below the plain test and a further third below the readout-only model. But it did not
cross the threshold, for two compounding reasons. The `from_backend` model under-predicts the
device's leakage (0.0183 modelled vs 0.0208 observed), and it predicts a near-symmetric error
(twin `01` 0.0094 ~ `10` 0.0089) where the device is markedly asymmetric (observed `10` 64 vs
`01` 21). The residual mismatch concentrates in the small-expected-count error bins, which a
goodness-of-fit test at 4096 shots punishes. This is the device-health reading working as
intended: the device deviates from its own published calibration, and a strict test flags it.

So on a clean device the twin is the correct direction and a strict calibration-drift gate, but
`from_backend` is an approximation of the hardware, not the hardware itself, so `noise_model:
auto` `chi_square` is not guaranteed to pass on a real QPU. The distance and divergence oracles
remain the robust hardware gates: on this run TVD was 0.0254, Hellinger fidelity 0.9790, and the
readout-aware `kl_divergence` 0.0064 bits, all passing. The Bell, GHZ, and Grover hardware gates
in the same dispatch passed on `ibm_fez`.

### Outcome: the noise-aware modes were retired in 0.7.0

Sections 9-12 are the record of three attempts to make `chi_square` gate against the *ideal*
expected on real hardware: a readout transform (ADR-0010), auto-calibrated readout (ADR-0013),
and the full `NoiseModel.from_backend` digital twin (ADR-0014). The twin captured the gate
leakage the readout transform missed but still did not gate reliably, because a published noise
model is only an approximation of the device. The conclusion (ADR-0015): `chi_square` is a
simulator instrument and now fails closed on hardware; `kl_divergence` keeps the readout
transform but applies it automatically (no knob); the `readout_error`/`noise_model` options and
the twin code were removed. These sections stay as the evidence behind that decision. To run the
removed modes, pin `shotgate==0.6.x`.

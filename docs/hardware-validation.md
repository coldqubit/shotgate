# Hardware Validation Plan (v0.2)

> **Goal of this milestone:** *validate the statistical gates against real quantum
> hardware.* shotgate's oracles are proven against the Aer simulator; this plan
> exercises them end-to-end on a real IBM QPU through the hardened `ibm` backend.
>
> **Status: VALIDATED on real hardware.** On 2026-06-11 the three hardware gates ran
> on `ibm_fez` (156-qubit Heron r2, Open Plan instance) at 4096 shots each, via the
> `hardware-validation` GitHub workflow installing `shotgate[ibm]==0.1.1` from PyPI.
> All gates passed; measured values in [section 9](#9-measured-baseline-ibm_fez-2026-06-11).
> This document remains the runbook for re-running the validation on any device.

---

## 0. Why a separate plan

A noiseless simulator passes simulator-tight bounds (χ² p ≥ 0.01, TVD ≤ 0.03,
fidelity ≥ 0.99). A real device will **not**: readout error, gate infidelity, decoherence,
and crosstalk shift the distribution. Validating on hardware therefore means two things:

1. The **plumbing** works — submit, transpile to the device ISA, retrieve counts from the
   right classical register, and surface them through the JUnit/JSON reports.
2. The **thresholds** are calibrated — gates pass on a healthy device and fail on a broken
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
         instance: "crn:v1:bluemix:public:quantum-computing:us-east:a/…::"
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
  free of quota. Budget a handful of jobs for the full matrix below. Confirm current plan
  limits on the IBM dashboard before a batch run.

## 4. Noise-aware acceptance criteria

Per example, the simulator profile is tight; the **hardware profile** is what should pass
on a healthy current-generation device. Treat these as starting points and tighten once a
device baseline is measured. `chi_square` is intentionally **dropped on hardware** — with
thousands of shots it over-rejects under coherent device error; use distance/fidelity/
structural oracles instead.

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

Rationale: a 2-qubit Bell pair on a good device typically lands at fidelity ≈ 0.9–0.98;
GHZ-3 and Grover-2 add depth/two-qubit gates and degrade further. The bounds above aim to
pass a healthy device while still catching a genuinely broken circuit or mis-mapped qubits.

The `examples/bell-state-hardware/workflow.yaml` already encodes the Bell hardware
profile. Create `*-hardware` variants for GHZ and Grover from the table above before the
run.

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
gate fails *because the device is noisier than the profile* — this calibrates thresholds.
A run is a **defect** when plumbing fails (extraction error, wrong register, crash) — file
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

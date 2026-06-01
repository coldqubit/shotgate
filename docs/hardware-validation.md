# Hardware Validation Plan (v0.2)

> **Goal of this milestone:** *validate the statistical gates against real quantum
> hardware.* shotgate's oracles are proven against the Aer simulator; this plan
> exercises them end-to-end on a real IBM QPU through the hardened `ibm` backend.
>
> **Status:** groundwork only. The `ibm` backend is **implemented but not yet validated
> on hardware**. No QPU runs have been performed. This document is the runbook a
> maintainer follows once a token is available.

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
2. Copy your API token from the dashboard.
3. Export it for shotgate (never commit it):

   ```bash
   export SHOTGATE_IBM_TOKEN="<your token>"
   ```

   The backend reads, in order: `backend.options.token`, `SHOTGATE_IBM_TOKEN`,
   `QISKIT_IBM_TOKEN`. The current Runtime channel is `ibm_quantum_platform` (the legacy
   `ibm_quantum` channel was removed); override via `backend.options.channel` if needed.

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

- [ ] Bell / GHZ / Grover each run on at least one real IBM device and produce reports.
- [ ] Hardware-profile thresholds calibrated so healthy-device runs pass reproducibly.
- [ ] A documented device baseline (fidelity per example) committed for regression tracking.
- [ ] The `ibm` backend label updated from "not yet validated" to "validated on \<device\>,
      \<date\>" in the README backends table and `CHANGELOG.md`.

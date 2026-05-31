# Getting Started

This walkthrough takes you from zero to a passing quantum quality gate in a few
minutes, using only Podman (no host Python, qiskit, or terraform).

## Prerequisites

- [Podman](https://podman.io/) 4+ (`podman --version`).
- Optional: `qemu-system-x86_64` + `/dev/kvm` for the VM tier.
- This repository checked out.

## 1. Build the image

```bash
make build         # podman build -t qforge:dev .
```

This bakes qiskit + the Aer simulator into the image, so the default `local-aer`
backend works fully offline.

## 2. Run your first gate

```bash
make run WORKFLOW=examples/bell-state/workflow.yaml
```

You'll see a Rich table of assertion results and the process will exit `0`. A JUnit
`report.xml` and `report.json` are written to the repo root.

## 3. Read the workflow

[`examples/bell-state/workflow.yaml`](../examples/bell-state/workflow.yaml) declares a
Bell pair and five statistical assertions. Open it alongside the
[workflow spec](workflow-spec.md) and the [assertion catalog](assertions.md).

## 4. Write your own

Create `my-workflow.yaml`:

```yaml
apiVersion: qforge.dev/v1alpha1
kind: QuantumWorkflow
metadata:
  name: my-first-gate
defaults:
  backend: { provider: local-aer, shots: 4096, seed: 1 }
jobs:
  - name: plus-state
    circuit:
      format: qasm2
      inline: |
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[1];
        creg c[1];
        h q[0];
        measure q -> c;
    assertions:
      - type: state_probability
        state: "0"
        min: 0.45
        max: 0.55
```

Validate then run it:

```bash
make validate WORKFLOW=my-workflow.yaml      # schema check only
make run      WORKFLOW=my-workflow.yaml      # execute + gate
```

## 5. Target real hardware (optional)

```bash
export QFORGE_IBM_TOKEN=...      # from your IBM Quantum account
podman run --rm -e QFORGE_IBM_TOKEN -v "$PWD:/work:Z" -w /work qforge:dev \
  run my-workflow.yaml --backend ibm
```

(Loosen thresholds for device noise — see the [pipeline guide](pipeline.md#1-the-hybrid-pipeline).)

## 6. Run with VM-grade isolation (optional)

```bash
make vm-up WORKFLOW=examples/ghz-state/workflow.yaml
```

Boots a throwaway KVM micro-VM that runs qforge in Podman *inside* the VM and writes
the report back. See [`infra/qemu`](../infra/qemu/README.md).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `backend 'local-aer' ... dependencies are not installed` | Use the image (`make build`), or `pip install 'qforge[aer]'`. |
| `:Z` mount errors on non-SELinux hosts | Drop `:Z` from the `-v` flag. |
| QASM parse error | Ensure `include "qelib1.inc";` and a `creg`/`measure` (or omit measurement and qforge appends `measure_all`). |
| VM won't boot | Check `/dev/kvm` is writable and `IMAGE_URL` resolves for your Fedora version. |

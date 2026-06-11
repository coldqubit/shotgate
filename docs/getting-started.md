# Getting Started

This walkthrough takes you from zero to a passing quantum quality gate in a few
minutes. Section 1 uses Podman with no host Python; Section 2 uses a pip install of the
`shotgate` CLI and pytest plugin. The two paths produce identical results.

## Prerequisites

- [Podman](https://podman.io/) 4+ (`podman --version`).
- Optional: `qemu-system-x86_64` + `/dev/kvm` for the VM tier.
- The example workflows from this repo (or your own).

## 1. Run your first gate (pull the image)

No build step is required: pull the published image and run an example:

```bash
podman run --rm --userns=keep-id --user "$(id -u):$(id -g)" \
  -v "$PWD:/work:Z" -w /work \
  ghcr.io/coldqubit/shotgate:latest \
  run examples/bell-state/workflow.yaml --junit report.xml --json report.json
```

You'll see a Rich table of assertion results and the process will exit `0`. A JUnit
`report.xml` and `report.json` are written to the working directory. The image bakes in
qiskit + the Aer simulator, so the default `local-aer` backend works fully offline.

> **Contributor build (optional).** To develop shotgate itself or run on an air-gapped
> runner, build locally instead: `make build` then `make run WORKFLOW=...`.

## 2. Run it from pip (CLI and pytest plugin)

If you prefer an existing Python environment to a container, install the package with the
backend extra you need. This exposes the `shotgate` CLI and registers a pytest plugin:

```bash
pip install 'shotgate[aer]'                       # CLI + local Aer simulator
shotgate run examples/bell-state/workflow.yaml --junit report.xml
```

The pytest plugin emits one pytest item per declared assertion. Point it at a workflow with
`--shotgate`, or let it auto-collect files named exactly `workflow.yaml`:

```bash
pytest --shotgate examples/bell-state/workflow.yaml
```

A workflow whose backend dependencies are missing skips with a reason naming the extra to
install, rather than erroring.

## 3. Read the workflow

[`examples/bell-state/workflow.yaml`](../examples/bell-state/workflow.yaml) declares a
Bell pair and five statistical assertions. Open it alongside the
[workflow spec](workflow-spec.md) and the [assertion catalog](assertions.md).

## 4. Write your own

Create `my-workflow.yaml`:

```yaml
apiVersion: shotgate.dev/v1alpha1
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

Use the **IBM-enabled image variant** (`:latest-ibm`), which bakes in
`qiskit-ibm-runtime`, and pass a token:

```bash
export SHOTGATE_IBM_TOKEN=...      # from your IBM Quantum account
podman run --rm -e SHOTGATE_IBM_TOKEN -v "$PWD:/work:Z" -w /work \
  ghcr.io/coldqubit/shotgate:latest-ibm \
  run examples/bell-state-hardware/workflow.yaml --backend ibm
```

The `ibm` backend is **validated on real hardware** (`ibm_fez`, 2026-06-11: the Bell,
GHZ, and Grover hardware gates all passed at 4096 shots; measured baseline in the
[hardware validation plan](hardware-validation.md)). Loosen thresholds for device noise
(the `*-hardware` examples already do), and see the
[pipeline guide](pipeline.md#1-the-hybrid-pipeline).

## 6. Run with VM-grade isolation (optional)

```bash
make vm-up WORKFLOW=examples/ghz-state/workflow.yaml
```

Boots a throwaway KVM micro-VM that runs shotgate in Podman *inside* the VM and writes
the report back. See [`infra/qemu`](../infra/qemu/README.md).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `backend 'local-aer' ... dependencies are not installed` | Use the published image (`ghcr.io/coldqubit/shotgate:latest`) or build it (`make build`); or `pip install 'shotgate[aer]'`. |
| `:Z` mount errors on non-SELinux hosts | Drop `:Z` from the `-v` flag. |
| QASM parse error | Ensure `include "qelib1.inc";` and a `creg`/`measure` (or omit measurement and shotgate appends `measure_all`). |
| VM won't boot | Check `/dev/kvm` is writable and `IMAGE_URL` resolves for your Fedora version. |

# Workflow Specification: `shotgate.dev/v1alpha1`

A shotgate workflow is a strict YAML document. Unknown fields are rejected so typos
fail fast. The schema is the single source of truth in
[`src/shotgate/config.py`](../src/shotgate/config.py).

## Top-level document

```yaml
apiVersion: shotgate.dev/v1alpha1   # required, pinned
kind: QuantumWorkflow             # required
metadata: { ... }                 # required
defaults: { ... }                 # optional: backend defaults for all jobs
jobs: [ ... ]                     # required, >= 1
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `apiVersion` | string | yes | Must equal `shotgate.dev/v1alpha1`. |
| `kind` | string | yes | Must equal `QuantumWorkflow`. |
| `metadata` | object | yes | See [`metadata`](#metadata). |
| `defaults` | object | no | `{ backend: BackendSpec }` inherited by jobs. |
| `jobs` | list | yes | One or more jobs; names must be unique. |

### `metadata`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | 1–63 chars; identifies the workflow in reports. |
| `description` | string | no | Free text. |
| `labels` | map[string]string | no | Arbitrary key/values (e.g. `suite: smoke`). |

## `jobs[]`

Each job loads one circuit, executes it on one backend, and evaluates its assertions.

```yaml
- name: bell-pair
  circuit: { format: qasm2, path: bell.qasm }
  backend: { provider: local-aer, shots: 8192, seed: 1234 }   # optional; merges with defaults
  assertions:
    - { type: distribution_tvd, expected: { "00": 0.5, "11": 0.5 }, max_distance: 0.03 }
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Unique within the workflow; becomes a JUnit `<testsuite>`. |
| `circuit` | object | yes | See [`circuit`](#circuit). |
| `backend` | object | no | See [`backend`](#backend). Fields fall back to `defaults.backend`. |
| `assertions` | list | no | See the [assertion catalog](assertions.md). |

### `circuit`

Exactly one of `path` or `inline` must be set.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `format` | `qasm2` \| `qasm3` | `qasm2` | OpenQASM dialect. |
| `path` | string | none | File path, resolved **relative to the workflow file**. |
| `inline` | string | none | OpenQASM source embedded in the YAML. |

If the loaded circuit has no classical bits, shotgate appends `measure_all()`.

### `backend`

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `provider` | `local-aer` \| `ibm` | `local-aer` | Execution target. Braket is planned (roadmap); selecting an unimplemented provider fails schema validation. |
| `shots` | int | `4096` | 1–1,000,000. |
| `seed` | int | none | Determinism for simulators. |
| `name` | string | none | Device/backend name (cloud providers). |
| `options` | map | `{}` | Provider-specific (e.g. `{ channel, instance, token }`). |
| `noise` | object | none | `local-aer` only: simulate device noise to exercise the noise-aware thresholds offline. Fields: `depolarizing_1q`, `depolarizing_2q`, `readout_p0`, `readout_p1` (each in `[0, 1]`). See [ADR-0009](adr/0009-noise-model-simulation.md). |

**Defaults merge semantics:** a job inherits every `defaults.backend` field it does
*not* explicitly set. Example: with `defaults.backend.shots: 8192`, a job that sets
only `backend: { shots: 1024 }` keeps the default `provider` and `seed`.

## CLI overrides

`--backend` and `--shots` on `shotgate run` override every job at runtime, handy for
re-running a simulator suite against real hardware without editing YAML.

## Full annotated example

See [`examples/bell-state/workflow.yaml`](../examples/bell-state/workflow.yaml),
[`examples/ghz-state/workflow.yaml`](../examples/ghz-state/workflow.yaml), and
[`examples/grover-2q/workflow.yaml`](../examples/grover-2q/workflow.yaml).

# shotgate documentation

shotgate runs container-native CI/CD quality gates for quantum circuits: it executes a
circuit on a simulator or a real quantum processing unit (QPU) and gates the pipeline on
the *statistical* properties of the measured shot distribution (chi-square goodness-of-fit,
total variation distance, Hellinger fidelity, support leakage) rather than on exact
equality, which probabilistic output makes meaningless. New here? Read
[Getting Started](getting-started.md) first, then the
[Workflow Specification](workflow-spec.md) for the YAML schema and the
[Assertion Catalog](assertions.md) for the oracles and how to set thresholds.

| Document | What it covers |
| --- | --- |
| [Getting Started](getting-started.md) | Zero to a passing quantum gate with Podman. |
| [Solution Architecture](architecture.md) | Components, data flow, isolation tiers, security, extension points. |
| [Pipeline Schema](pipeline.md) | How shotgate gates a CI/CD pipeline; stage contract; exit codes. |
| [Workflow Specification](workflow-spec.md) | The `shotgate.dev/v1alpha1` YAML schema, field by field. |
| [Assertion Catalog](assertions.md) | The statistical oracles, with the math and threshold guidance. |
| [Hardware Validation Plan](hardware-validation.md) | v0.2 milestone: runbook and measured `ibm_fez` baseline (2026-06-11). |
| [Motivation](motivation.md) | The market/community gap shotgate fills, with sources. |
| [ADRs](adr/) | Architecture Decision Records and their rationale. |
| [Diagrams](diagrams/) | Mermaid sources for the architecture and pipeline diagrams. |

Infrastructure docs live next to the code they describe:

- [Terraform module](../infra/terraform/README.md): quantum workflow as code.
- [KVM/QEMU runner](../infra/qemu/README.md): ephemeral VM isolation tier.

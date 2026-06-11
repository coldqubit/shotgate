# shotgate documentation

| Document | What it covers |
| --- | --- |
| [Getting Started](getting-started.md) | Zero to a passing quantum gate with Podman. |
| [Solution Architecture](architecture.md) | Components, data flow, isolation tiers, security, extension points. |
| [Pipeline Schema](pipeline.md) | How shotgate gates a CI/CD pipeline; stage contract; exit codes. |
| [Workflow Specification](workflow-spec.md) | The `shotgate.dev/v1alpha1` YAML schema, field by field. |
| [Assertion Catalog](assertions.md) | The statistical oracles, with the math and threshold guidance. |
| [Hardware Validation Plan](hardware-validation.md) | v0.2 runbook to validate the gates on a real IBM QPU. |
| [Motivation](motivation.md) | The market/community gap shotgate fills, with sources. |
| [ADRs](adr/) | Architecture Decision Records and their rationale. |
| [Diagrams](diagrams/) | Mermaid sources for the architecture and pipeline diagrams. |

Infrastructure docs live next to the code they describe:

- [Terraform module](../infra/terraform/README.md): quantum workflow as code.
- [KVM/QEMU runner](../infra/qemu/README.md): ephemeral VM isolation tier.

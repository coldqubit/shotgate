# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-01

### Added

- **Declarative workflows** (`qforge.dev/v1alpha1`): strict, Kubernetes-style YAML
  schema for "quantum workflow as code" with workflow-level backend defaults.
- **Statistical assertion oracles**: `distribution_tvd`, `hellinger_fidelity`,
  `chi_square` (Pearson goodness-of-fit), `state_probability`, `allowed_states`.
- **Pure-Python statistics core**: total variation distance, Hellinger fidelity, and a
  from-scratch chi-square survival function via the regularised incomplete gamma
  function (no SciPy/numpy dependency).
- **Pluggable backends**: `Backend` ABC + lazy registry; `local-aer` (Qiskit Aer) and
  an `ibm` (Qiskit Runtime) backend. SDKs imported lazily so the core stays light.
- **CLI**: `qforge run` (CI quality gate, exit 0/1/2), `validate`, `backends`.
- **Reporters**: JUnit XML, JSON, Markdown summary, and Rich console output.
- **Telemetry**: per-job circuit width/depth/size/op-counts and wall-clock runtime.
- **Container-native tooling**: multi-stage `Containerfile` (non-root runtime + test
  stage) and a Podman/QEMU `Makefile`.
- **KVM/QEMU isolation tier**: `infra/qemu` boots an ephemeral Fedora micro-VM
  (cloud-init, copy-on-write overlay) that runs qforge in Podman inside the VM.
- **Terraform IaC module**: express a quantum quality gate as a `terraform_data`
  resource driven by the qforge container.
- **CI/CD**: Podman-based GitHub Actions for lint, core + integration tests, example
  gates, Terraform validation, and a tagged release pipeline (dist + GHCR image).
- **Docs**: solution architecture, pipeline schema, workflow spec, assertion catalog
  (with the math), getting-started guide, and ADRs.
- **Examples**: Bell state, 3-qubit GHZ, and 2-qubit Grover workflows.

[Unreleased]: https://github.com/your-org/qforge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/qforge/releases/tag/v0.1.0

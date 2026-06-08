# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Relicensed from AGPL-3.0-or-later to Apache-2.0.** The `LICENSE` file now carries the
  verbatim Apache License 2.0 text, every `src/shotgate/**/*.py` SPDX header reads
  `Apache-2.0`, and `pyproject.toml` declares `license = "Apache-2.0"` with the
  `License :: OSI Approved :: Apache Software License` classifier. Apache-2.0 is permissive:
  use, modification, and redistribution are allowed for any purpose, including commercial and
  closed-source, provided the license and attribution notices are retained. The previous
  network-copyleft (source-disclosure for hosted modified versions) no longer applies.
- **Renamed the project from `qforge` to `shotgate`.** The name `qforge` was already
  taken (PyPI/crates) and raised a VS Code marketplace trademark concern. The package
  (`src/shotgate`), CLI program, container image, environment variables
  (`SHOTGATE_IBM_TOKEN`), and the workflow API version (`shotgate.dev/v1alpha1`) all
  moved to the new name. The canonical home is `github.com/coldqubit/shotgate` and the
  published image is `ghcr.io/coldqubit/shotgate`.
- **Pull-first usage.** Documentation now leads with `podman run
  ghcr.io/coldqubit/shotgate …`; building from source is the contributor fallback.
- **Honest extras.** `braket` and `mitigation` are marked *planned* and removed from the
  installable `all` extra, since no Braket backend or Mitiq integration ships yet.
  `--backend braket` now fails fast at schema validation with a clear message.
- **Project identity and governance made consistent.** Committed files refer to the
  project home as `coldqubit` and to the maintainer *role* rather than to a personal
  account: the README maintainer note was rewritten, [`CODEOWNERS`](CODEOWNERS) now
  points at the `@coldqubit/maintainers` team, and the contribution terms were aligned.
  The `CONTRIBUTING.md` inbound-license statement, which incorrectly named the MIT
  License, now correctly states Apache-2.0 and is expressed as a Developer Certificate of
  Origin (DCO) sign-off.

### Added

- **Published container image** to GHCR on tag, tagged with the semver version, the
  git SHA, and `latest` (release pipeline).
- **Reference CI for GitLab and Jenkins** (`.gitlab-ci.yml`, `Jenkinsfile`) that pull the
  published image and emit JUnit, alongside the existing GitHub Actions example.
- **Hardened IBM/QPU backend**: robust counts extraction from named classical registers
  (with a clear error on unexpected result shapes), corrected Runtime channel default,
  a token-gated smoke test, and an `[ibm]`-baked image variant (build arg
  `SHOTGATE_EXTRAS="aer,ibm"`, published as the `:…-ibm` image tag).
- **Noise-tolerant example** (`examples/bell-state-hardware/`) with relaxed thresholds
  for real-device runs, plus a documented simulator-vs-QPU threshold split.
- **`docs/hardware-validation.md`**: a step-by-step plan and acceptance matrix for
  validating the statistical gates on real IBM quantum hardware (v0.2 milestone).
- **`GOVERNANCE.md` and `MAINTAINERS.md`**: how decisions are made (lazy consensus,
  Architecture Decision Records for substantial changes, single maintainer today and
  structured to grow) and who maintains the project, including the concrete path for a
  co-maintainer to join.

> The `ibm` backend remains **implemented but not yet validated on real hardware**.

## [0.1.0] - 2026-06-01

> Initial release, published under the project's original name **`qforge`** (the
> workflow API version was `qforge.dev/v1alpha1`). Renamed to `shotgate` post-release;
> see [Unreleased].

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
- **CLI**: `shotgate run` (CI quality gate, exit 0/1/2), `validate`, `backends`.
- **Reporters**: JUnit XML, JSON, Markdown summary, and Rich console output.
- **Telemetry**: per-job circuit width/depth/size/op-counts and wall-clock runtime.
- **Container-native tooling**: multi-stage `Containerfile` (non-root runtime + test
  stage) and a Podman/QEMU `Makefile`.
- **KVM/QEMU isolation tier**: `infra/qemu` boots an ephemeral Fedora micro-VM
  (cloud-init, copy-on-write overlay) that runs shotgate in Podman inside the VM.
- **Terraform IaC module**: express a quantum quality gate as a `terraform_data`
  resource driven by the shotgate container.
- **CI/CD**: Podman-based GitHub Actions for lint, core + integration tests, example
  gates, Terraform validation, and a tagged release pipeline (dist + GHCR image).
- **Docs**: solution architecture, pipeline schema, workflow spec, assertion catalog
  (with the math), getting-started guide, and ADRs.
- **Examples**: Bell state, 3-qubit GHZ, and 2-qubit Grover workflows.

[Unreleased]: https://github.com/coldqubit/shotgate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/coldqubit/shotgate/releases/tag/v0.1.0

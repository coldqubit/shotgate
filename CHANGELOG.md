# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-07-11

### Added

- **Statistical-power tooling (ADR-0017): Wilson confidence intervals and sample-size
  planning, pure stdlib.** `validation/metrics.py` gains `wilson_interval`,
  `shots_for_margin`, and `shots_for_power`, backed by a Newton-iteration inverse-normal
  (`_norm_ppf`) rather than a hard-coded rational approximation, verified to match textbook
  z-values (1.959964 at 95%, 2.575829 at 99%) to 9 decimal places. `state_probability` now
  reports a 95% Wilson interval on the measured probability (`ci95_lower`/`ci95_upper` in
  `metrics`, shown in the message) whenever shots are available; every other oracle's
  `evaluate()` is unchanged. New CLI command `shotgate shots --margin M` or
  `--effect-size W [--alpha A] [--power P]` plans a shot count for a target confidence-interval
  width or detection power ahead of writing a workflow, e.g.
  `shots_for_power(0.05, alpha=0.01, power=0.9) == 5952`, matching the hand calculation
  `((z_0.01 + z_power=0.9) / 0.05)^2`.

## [0.8.0] - 2026-07-11

### Added

- **`differential` assertion (ADR-0016): the first oracle needing no declared `expected`.**
  Bounds the total variation distance between one job's measured counts and another job's
  (`against_job`, naming a job declared earlier in the same workflow), instead of a static
  distribution. Lets a workflow gate a circuit whose correct output is not known in closed
  form, or catch a backend/optimization-level/transpiler regression that a fixed-expected
  oracle would not, since both sides of the comparison come from actually running the circuit.
  `Runner` now tracks already-executed jobs by name and threads the referenced job's counts
  into `evaluate()` via two new, generically-named optional keyword arguments
  (`reference_counts`, `reference_shots`) that only this oracle consumes; every other oracle's
  call site is unaffected. A forward reference, self-reference, or missing job name fails
  closed with a message naming the problem, rather than a schema error. New example:
  `examples/bell-state-differential` (one Bell circuit through Aer's `statevector` and
  `matrix_product_state` methods, no `expected` anywhere; measured TVD 0.0006).

## [0.7.0] - 2026-06-30

### Changed

- **BREAKING: `chi_square` is now simulator-only and `kl_divergence` is automatically
  readout-aware (ADR-0015).** The three attempts to make `chi_square` gate against the ideal
  on real hardware (a readout transform, auto-calibrated readout, and the `NoiseModel.from_backend`
  digital twin) are retired: a goodness-of-fit test against an exact expected only holds on a
  simulator, and the twin, though it lowered the statistic, did not gate reliably because a
  published noise model only approximates the device (`docs/hardware-validation.md` sections
  9-12). `chi_square` now **fails closed on real hardware** with guidance toward the
  noise-tolerant oracles; `kl_divergence` keeps the readout transform but applies it
  **automatically** (the device's calibration on a QPU, the plain ideal on a simulator) with no
  configuration. Each backend reports `metadata['simulator']`. Gate hardware with
  `distribution_tvd`, `hellinger_fidelity`, and `allowed_states`.

### Removed

- **BREAKING: the `readout_error` and `noise_model` assertion fields and the digital-twin
  machinery** (`backends/digital_twin.py`, `NoiseModel.from_backend`, twin-shot options).
  Setting either field now raises a migration error. The `shotgate.dev/v1alpha1` schema version
  is unchanged (a removal within an alpha API). To keep the removed modes, pin `shotgate==0.6.x`.

## [0.6.0] - 2026-06-30

### Added

- **`noise_model: auto` (digital twin) for `chi_square` and `kl_divergence` (ADR-0014).**
  Compares measured counts against the device's *full* calibrated noise model (gate, readout,
  and thermal relaxation) simulated on the same circuit, not just a readout transform. The `ibm`
  backend builds the twin with `NoiseModel.from_backend` and simulates the ISA circuit on Aer;
  `local-aer` reuses its `noise` block; a noiseless run carries no twin, so `auto` falls back
  to the ideal expected (the plain test). It captures the gate and decoherence leakage a
  readout transform misses, lowering the goodness-of-fit statistic (on a real `ibm_marrakesh`
  run: ideal 4.54e15 -> readout-only auto 47.56 -> twin 32.40); whether it then passes depends
  on how closely the device matches its published model. The verdict's meaning shifts to a
  calibration-drift / device-health check ("does the device match its own calibrated model?"):
  in simulation, where the device is its model, the twin passes (healthy run p-value 0.70, a
  drifted device rejected at p-value 0); on a real QPU `NoiseModel.from_backend` is an
  approximation, so `chi_square` can still reject (see `docs/hardware-validation.md` section
  12). `noise_model` and
  `readout_error` are mutually exclusive on one assertion; the twin needs Aer on the `ibm`
  backend (`shotgate[ibm,aer]` or the `:latest-ibm` image). Twin shot budget is
  `backend.options.twin_shots` (default 200000). The schema addition is backward-compatible
  (no `shotgate.dev/v1alpha1` bump). See `docs/hardware-validation.md` section 12.

## [0.5.0] - 2026-06-27

### Added

- **`readout_error: auto` for `chi_square` and `kl_divergence` (ADR-0013).** The oracle uses
  the readout calibration the run actually had instead of a hand-written guess: the `ibm`
  backend reads it from the device's published properties (averaged over the active qubits),
  `local-aer` reports its `noise` block's readout parameters, and a noiseless simulator
  reports none, so `auto` falls back to the plain test. One workflow then gates with the
  plain `chi_square` on a simulator and the device-calibrated one on a QPU, with no
  per-device editing. The `evaluate` contract gains an optional `backend_metadata` argument;
  existing oracles ignore it.

## [0.4.0] - 2026-06-26

### Added

- **Two structural oracles (9 -> 11), see ADR-0012:** `circuit_depth` and `gate_set` gate on
  the authored circuit's structure (its depth and its gate set) rather than its output. They
  are static: a job whose assertions are all structural runs with no shots, no QPU time, and
  no backend execution. The assertion contract gains an optional `circuit_metrics` argument
  (the runner passes the telemetry it already computes); existing oracles are unaffected. A
  `bell-state-structural` example demonstrates the no-execution path.
- **`most_frequent_outcome` on the Grover hardware example,** giving that oracle a gating
  hardware data point on its natural use case (a single intended answer).

### Changed

- Documented a 2026-06-26 real-QPU re-run exercising the post-v0.2 oracles on hardware
  (`expectation_value`, noise-aware `chi_square`/`kl_divergence`, `most_frequent_outcome`):
  see `docs/hardware-validation.md` section 10.

## [0.3.0] - 2026-06-26

> Bundles the work the roadmap sketched across several minor milestones (oracle breadth,
> noise-aware validation, the AWS Braket backend) into one release after `0.2.2`.

### Added

- **AWS Braket backend (ADR-0011).** `provider: braket` runs the same workflows on Braket.
  Local simulation needs **no AWS account** (omit `backend.name`); cloud devices are reached
  by setting `backend.name` (e.g. `SV1`) and need configured AWS credentials. Dependencies
  live in the `braket` extra (`pip install shotgate[braket]`); a dedicated CI job validates
  the local path. Promotes `braket` from a planned to a working backend. The cloud path is
  implemented but not yet validated on real Braket hardware.
- **Noise-aware expected distributions: `chi_square` and `kl_divergence` can gate on
  hardware (ADR-0010).** An optional `readout_error: { p0, p1 }` block transforms the ideal
  `expected` through a calibration-derived per-qubit readout model, giving the test nonzero
  mass on the device's error states. On the measured `ibm_fez` Bell counts this takes
  `chi_square` from statistic 1.5e17 / p-value 0 to statistic 5.51 / p-value 0.138 (passes
  at alpha 0.01); the readout parameters are declared from calibration, not fit to the
  counts, so the gate stays honest. Partially lifts the ADR-0006 simulator-only policy.
- **Declarative noise-model simulation on `local-aer` (ADR-0009).** A backend can carry a
  `noise` block (`depolarizing_1q`/`depolarizing_2q`/`readout_p0`/`readout_p1`) so the
  noise-aware `*-hardware` thresholds can be regression-tested in CI without a QPU. A
  simulated-noisy Bell pair lands in the measured device regime (TVD ~0.12 vs the measured
  `ibm_fez` 0.1284); a `bell-state-noisy-sim` example gates it against hardware-profile
  bounds. Non-simulator backends ignore `noise`.
- **Four new assertion oracles (5 -> 9), see ADR-0008:** `kl_divergence` (bound the
  Kullback-Leibler divergence to an expected distribution, in bits; simulator-oriented
  like `chi_square`), `shannon_entropy` (bound the distribution entropy in a min/max
  window), `expectation_value` (bound the Pauli-Z product `<Z..Z>` in [-1, 1] via a
  window or a target), and `most_frequent_outcome` (assert the modal state, optionally
  above a probability). All are counts-based and keep the validation core SDK-free. A
  `bell-state-observables` example exercises the new observable oracles. The JSON reporter
  now serialises a non-finite metric (a diverged KL) as `null` so output stays valid.

### Changed

- **JUnit reports carry `timestamp` and `skipped`** attributes on the root and every
  testsuite, for fuller xUnit-schema compliance in CI dashboards. Declared the supported
  Python grid (3.10-3.13) as trove classifiers.
- **Fail-closed validation (see ADR-0007).** A job that runs but declares no
  assertions now **fails** by default, instead of silently passing a gate that checked
  nothing; opt out with `--allow-empty` (CLI) or `allow_empty=True` (`Runner`).
  Basis-state keys in `expected`, `state`, and `states` are validated at schema-parse
  time: non-empty, `0`/`1` only, and a single consistent width, so a malformed key
  (e.g. `"0x"`, or mixed `"0"`/`"11"`) raises a clear `ValidationError` instead of being
  silently mis-compared. Both are behaviour changes, intended at `0.x`.

### Fixed

- **OpenQASM 3 circuits now load.** The `qasm3` circuit format was advertised in
  the schema but failed at runtime: `qiskit.qasm3.loads` needs the
  `qiskit-qasm3-import` package, which no extra declared. It is now a dependency of
  the `aer` and `ibm` extras (and the published images), the loader raises an
  actionable error if it is somehow absent, and a `bell-state-qasm3` example plus
  loader tests cover the path.

## [0.2.2] - 2026-06-11

### Added

- **Three Architecture Decision Records.** ADR-0004 (rename `qforge` to `shotgate`,
  including the breaking `apiVersion` change), ADR-0005 (license MIT to
  AGPL-3.0-or-later to Apache-2.0, and the DCO inbound policy), and ADR-0006
  (`chi_square` simulator-only, noise-aware hardware thresholds), completing the
  ADR series against the GOVERNANCE.md criteria.
- **Docker Hub repository page sync.** After mirroring images, the `dockerhub-mirror`
  workflow now pushes the repository README and the project tagline to the Docker Hub
  repository description, so the Hub listing tracks the source. The step is non-fatal:
  a description-API failure never blocks the image mirror or the release.

### Changed

- **Docker Hub mirroring is a reusable, dispatchable workflow.** The mirror moved from an
  inline release job to `dockerhub-mirror.yml` (`workflow_call` from the release plus
  `workflow_dispatch` to back-fill any version), with credentials read from the
  `dockerhub` environment (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, optional
  `DOCKERHUB_NAMESPACE`) instead of repository secrets.
- **Reporter copy uses ASCII separators.** The Markdown summary title format is now
  ``## shotgate: `name` (status)``, the no-assertion row prints `n/a`, and the plain
  console fallback separates label and message with a colon; previously all three used
  an em-dash. JUnit and JSON payloads are unchanged.

## [0.2.1] - 2026-06-11

### Added

- **Full oracle coverage on hardware.** A non-gating diagnostic example,
  `bell-state-hardware-oracle-coverage`, runs all five oracles on one Bell circuit so
  `chi_square` also has a real-QPU data point. Measured on `ibm_fez`: the four
  distance/structural oracles passed while `chi_square` returned p-value 0.0000
  (statistic 1.5e17, dof 3), confirming why it is simulator-only. Mechanism and numbers
  in `docs/hardware-validation.md` section 9.
- **GitHub-only install path in release notes.** Each release now documents installing the
  attached wheel and pulling the GHCR image directly, so neither PyPI nor Docker Hub is
  required to consume a release.
- **Optional Docker Hub mirror** in the release pipeline. When the `DOCKERHUB_USERNAME` and
  `DOCKERHUB_TOKEN` repository secrets are present, released images are mirrored to Docker
  Hub alongside the canonical GHCR images; absent the secrets the step is skipped and the
  release is unaffected.

### Changed

- **Portable device selection.** A pinned `ibm` device that the account or instance cannot
  reach now raises a clear error listing the reachable real devices and pointing at the
  `least_busy` default, instead of an opaque Qiskit lookup failure. The
  `hardware-validation` workflow's device input now defaults to empty (`least_busy`) rather
  than a pinned `ibm_fez`.

## [0.2.0] - 2026-06-11

### Added

- **Hardware validation on a real QPU.** The Bell, GHZ, and Grover hardware gates ran on
  `ibm_fez` (156-qubit Heron r2) at 4096 shots each through the `ibm` backend and all
  passed: Bell TVD 0.1284 (<= 0.15), Hellinger fidelity 0.8716 (>= 0.85); GHZ TVD 0.1536
  (<= 0.20), fidelity 0.8463 (>= 0.80); Grover P(11) = 0.8357 (>= 0.70). Measured baseline,
  raw counts, and job ids are recorded in `docs/hardware-validation.md` section 9. Total
  QPU usage: 9 s.
- **Hardware example gates** `examples/ghz-state-hardware` and `examples/grover-2q-hardware`
  with the noise-aware thresholds from the validation plan (chi_square stays
  simulator-only because it over-rejects under coherent device noise).
- **`hardware-validation` workflow** (manual dispatch): installs `shotgate[ibm]` from PyPI
  on a clean runner, pins the requested device (input, default `ibm_fez`), runs the three
  hardware gates against the real QPU, and uploads JUnit/JSON/Markdown reports.

### Changed

- The `ibm` backend status moved from "implemented but not yet validated on real hardware"
  to "validated on real hardware" in the README backends table, the backend docstring,
  `docs/getting-started.md`, and the hardware validation plan.

## [0.1.1] - 2026-06-11

### Changed

- **Contact email** in package metadata and `MAINTAINERS.md` is now `info@coldqubit.org`.
- **README images use absolute URLs** (raw.githubusercontent.com) so the logomark and the
  terminal demo render on the PyPI project page, which resolves the README standalone.
- **Registry resilience in CI and release pipelines**: base images are pre-pulled with
  exponential backoff (5 attempts) and fall back to the same official image on
  `public.ecr.aws`, after Docker Hub was unreachable from a runner for over 3 minutes
  on 2026-06-10 and failed a main-branch CI run.
- **Dependencies**: qiskit constraint widened to `>=1.2,<3` (integration suite passes on
  qiskit 2.x); GitHub Actions bumped (checkout v6, upload-artifact v7, download-artifact v8,
  action-gh-release v3).

### Added

- **shotgate logomark** at the top of the README (`docs/assets/shotgate-logomark.svg`).
- **`pypi-smoke` workflow** (manual dispatch): installs the published package from PyPI on a
  clean runner and exercises the CLI gate and the pytest plugin, as a post-release check.

## [0.1.0] - 2026-06-10

> First public, tagged release. The codebase began on 2026-06-01 under the name `qforge`
> and was renamed to `shotgate`; it had no prior git tag, PyPI release, or published
> container image, so this is the project's first release of record. The capability
> baseline (workflows, oracles, backends, CLI, reporters, IaC, isolation) is listed under
> **Core capabilities** below; the entries above it are what changed on the way to release.

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
  ghcr.io/coldqubit/shotgate ...`; building from source is the contributor fallback.
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
  `SHOTGATE_EXTRAS="aer,ibm"`, published as the `:...-ibm` image tag).
- **Noise-tolerant example** (`examples/bell-state-hardware/`) with relaxed thresholds
  for real-device runs, plus a documented simulator-vs-QPU threshold split.
- **`docs/hardware-validation.md`**: a step-by-step plan and acceptance matrix for
  validating the statistical gates on real IBM quantum hardware (v0.2 milestone).
- **`GOVERNANCE.md` and `MAINTAINERS.md`**: how decisions are made (lazy consensus,
  Architecture Decision Records for substantial changes, single maintainer today and
  structured to grow) and who maintains the project, including the concrete path for a
  co-maintainer to join.
- **Automated PyPI publishing** via trusted publishing (OIDC, no stored token): the tagged
  release pipeline builds the sdist + wheel and publishes them to PyPI alongside the GHCR
  image and the GitHub Release, so `pip install shotgate[aer]` resolves from a tag.
- **README terminal visual** (`docs/assets/bell-state-demo.svg`): a branded render of the
  `examples/bell-state` gate output (five passing oracles), plus a live CI status badge.

> The `ibm` backend remains **implemented but not yet validated on real hardware**.

### Core capabilities

> The feature baseline, first built under the name `qforge` (workflow API `qforge.dev/v1alpha1`,
> since renamed to `shotgate.dev/v1alpha1`).

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

[Unreleased]: https://github.com/coldqubit/shotgate/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/coldqubit/shotgate/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/coldqubit/shotgate/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/coldqubit/shotgate/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/coldqubit/shotgate/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/coldqubit/shotgate/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/coldqubit/shotgate/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/coldqubit/shotgate/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/coldqubit/shotgate/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/coldqubit/shotgate/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/coldqubit/shotgate/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/coldqubit/shotgate/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/coldqubit/shotgate/releases/tag/v0.1.0

# Security Policy

## Supported versions

shotgate is alpha (`0.x`); security fixes land on `main` and the latest tagged release.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository, or email the maintainers listed in `CODEOWNERS`.

Include: affected version/image tag, reproduction steps, and impact. We aim to
acknowledge within 72 hours and to provide a remediation timeline after triage.

## Security model (what to attack / what we defend)

- **Untrusted circuits.** Circuits are OpenQASM parsed by qiskit's QASM reader, not
  `eval`'d Python. For circuits from untrusted sources, use the **VM isolation tier**
  (`infra/qemu`), which runs the workflow in an ephemeral KVM micro-VM.
- **Secrets.** Provider tokens are read from environment variables / container `-e`
  and are never written to disk by shotgate. The Terraform module marks token inputs
  `sensitive`. Never commit tokens or bake them into images.
- **Least privilege.** The runtime image runs as a non-root user (UID 1001). Prefer
  rootless Podman on shared runners.
- **Supply chain.** Dependencies are pinned by range and watched by Dependabot. The
  image is built from official base images; pin digests for production deployments.

## Hardening recommendations

- Run with `--network=none` when the backend is `local-aer` (no network needed).
- Mount the workspace read-only where possible; only the report directory needs write.
- Pin the base image by digest in your own deployment of the `Containerfile`.

# ADR-0003: Container-native execution; Terraform module over Go provider

- **Status:** Accepted
- **Date:** 2026-06-01

## Context

qforge must run quantum SDKs (qiskit, aer, provider clients) that are heavy and
version-sensitive, sometimes on circuits from untrusted contributors, across
heterogeneous CI runners. We want reproducibility, isolation, and zero host
pollution. We also want an Infrastructure-as-Code surface, because IaC tools "may need
support for quantum backends" and none exists.

Two sub-decisions:

1. **Execution substrate:** install on host vs. containers vs. VMs.
2. **IaC shape:** a bespoke Terraform *provider* (Go plugin) vs. a *module* that drives
   the qforge container.

## Decision

1. **Containers are the unit of execution.** The shipped artifact is the qforge OCI
   image (built and run with **Podman**, rootless-friendly, non-root user). Local
   `make` targets and CI both invoke the same image. Nothing but Podman (and QEMU) is
   required on the host.
2. **Offer a VM tier with KVM/QEMU.** For untrusted circuits or hard stage isolation,
   `infra/qemu` boots an ephemeral Fedora micro-VM (copy-on-write overlay, cloud-init)
   that runs qforge in Podman *inside* the VM. Hardware boundary, fully disposable.
3. **IaC is a Terraform module, not a Go provider (for now).** The module expresses a
   quantum workflow as a `terraform_data` resource whose provisioner runs the qforge
   container, re-running when the workflow/image/backend/shots change.

## Consequences

- **+** One reproducible environment everywhere; "works on my machine" disappears.
- **+** Three isolation tiers (container → rootless → VM) selectable per pipeline
  trigger, all host-clean.
- **+** The Terraform module ships today with no compiler, no plugin registry, and
  keeps validation logic in exactly one place (the container).
- **−** Container/VM startup adds latency vs. a host install (seconds; acceptable for
  CI). The VM tier downloads a base image once.
- **−** A module can't model a typed resource graph the way a native provider could.
  Revisit a Go provider when there's demand for first-class quantum resources in plans;
  the workflow contract is designed to stay identical, so migration is additive.

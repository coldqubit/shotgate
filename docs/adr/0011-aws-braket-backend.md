# ADR-0011: AWS Braket backend (local simulation working; cloud needs an AWS account)

- **Status:** Accepted
- **Date:** 2026-06-26

## Context

ADR-0003 shipped a lazy, pluggable backend layer and listed AWS Braket as planned;
`braket` was intentionally absent from the selectable providers so a workflow could not
request a backend that did not exist. The roadmap places a minimal Braket backend in the
multi-vendor milestone. The `amazon-braket-sdk` exposes a `LocalSimulator` that runs on the
host with **no AWS account**, and `qiskit-braket-provider` adapts shotgate's Qiskit circuits
to it, so the backend can be implemented and tested offline; only real Braket cloud devices
require AWS.

A measurement confirmed the local path: a Bell circuit run through
`BraketLocalBackend` returned `{00: 2082, 11: 2014}` over 4096 shots with no credentials.

## Decision

Promote `braket` to a working provider with two paths under one name:

- **Local simulation (default):** omit `backend.name` (or set `local`); runs on Braket's
  `LocalSimulator` via `qiskit-braket-provider`, no AWS account, no cost.
- **Cloud devices / on-demand simulators:** set `backend.name` to a Braket device (e.g.
  `SV1` or a device ARN); requires configured AWS credentials and Braket access, billed by
  AWS. An unavailable device raises a `BackendUnavailableError` that names the local path.

`braket` is added to the `ProviderName` literal and the registry; its dependencies
(`amazon-braket-sdk`, `qiskit-braket-provider`) move from a planned extra to the working
`braket` extra and join `shotgate[all]`. A dedicated `braket-local` CI job exercises the
local path so the heavy SDK does not bloat the main test image.

## Consequences

- **+** Multi-vendor: shotgate now runs the same workflow on Aer, IBM, and Braket, which is
  the credibility point of a backend-agnostic gate.
- **+** The local Braket path is testable in CI and by contributors with no AWS account.
- **-** The cloud path is implemented but **not yet validated against real Braket devices**;
  that validation needs an AWS account with Braket access and is deferred (the analogue of
  the `ibm` hardware validation in ADR-0006 / `docs/hardware-validation.md`).
- **-** `amazon-braket-sdk` is a heavy dependency tree (boto3, openqasm3, antlr); it is kept
  to the `braket` extra and a single CI job, never the core or the default image.
- **-** Braket's local path does not honor a simulator seed through this provider, so those
  runs are not deterministic; the backend records `seed_requested` for traceability only and
  tests assert structural properties rather than exact counts.
- Braket-local overlaps with `local-aer` for offline use; the backend's distinct value is
  the cloud device path and the multi-vendor surface, not local simulation per se.

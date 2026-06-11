# ADR-0005: License is Apache-2.0 (after MIT and an AGPL interlude)

- **Status:** Accepted
- **Date:** 2026-06-08

## Context

The project's license changed twice before the first release settled it:

1. **MIT** at inception (2026-06-01).
2. **AGPL-3.0-or-later** later the same day, chosen for the network copyleft:
   distributing the tool, or running a modified version as a hosted service, would
   have required releasing source.
3. **Apache-2.0** on 2026-06-08, two days before the first tagged release.

The week under AGPL exposed a conflict with the adoption model. shotgate's target
user is a corporate continuous integration (CI) pipeline, and the quantum ecosystem
it builds on (Qiskit, Qiskit Aer, Cirq, Mitiq) is Apache-2.0 licensed; a
network-copyleft gate inside that stack invites legal review friction that a CI
utility cannot justify, and the "hosted modified service" trigger is ambiguous for a
tool whose whole purpose is to run inside other people's pipelines.

Relicensing was legally clean at that date: every line of source had a single
copyright holder (the maintainer), since the only third-party commits were
Dependabot version-range bumps and none had landed before the relicense commit.

## Decision

License the project **Apache-2.0**: verbatim license text in `LICENSE`, the
two-line SPDX header (`Apache-2.0`, `Copyright (C) 2026 coldqubit`) in all `src/`
files (17 files at the time), the `Apache-2.0` expression and classifier in
`pyproject.toml`, and the OCI license label in the `Containerfile`. Inbound
contributions are accepted under a Developer Certificate of Origin (DCO) sign-off
carrying the same Apache-2.0 terms (Apache-2.0 section 5), with no separate
contributor license agreement.

## Consequences

- **+** Permissive adoption: use, modification, and redistribution for any purpose,
  including commercial and closed-source, retaining the license and attribution
  notices (Apache-2.0 sections 4(a) through 4(d)).
- **+** An explicit patent grant (section 3), which MIT lacked.
- **+** License-compatible with the Apache-2.0 quantum SDK stack it imports.
- **−** The AGPL network-copyleft promise is removed, not replaced: a vendor can
  ship a modified closed-source shotgate as a service.
- **−** Practically irreversible: once external DCO-signed contributions land,
  relicensing again would require every contributor's consent. This ADR therefore
  also fixes the inbound policy (DCO, same license in and out).

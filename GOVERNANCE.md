# Governance

shotgate is an independent open-source project developed under the
[coldqubit](https://github.com/coldqubit) project home. This document describes how
decisions are made. It is intentionally lightweight and matches the project's current
size: one maintainer today, structured to grow.

## Roles

- **Users** open issues, ask questions, and propose features.
- **Contributors** send pull requests. Anyone can be a contributor; start with
  [CONTRIBUTING.md](CONTRIBUTING.md).
- **Maintainers** review and merge, cut releases, and steward the roadmap. The current
  roster and the path to join it are in [MAINTAINERS.md](MAINTAINERS.md).

## How decisions are made

Routine changes (bug fixes, docs, tests, and additive features that fit the existing
design) are decided by **lazy consensus**: a maintainer approves and merges, and any
maintainer may ask to hold a change for discussion before it lands.

Substantial or hard-to-reverse changes (a new assertion oracle or backend, a change to
the `shotgate.dev/v1alpha1` workflow schema, the license, or any breaking change) are
recorded as an **Architecture Decision Record (ADR)** in [docs/adr/](docs/adr/) and
discussed in an issue or pull request first. This is already the project's practice; see
[ADR-0001](docs/adr/0001-record-architecture-decisions.md).

While there is a single maintainer, that maintainer is the final decision-maker. As
maintainers are added, decisions move to consensus among them, with the lead maintainer
breaking ties only when consensus is not reached. The explicit goal is that no decision
depends on one person staying available.

## Changing the maintainer roster

Adding or removing a maintainer is itself a pull request against
[MAINTAINERS.md](MAINTAINERS.md), confirmed by lazy consensus of the current
maintainers. The criteria and steps are in
[MAINTAINERS.md](MAINTAINERS.md#becoming-a-maintainer).

## Code of conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Reports go to the
maintainers listed in [CODEOWNERS](CODEOWNERS) and are handled per that document.

## Releases and security

Releases are tracked in [CHANGELOG.md](CHANGELOG.md) and follow semantic versioning while
the project is in `0.x` (alpha). Security reports follow [SECURITY.md](SECURITY.md).

# ADR-0004: Rename qforge to shotgate (and the workflow apiVersion with it)

- **Status:** Accepted
- **Date:** 2026-06-01

## Context

The project started on 2026-06-01 under the name `qforge`. Before any release was
tagged, two problems surfaced: the name was already taken on the package indexes
(PyPI and crates.io), and it raised a trademark concern on the VS Code marketplace.
The name is load-bearing in more places than the repository title: the Python
package, the command-line interface (CLI) program, the container image path, the
environment variables, and the workflow schema's `apiVersion` literal
(`qforge.dev/v1alpha1`) all embed it.

## Decision

Rename the project to **shotgate** everywhere the old name appeared: package
`src/shotgate`, CLI program `shotgate`, image `ghcr.io/coldqubit/shotgate`,
environment variable prefix `SHOTGATE_*`, and the workflow schema pin
`apiVersion: shotgate.dev/v1alpha1`. The schema pin is a pydantic `Literal`, so a
workflow declaring the old `qforge.dev/v1alpha1` fails schema validation rather
than being silently accepted.

## Consequences

- **+** The name is unique on PyPI and the container registries, so the package and
  image are installable under their own name with no squatting or trademark risk.
- **+** It describes the product (gating on measurement shots) instead of a generic
  "forge" metaphor.
- **−** The `apiVersion` change is breaking for any pre-rename workflow file. The
  impact was zero in practice: the rename landed on 2026-06-01 and the first tagged
  release (`v0.1.0`) followed on 2026-06-10, so no published package, image, or tag
  ever carried the old name and no external consumer existed to break.
- The old name survives only in git history and in the `CHANGELOG.md` v0.1.0 notes.

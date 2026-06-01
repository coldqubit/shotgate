# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-06-01

## Context

shotgate sits at an immature intersection (quantum × DevOps) where the "right" design
is not yet settled by convention. Decisions — why statistical oracles, why containers,
why a Terraform module instead of a provider — need to be legible to contributors and
to our future selves.

## Decision

We keep lightweight Architecture Decision Records (ADRs) in `docs/adr/`, one file per
significant decision, numbered sequentially, using the Nygard format (Context →
Decision → Consequences). An ADR is immutable once Accepted; we supersede rather than
edit.

## Consequences

- Reviewers can see the rationale behind a structure without archaeology.
- Superseding an ADR is itself a recorded event, preserving history.
- Minimal overhead: ADRs are short and only written for decisions with trade-offs.

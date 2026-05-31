# ADR-0002: Statistical oracles as the validation core

- **Status:** Accepted
- **Date:** 2026-06-01

## Context

Quantum programs are probabilistic; exact-equality assertions are either flaky or
vacuous. The academic literature (χ²-as-oracle, QUTest, QuCheck, QUT) establishes the
correct techniques — total variation distance, Hellinger fidelity, chi-square
goodness-of-fit — but they live in research prototypes, not in production CI tooling.
Meanwhile DevOps writers repeatedly note that quantum CI "lacks robust test
frameworks" and needs "specialized validation… in CI/CD pipelines".

We must also decide the dependency footprint. Pulling SciPy (for `chi2.sf`) and numpy
into the core would make the metrics layer heavy and couple it to a scientific stack.

## Decision

1. The product's core is a **library of statistical oracles**, exposed declaratively
   as assertion types in workflow YAML.
2. The core is implemented in **pure Python (standard library + pydantic only)**. In
   particular, the chi-square survival function is computed from the **regularised
   incomplete gamma function** (series + continued fraction, Numerical Recipes),
   avoiding SciPy entirely.
3. Oracles are **counts-based** first (distribution distance, fidelity, χ², marginal
   probability, support leakage). State-vector / tomography oracles are deferred.

## Consequences

- **+** The validation core imports no quantum SDK and no scientific stack, so metrics
  and schema run in a tiny container, in constrained CI, or as a library.
- **+** Correctness is unit-tested against known χ² quantiles and analytic values.
- **+** Adding an oracle is local: a pydantic model + one metrics function.
- **−** We reimplement a special function that SciPy provides; mitigated by tests
  against textbook quantiles (dof=1,2,5 at α=0.05).
- **−** Counts-based oracles can't express phase/entanglement-structure properties
  directly; revisit with tomography-based assertions when demand appears.

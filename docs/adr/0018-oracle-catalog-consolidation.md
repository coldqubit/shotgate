# ADR-0018: Oracle catalog consolidation toward 1.0

- **Status:** Accepted
- **Date:** 2026-07-11

## Context

The catalog reached 12 assertion types (v0.9.0). Four of them answer overlapping variants of
one question, "how close is the observed distribution to the expected one": `distribution_tvd`,
`hellinger_fidelity`, `chi_square`, `kl_divergence`. A 1.0 release freezes this catalog under
SemVer, so it is the last point where redundant surface is cheap to remove: today there are no
confirmed external adopters, so a deprecation costs nothing beyond internal churn; after 1.0 it
costs a MAJOR bump.

Auditing the four against three questions (does it answer a genuinely different question; would
a practitioner specifically reach for it; what does it cost to keep documented, tested, and
hardware-validated) gives three different answers, not one:

- **`distribution_tvd`**: the worst-single-event distance bound, shot-count agnostic,
  interpretable without a statistics background. The default; not in question.
- **`chi_square`**: a genuinely different *framework*, not a rescaled distance. It answers "does
  this reject a null hypothesis at significance alpha," a formal-testing semantics `distribution_tvd`
  does not provide. Now cleanly scoped to simulators (ADR-0015); real, distinct audience (anyone
  writing a report that needs a p-value, not a threshold).
- **`kl_divergence`**: an asymmetric, information-theoretic distance, and, since ADR-0015, the
  only member of this family that is *automatically* hardware-portable (it transforms `expected`
  through the run's device readout calibration with no configuration) and has a proven real-QPU
  result (0.0064 bits, passing, on `ibm_marrakesh`). That is a genuine, evidenced differentiator,
  not a hypothetical one.
- **`hellinger_fidelity`**: does not clear either bar. It is TVD's close mathematical cousin (both
  are bounded $f$-divergences; they are related by two-sided inequalities and, at the threshold
  levels this project's examples and hardware runs actually use, agree on pass/fail every time
  they have been compared here). It has no distinct framework (unlike `chi_square`) and no
  distinct hardware mechanism (unlike `kl_divergence`). Its only real argument is vocabulary:
  "fidelity" is standard quantum-computing terminology and the metric matches
  `qiskit.quantum_info.hellinger_fidelity`, which lowers the bar for a user coming straight from
  Qiskit. That argument is real but narrower than the other two's.

Outside this family, the other eight oracles were each checked for the same overlap and none
qualify: `state_probability` (a single state's probability, windowed) and `most_frequent_outcome`
(the argmax state, optionally windowed) look similar but answer different questions in practice,
a fixed probability threshold versus "whichever state wins, it must be this one," which matters
specifically when the winning margin narrows under noise but the ranking should not change.
`allowed_states` bounds mass *outside* a set rather than *inside* one. `shannon_entropy` and
`expectation_value` are different axes entirely (spread, and a parity observable). `differential`
needs no `expected` at all. `circuit_depth` and `gate_set` are static and orthogonal to each
other. No consolidation candidates found there.

## Decision

- **Keep `distribution_tvd` (default), `chi_square` (hypothesis-test alternate), and
  `kl_divergence` (hardware-portable information-theoretic alternate)** as the three oracles for
  "closeness to an expected distribution." This is the "1 default plus up to 2 reasoned
  alternates" shape: three total, each earning its place on a distinct axis (interpretability,
  formal framework, hardware portability), not four variations on the same axis.
- **Mark `hellinger_fidelity` a deprecation candidate.** It is not removed in this change; the
  plan, to ship in v0.10.0:
  1. `distribution_tvd`'s `AssertionResult.metrics` gains an additive `fidelity` field (computed
     from the same two distributions the TVD calculation already has, via the existing
     `metrics.hellinger_fidelity` function), so the number survives without a second
     independently-thresholded gate to configure.
  2. `hellinger_fidelity` is marked deprecated in its docstring and in `docs/assertions.md`
     (a non-breaking, non-functional change: it keeps working exactly as today).
  3. At the `v1alpha1` -> `v1` schema migration (the 1.0 API-freeze work), `hellinger_fidelity`
     is dropped from the frozen `v1` catalog unless real usage between now and then argues
     otherwise. `metrics.hellinger_fidelity` (the pure function) is unaffected either way; only
     the standalone assertion *type* is in question.
- **Revises the "mission-complete oracle set" clause of the 1.0 definition of done**: "closeness
  (Hellinger)" is replaced by "closeness (TVD, the default) plus the hypothesis-test and
  hardware-portable-divergence alternates (chi-square, KL)"; Hellinger fidelity remains reported,
  just not as a fourth independently-configured gate.
- **`most_frequent_outcome` and `state_probability` are both kept**, with the argmax-vs-threshold
  distinction made explicit in `docs/assertions.md` rather than left implicit, since the audit
  found the overlap was a documentation-clarity problem, not a redundancy problem.

## Consequences

- **+** A 1.0 catalog with three well-differentiated closeness oracles instead of four
  overlapping ones is easier to document, easier for a first-time user to choose from (directly
  answers the "too many cards" problem on the landing page), and cheaper to keep hardware-validated
  going forward (one fewer oracle needing its own real-QPU evidence line in
  `docs/hardware-validation.md`).
- **+** Non-breaking in this release: no code changes ship with this ADR. The deprecation
  mechanism (additive `fidelity` metric, docstring/doc notice) is itself designed to be
  non-breaking when it ships in v0.10.0; only the eventual `v1` catalog drops the standalone type.
- **-** A real, if narrow, loss: users who specifically want the "fidelity" vocabulary as an
  independently-thresholded gate (rather than a reported number alongside TVD) lose that once the
  `v1` catalog lands. Mitigated by keeping the metric, not the assertion type.
- **-** This is a judgment call made with no confirmed external usage data (pre-1.0, no known
  external adopters yet). It is deliberately reversible up to the `v1` migration: if real usage
  shows independent demand for `hellinger_fidelity` as its own gate before then, this ADR's
  removal plan does not have to execute.

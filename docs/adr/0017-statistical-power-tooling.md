# ADR-0017: Statistical-power tooling (Wilson intervals, sample-size planning)

- **Status:** Accepted
- **Date:** 2026-07-11

## Context

Every counts-based oracle reports a point estimate (a probability, a distance, a divergence)
compared against a fixed threshold. `state_probability`, for instance, reports `P(state)` and
passes or fails against `min`/`max`/`equals`, but says nothing about how tightly `shots` actually
constrains that estimate: a measured `P(11) = 0.62` at 100 shots and the same value at 100000
shots carry very different evidentiary weight, and the assertion result does not distinguish
them. Symmetrically, nothing in the workflow schema helps a user choose a shot count in the
first place: `docs/assertions.md` §"Setting thresholds" already gives the standard-error
formula ($\sqrt{p(1-p)/N}$) as guidance to read by hand, but shotgate had no function or command
that answers "how many shots do I need for a given precision or detection power?" directly.

Classical CI/CD has an analogous gap closed by power analysis: before writing a test with a
statistical component (e.g., an A/B test), you compute the sample size needed to detect a given
effect at a target significance and power. The same reasoning applies to shot counts.

## Decision

Add three pure-stdlib functions to `validation/metrics.py`:

- `wilson_interval(successes, trials, confidence=0.95) -> (lower, upper)`: the Wilson score
  confidence interval for a binomial proportion. Chosen over the naive
  `p +/- z*sqrt(p(1-p)/n)` interval because Wilson's form stays inside `[0, 1]` and remains
  well-behaved at `p` near 0 or 1 or small `n` (the common case for a rare leakage state), where
  the naive interval can go negative or exceed 1.
- `shots_for_margin(p, margin, confidence=0.95) -> int`: shots needed for a Wilson half-width
  at most `margin` (the standard normal-approximation planning formula
  `n = (z/margin)^2 p(1-p)`).
- `shots_for_power(effect_size, alpha=0.05, power=0.9) -> int`: shots needed to detect a
  proportion shift of `effect_size` at significance `alpha` with the given `power`.

All three need the standard normal quantile function, which the standard library does not
provide directly; rather than hard-code a rational-approximation lookup table (as the earlier
literature-sourced approximations for this class of problem typically do), `_norm_ppf` inverts
`math.erf` with a few Newton iterations, verified to match textbook z-values (1.959964 at 95%,
2.575829 at 99%) to 9 decimal places.

Wiring: `state_probability`'s result now includes a 95% Wilson interval on the measured
probability (`ci95_lower`, `ci95_upper` in `metrics`, appended to the message) whenever
`shots > 0`; every other oracle's `evaluate()` signature and return shape is unchanged. A new
CLI command, `shotgate shots --margin M` or `shotgate shots --effect-size W [--alpha A]
[--power P]`, exposes the two sample-size functions directly for planning a workflow's shot
count before writing it.

## Consequences

- **+** Every `state_probability` result now carries its own confidence interval, making explicit
  how much the measured probability could plausibly move on a re-run at the same shot count, not
  just whether the point estimate crossed a threshold.
- **+** `shotgate shots` answers the sample-size question directly instead of requiring a user to
  apply the standard-error formula by hand; verified against a hand calculation
  (`shots_for_power(0.05, alpha=0.01, power=0.9) == 5952`, matching
  `((2.575829 + 1.281552) / 0.05)^2`).
- **+** Pure stdlib, no SciPy: consistent with the SDK-free core invariant (ADR-0002); the
  `_norm_ppf` Newton iteration adds negligible cost (a handful of `erf` evaluations) and no new
  dependency.
- **+** Backward compatible: `state_probability`'s `metrics` dict only grows two keys; no schema
  change, no `v1alpha1` bump.
- **-** `shots_for_margin`/`shots_for_power` use the normal approximation to the binomial, which is
  the standard planning formula but is not exact for small `n`; it is a planning aid for choosing
  a shot count in advance, not a substitute for the exact Wilson interval computed after the run.
- **-** The Wilson interval is currently attached only to `state_probability`; extending it to
  other single-probability-flavoured oracles (e.g. `most_frequent_outcome`) is left for a
  follow-up rather than done here, to keep this change's blast radius to one oracle.

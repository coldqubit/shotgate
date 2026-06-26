# ADR-0007: Fail-closed workflow validation (empty gates and malformed expected distributions)

- **Status:** Accepted
- **Date:** 2026-06-26

## Context

Two ways a shotgate gate could pass while not actually validating anything were found
by exercising the runner and the schema:

1. **A job with no assertions reported PASS.** The runner computed
   `all(o.passed for o in outcomes)`, and `all([])` is `True`, so a workflow whose
   jobs declared `assertions: []` passed the pipeline while checking nothing. A quality
   gate that can be green without testing is a correctness hazard, not a convenience.
2. **Expected distributions accepted any string key.** The `expected` maps of the
   distribution oracles, and the `state`/`states` fields, were typed `dict[str, float]`
   / `str` / `list[str]` with no constraint, so a 3-bit key against a 2-qubit circuit,
   mixed-width keys, or a typo like `"0x"` parsed cleanly and were then silently
   mis-compared, producing a wrong-but-green result instead of an error.

## Decision

shotgate validates fail-closed: a gate that cannot meaningfully check something is an
error, not a pass.

1. **An empty gate fails by default.** A job that runs but declares no assertions is
   marked failed with an explanatory message. The behaviour is opt-out: `--allow-empty`
   on `shotgate run` (or `allow_empty=True` on `Runner`) restores a passing empty job
   for the rare case where that is intended (a placeholder, a circuit-only smoke run).
2. **Basis-state keys are validated at schema-parse time.** Keys in `expected`, and the
   `state`/`states` fields, must be non-empty, contain only `0`/`1` (whitespace from
   multi-register formatting is stripped, matching `metrics.clean_key`), and all
   describe the same number of bits. A malformed key now raises a pydantic
   `ValidationError` with the offending key named.

## Consequences

- **+** No silent no-op gates: a green shotgate run means assertions actually ran.
- **+** Distribution typos fail fast at load time with a clear message, the same way the
  strict (`extra="forbid"`) schema already catches unknown fields.
- **+** The cross-check against the circuit's qubit width is now well-defined to add at
  evaluate time later, because the keys are guaranteed internally consistent.
- **-** This is a behaviour change: a previously-passing empty gate now fails, and a
  workflow with a malformed key that previously parsed now raises. Both are pre-1.0
  (`0.x`) and intended; the empty-gate change is documented in `CHANGELOG.md`, and the
  escape hatch (`--allow-empty`) covers the legitimate case.
- The validation is internal-consistency only (binary, equal width). Matching the key
  width to the executed circuit's classical-bit count is a separate evaluate-time check
  deferred to a later version.

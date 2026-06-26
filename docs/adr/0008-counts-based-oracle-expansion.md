# ADR-0008: Counts-based oracle expansion (divergence, entropy, expectation, mode)

- **Status:** Accepted
- **Date:** 2026-06-26

## Context

shotgate shipped five assertion oracles: a distance test (`distribution_tvd`), a
goodness-of-fit test (`chi_square`), a closeness score (`hellinger_fidelity`), a marginal
(`state_probability`), and a structural/leakage bound (`allowed_states`). The quantum
software-testing field, and adjacent tools such as QUTest, cover a wider assertion set,
notably observable expectation values, distribution entropy, and information-theoretic
divergence. These are real gaps for a tool that markets itself as the statistical quality
gate for quantum circuits.

The constraint that has served the project well is that oracles are **counts-based and
pure-Python**: each assertion's `evaluate(counts, shots)` operates only on a histogram of
measured bitstrings, so the validation core never imports a quantum SDK (ADR-0002).

## Decision

Add four oracles that stay inside that contract, taking the count from five to nine:

1. `kl_divergence`: bound the Kullback-Leibler divergence `D(observed || expected)` in bits.
2. `shannon_entropy`: bound the distribution's Shannon entropy (min/max bits).
3. `expectation_value`: bound the Pauli-Z product `<Z_{q0} Z_{q1} ...>` in `[-1, 1]`, read
   off the computational-basis counts as a parity expectation.
4. `most_frequent_outcome`: assert the modal measured state, optionally above a probability.

Two related oracles are **deferred** because they do not fit the `evaluate(counts, shots)`
contract:

- **Arbitrary-Pauli observables** (e.g. `<X>`, `<Y>`, entanglement witnesses) need
  basis-change measurement circuits, not just computational-basis counts. `expectation_value`
  is therefore Z-basis only for now.
- **Structural assertions on the circuit** (depth, width, gate-set membership) need the
  circuit/telemetry, which `evaluate` does not receive; they require a signature change and
  are left to a later version.

## Consequences

- **+** Closes the distribution/observable breadth gap while keeping the core SDK-free and
  unit-tested against analytic values (`<Z0 Z1> = +1` for a Bell pair, `H = 1` bit for a
  balanced two-outcome distribution, `D(p||p) = 0`).
- **+** `expectation_value` gives a hardware-friendly single-number observable to track,
  complementing the distribution oracles.
- **-** `kl_divergence` inherits the zero-support pathology of `chi_square`: an ideal
  `expected` that assigns probability 0 to a device's error states diverges to infinity, so
  KL is simulator-oriented unless `expected` is noise-aware (the v0.5 work). The reporter
  serialises a non-finite metric as JSON `null` so output stays valid.
- **-** `expectation_value` covers only Z-basis products; the broader Pauli and
  entanglement-witness oracles remain future work, as do the circuit-structural oracles.

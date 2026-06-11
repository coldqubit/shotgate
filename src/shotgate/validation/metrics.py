# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Statistical metrics for comparing quantum measurement distributions.

Quantum programs are *probabilistic*: running the same circuit twice yields
different shot counts. Validating them in CI therefore cannot use exact equality;
it requires statistical oracles. This module implements those oracles in pure
Python (only the standard library), so the validation core has no heavy
dependencies and runs in any container or CI runner.

All functions operate on *distributions* expressed as ``{bitstring: value}``
mappings. Helper functions normalise raw shot counts into probability
distributions and reconcile differing supports.

References
----------
- Hellinger fidelity is the squared Bhattacharyya coefficient, matching the
  definition used by ``qiskit.quantum_info.hellinger_fidelity``.
- The chi-square goodness-of-fit p-value is computed from the regularised upper
  incomplete gamma function Q(a, x) using the series / continued-fraction
  algorithms of *Numerical Recipes* (Press et al.), avoiding a SciPy dependency.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

Distribution = Mapping[str, float]
Counts = Mapping[str, int]

__all__ = [
    "bhattacharyya_coefficient",
    "chi2_sf",
    "chi_square_statistic",
    "chi_square_test",
    "clean_key",
    "counts_to_probabilities",
    "hellinger_distance",
    "hellinger_fidelity",
    "normalize",
    "state_probability",
    "support_leakage",
    "total_variation_distance",
]


def clean_key(key: str) -> str:
    """Normalise a measurement key.

    Qiskit may format multi-register results with spaces (``"01 1"``). We strip
    whitespace so user-supplied expected distributions and backend counts use a
    consistent, register-agnostic bitstring representation.
    """
    return key.replace(" ", "")


def counts_to_probabilities(counts: Counts) -> dict[str, float]:
    """Convert raw shot counts into a normalised probability distribution."""
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("cannot build a probability distribution from empty counts")
    probs: dict[str, float] = {}
    for key, value in counts.items():
        if value < 0:
            raise ValueError(f"negative count for {key!r}: {value}")
        probs[clean_key(key)] = probs.get(clean_key(key), 0.0) + value / total
    return probs


def normalize(distribution: Distribution) -> dict[str, float]:
    """Return a copy of ``distribution`` normalised to sum to 1."""
    cleaned: dict[str, float] = {}
    for key, value in distribution.items():
        if value < 0:
            raise ValueError(f"negative probability for {key!r}: {value}")
        cleaned[clean_key(key)] = cleaned.get(clean_key(key), 0.0) + float(value)
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("cannot normalise a distribution that sums to zero")
    return {key: value / total for key, value in cleaned.items()}


def _domain(p: Distribution, q: Distribution) -> list[str]:
    return sorted(set(p) | set(q))


def total_variation_distance(p: Distribution, q: Distribution) -> float:
    """Total variation distance ``0.5 * sum_i |p_i - q_i|`` in ``[0, 1]``.

    A value of 0 means the distributions are identical; 1 means disjoint support.
    """
    p = normalize(p)
    q = normalize(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in _domain(p, q))


def bhattacharyya_coefficient(p: Distribution, q: Distribution) -> float:
    """Bhattacharyya coefficient ``sum_i sqrt(p_i q_i)`` in ``[0, 1]``."""
    p = normalize(p)
    q = normalize(q)
    return sum(math.sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in _domain(p, q))


def hellinger_fidelity(p: Distribution, q: Distribution) -> float:
    """Classical (Hellinger) fidelity between two distributions in ``[0, 1]``.

    Defined as the squared Bhattacharyya coefficient, identical to
    ``qiskit.quantum_info.hellinger_fidelity``. 1.0 means the distributions match
    exactly.
    """
    bc = bhattacharyya_coefficient(p, q)
    return min(1.0, max(0.0, bc * bc))


def hellinger_distance(p: Distribution, q: Distribution) -> float:
    """Hellinger distance ``sqrt(1 - BC)`` in ``[0, 1]``."""
    bc = bhattacharyya_coefficient(p, q)
    return math.sqrt(max(0.0, 1.0 - bc))


def state_probability(counts: Counts, state: str) -> float:
    """Return the measured probability of a single basis state."""
    return counts_to_probabilities(counts).get(clean_key(state), 0.0)


def support_leakage(counts: Counts, allowed_states: list[str]) -> float:
    """Probability mass measured *outside* an allowed set of basis states.

    Useful as a structural oracle: e.g. a perfect GHZ circuit should only ever
    produce all-zeros or all-ones; everything else is leakage.
    """
    allowed = {clean_key(s) for s in allowed_states}
    probs = counts_to_probabilities(counts)
    return sum(prob for key, prob in probs.items() if key not in allowed)


# --------------------------------------------------------------------------- #
# Chi-square goodness-of-fit
# --------------------------------------------------------------------------- #

# Floor for expected counts to keep the chi-square statistic finite. A basis
# state that is *expected* with probability 0 but observed with nonzero counts
# (leakage) yields a huge contribution -> correctly fails the test.
_MIN_EXPECTED = 1e-12


def chi_square_statistic(counts: Counts, expected: Distribution) -> tuple[float, int]:
    """Pearson chi-square statistic and degrees of freedom.

    The expected distribution is normalised and scaled by the total number of
    shots. The domain is the union of observed and expected basis states; degrees
    of freedom is ``len(domain) - 1``.
    """
    observed: dict[str, float] = {}
    for key, value in counts.items():
        observed[clean_key(key)] = observed.get(clean_key(key), 0.0) + value
    shots = sum(observed.values())
    if shots <= 0:
        raise ValueError("cannot run a chi-square test on empty counts")

    expected_probs = normalize(expected)
    domain = _domain(observed, expected_probs)

    statistic = 0.0
    for key in domain:
        obs = observed.get(key, 0.0)
        exp = max(shots * expected_probs.get(key, 0.0), _MIN_EXPECTED)
        statistic += (obs - exp) ** 2 / exp

    dof = max(len(domain) - 1, 0)
    return statistic, dof


def chi_square_test(counts: Counts, expected: Distribution) -> tuple[float, int, float]:
    """Run a chi-square goodness-of-fit test.

    Returns ``(statistic, degrees_of_freedom, p_value)``. A large p-value means we
    *fail to reject* the null hypothesis that the observed counts were drawn from
    the expected distribution, i.e. the circuit behaves as specified.
    """
    statistic, dof = chi_square_statistic(counts, expected)
    p_value = chi2_sf(statistic, dof)
    return statistic, dof, p_value


def chi2_sf(statistic: float, dof: int) -> float:
    """Survival function (1 - CDF) of the chi-square distribution.

    Equivalent to ``scipy.stats.chi2.sf(statistic, dof)`` but implemented with the
    standard library only, via the regularised upper incomplete gamma function
    ``Q(dof/2, statistic/2)``.
    """
    if dof <= 0:
        return 1.0 if statistic <= 0 else 0.0
    if statistic <= 0:
        return 1.0
    return _gamma_q(dof / 2.0, statistic / 2.0)


def _gamma_q(a: float, x: float) -> float:
    """Regularised upper incomplete gamma function Q(a, x) = 1 - P(a, x)."""
    if x < 0 or a <= 0:
        raise ValueError("invalid arguments to the incomplete gamma function")
    if x == 0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gamma_p_series(a, x)
    return _gamma_q_cf(a, x)


def _gamma_p_series(a: float, x: float, *, max_iter: int = 10_000) -> float:
    """Lower incomplete gamma P(a, x) via its power series (good for x < a + 1)."""
    ap = a
    term = 1.0 / a
    total = term
    for _ in range(max_iter):
        ap += 1.0
        term *= x / ap
        total += term
        if abs(term) < abs(total) * 1e-16:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_q_cf(a: float, x: float, *, max_iter: int = 10_000) -> float:
    """Upper incomplete gamma Q(a, x) via the Lentz continued fraction."""
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, max_iter):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h

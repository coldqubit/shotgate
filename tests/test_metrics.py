"""Unit tests for the statistical metrics core (no quantum SDK required)."""

from __future__ import annotations

import math

import pytest

from qforge.validation import metrics


def test_counts_to_probabilities_normalises_and_strips_whitespace():
    probs = metrics.counts_to_probabilities({"0 0": 25, "11": 75})
    assert probs == {"00": 0.25, "11": 0.75}


def test_counts_to_probabilities_rejects_empty():
    with pytest.raises(ValueError):
        metrics.counts_to_probabilities({})


def test_tvd_identical_is_zero():
    p = {"00": 0.5, "11": 0.5}
    assert metrics.total_variation_distance(p, p) == pytest.approx(0.0)


def test_tvd_disjoint_is_one():
    assert metrics.total_variation_distance({"00": 1.0}, {"11": 1.0}) == pytest.approx(1.0)


def test_tvd_symmetry_and_value():
    p = {"00": 0.6, "11": 0.4}
    q = {"00": 0.5, "11": 0.5}
    assert metrics.total_variation_distance(p, q) == pytest.approx(0.1)
    assert metrics.total_variation_distance(q, p) == pytest.approx(0.1)


def test_hellinger_fidelity_identical_is_one():
    p = {"00": 0.5, "11": 0.5}
    assert metrics.hellinger_fidelity(p, p) == pytest.approx(1.0)


def test_hellinger_fidelity_disjoint_is_zero():
    assert metrics.hellinger_fidelity({"00": 1.0}, {"11": 1.0}) == pytest.approx(0.0)


def test_hellinger_distance_matches_definition():
    p = {"0": 1.0}
    q = {"0": 0.5, "1": 0.5}
    # BC = sqrt(0.5) => H = sqrt(1 - sqrt(0.5))
    expected = math.sqrt(1 - math.sqrt(0.5))
    assert metrics.hellinger_distance(p, q) == pytest.approx(expected)


def test_support_leakage():
    counts = {"00": 480, "11": 500, "01": 20}
    leakage = metrics.support_leakage(counts, ["00", "11"])
    assert leakage == pytest.approx(0.02)


def test_state_probability():
    counts = {"00": 400, "11": 600}
    assert metrics.state_probability(counts, "11") == pytest.approx(0.6)
    assert metrics.state_probability(counts, "01") == 0.0


@pytest.mark.parametrize(
    "stat,dof,expected",
    [
        (0.0, 1, 1.0),
        (3.841458820694124, 1, 0.05),  # chi2 0.95 quantile, dof=1
        (5.991464547107979, 2, 0.05),  # chi2 0.95 quantile, dof=2
        (11.070497693516351, 5, 0.05),  # chi2 0.95 quantile, dof=5
        (0.0, 0, 1.0),
    ],
)
def test_chi2_survival_function_matches_known_quantiles(stat, dof, expected):
    assert metrics.chi2_sf(stat, dof) == pytest.approx(expected, abs=1e-4)


def test_chi_square_test_perfect_fit_high_pvalue():
    # Observed exactly matches expected -> statistic ~0 -> p-value ~1.
    counts = {"00": 500, "11": 500}
    stat, dof, p = metrics.chi_square_test(counts, {"00": 0.5, "11": 0.5})
    assert stat == pytest.approx(0.0, abs=1e-9)
    assert dof == 1
    assert p == pytest.approx(1.0)


def test_chi_square_test_bad_fit_low_pvalue():
    # Heavily skewed observations against a uniform expectation.
    counts = {"00": 900, "11": 100}
    _, _, p = metrics.chi_square_test(counts, {"00": 0.5, "11": 0.5})
    assert p < 0.001


def test_chi_square_penalises_leakage():
    # An outcome expected with probability 0 but observed -> should reject.
    counts = {"00": 480, "11": 480, "01": 40}
    _, _, p = metrics.chi_square_test(counts, {"00": 0.5, "11": 0.5})
    assert p < 0.001

"""Unit tests for the statistical metrics core (no quantum SDK required)."""

from __future__ import annotations

import math

import pytest

from shotgate.validation import metrics


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


def test_shannon_entropy_uniform_and_deterministic():
    assert metrics.shannon_entropy({"00": 50, "11": 50}) == pytest.approx(1.0)
    assert metrics.shannon_entropy({"00": 100}) == pytest.approx(0.0)
    assert metrics.shannon_entropy(
        {"00": 25, "01": 25, "10": 25, "11": 25}
    ) == pytest.approx(2.0)


def test_kl_divergence_zero_value_and_infinite():
    p = {"00": 0.5, "11": 0.5}
    assert metrics.kl_divergence(p, p) == pytest.approx(0.0)
    # D({1:1} || {0:0.5, 1:0.5}) = 1 bit
    assert metrics.kl_divergence({"1": 1.0}, {"0": 0.5, "1": 0.5}) == pytest.approx(1.0)
    # q assigns zero to an outcome p observes -> infinite (zero-support pathology)
    assert metrics.kl_divergence({"00": 0.5, "01": 0.5}, {"00": 1.0}) == math.inf


def test_z_expectation_values():
    assert metrics.z_expectation({"00": 50, "11": 50}, [0, 1]) == pytest.approx(1.0)
    assert metrics.z_expectation({"01": 50, "10": 50}, [0, 1]) == pytest.approx(-1.0)
    assert metrics.z_expectation({"0": 100}, [0]) == pytest.approx(1.0)
    assert metrics.z_expectation({"1": 100}, [0]) == pytest.approx(-1.0)
    assert metrics.z_expectation({"0": 50, "1": 50}, [0]) == pytest.approx(0.0)


def test_z_expectation_rejects_out_of_range_qubit():
    with pytest.raises(ValueError):
        metrics.z_expectation({"00": 100}, [2])


def test_most_frequent_outcome_and_tie_break():
    state, prob = metrics.most_frequent_outcome({"11": 70, "00": 30})
    assert state == "11"
    assert prob == pytest.approx(0.7)
    # tie -> lexicographically smallest bitstring
    assert metrics.most_frequent_outcome({"11": 50, "00": 50})[0] == "00"


def test_apply_readout_error_identity_and_mass_on_errors():
    ideal = {"00": 0.5, "11": 0.5}
    # No readout error -> identity (zero mass on the error states).
    assert metrics.apply_readout_error(ideal, 0.0, 0.0) == pytest.approx(
        {"00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5}
    )
    # With readout error, the error states gain mass and the result stays a distribution.
    noisy = metrics.apply_readout_error(ideal, 0.07, 0.075)
    assert noisy["01"] > 0.0 and noisy["10"] > 0.0
    assert sum(noisy.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "p,expected_z",
    [
        (0.90, 1.6448536269514722),
        (0.95, 1.959963984540054),
        (0.99, 2.5758293035489),
    ],
)
def test_norm_ppf_matches_known_z_values(p, expected_z):
    assert metrics._norm_ppf(0.5 + p / 2.0) == pytest.approx(expected_z, abs=1e-9)


def test_wilson_interval_matches_textbook_and_stays_in_unit_range():
    # p=0.5, n=8192: half-width ~= 1.96 * sqrt(0.25/8192) =~ 0.01083 (textbook normal approx).
    lo, hi = metrics.wilson_interval(4096, 8192)
    assert lo == pytest.approx(0.5 - 0.01083, abs=2e-3)
    assert hi == pytest.approx(0.5 + 0.01083, abs=2e-3)
    # Zero successes: the naive p +/- z*sqrt(p(1-p)/n) interval would be degenerate ([0, 0]);
    # Wilson's form correctly stays inside [0, 1] and is asymmetric.
    lo0, hi0 = metrics.wilson_interval(0, 100)
    assert lo0 == pytest.approx(0.0, abs=1e-9)
    assert 0.0 < hi0 < 1.0
    with pytest.raises(ValueError):
        metrics.wilson_interval(5, 0)
    with pytest.raises(ValueError):
        metrics.wilson_interval(-1, 10)


def test_shots_for_margin_scales_as_expected():
    # Halving the margin should ~quadruple the required shots (n ~ 1/margin^2).
    n_01 = metrics.shots_for_margin(0.5, 0.01)
    n_005 = metrics.shots_for_margin(0.5, 0.005)
    assert n_005 == pytest.approx(4 * n_01, rel=0.01)
    # p=0.5 (max variance) needs more shots than p=0.1 for the same margin.
    assert metrics.shots_for_margin(0.5, 0.01) > metrics.shots_for_margin(0.1, 0.01)
    with pytest.raises(ValueError):
        metrics.shots_for_margin(0.5, 0.0)
    with pytest.raises(ValueError):
        metrics.shots_for_margin(0.0, 0.01)


def test_shots_for_power_hand_calculation():
    # z(alpha=0.01, two-sided) = 2.575829, z(power=0.9, one-sided) = 1.281552.
    # n = ((2.575829 + 1.281552) / 0.05)^2 = 5951.75 -> ceil 5952.
    assert metrics.shots_for_power(0.05, alpha=0.01, power=0.9) == 5952
    # A larger effect size is easier to detect -> fewer shots needed.
    assert metrics.shots_for_power(0.10, alpha=0.01, power=0.9) < metrics.shots_for_power(
        0.05, alpha=0.01, power=0.9
    )
    with pytest.raises(ValueError):
        metrics.shots_for_power(0.0)

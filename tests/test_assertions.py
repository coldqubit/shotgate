"""Unit tests for the assertion oracles (no quantum SDK required)."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from shotgate.validation.assertions import (
    AllowedStatesAssertion,
    Assertion,
    ChiSquareAssertion,
    DistributionTVDAssertion,
    HellingerFidelityAssertion,
    StateProbabilityAssertion,
)

ADAPTER = TypeAdapter(Assertion)

BELL_COUNTS = {"00": 4096, "11": 4096}
NOISY_COUNTS = {"00": 4000, "11": 4000, "01": 96, "10": 96}


def test_discriminated_union_parses_by_type():
    obj = ADAPTER.validate_python(
        {"type": "distribution_tvd", "expected": {"00": 0.5, "11": 0.5}}
    )
    assert isinstance(obj, DistributionTVDAssertion)


def test_unknown_type_rejected():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "telepathy", "expected": {}})


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {"type": "distribution_tvd", "expected": {"00": 1.0}, "bogus": 1}
        )


def test_tvd_pass_and_fail():
    a = DistributionTVDAssertion(
        type="distribution_tvd", expected={"00": 0.5, "11": 0.5}, max_distance=0.05
    )
    assert a.evaluate(BELL_COUNTS, 8192).passed is True

    strict = DistributionTVDAssertion(
        type="distribution_tvd", expected={"00": 1.0}, max_distance=0.01
    )
    assert strict.evaluate(BELL_COUNTS, 8192).passed is False


def test_hellinger_fidelity_pass():
    a = HellingerFidelityAssertion(
        type="hellinger_fidelity", expected={"00": 0.5, "11": 0.5}, min_fidelity=0.99
    )
    result = a.evaluate(BELL_COUNTS, 8192)
    assert result.passed is True
    assert result.metrics["fidelity"] == pytest.approx(1.0, abs=1e-6)


def test_chi_square_pass_on_good_fit():
    a = ChiSquareAssertion(
        type="chi_square", expected={"00": 0.5, "11": 0.5}, significance=0.01
    )
    assert a.evaluate(BELL_COUNTS, 8192).passed is True


def test_chi_square_fail_on_bad_fit():
    a = ChiSquareAssertion(
        type="chi_square", expected={"00": 0.5, "11": 0.5}, significance=0.05
    )
    assert a.evaluate({"00": 7000, "11": 1192}, 8192).passed is False


def test_allowed_states_leakage_budget():
    forbid = AllowedStatesAssertion(
        type="allowed_states", states=["00", "11"], max_leakage=0.0
    )
    assert forbid.evaluate(BELL_COUNTS, 8192).passed is True
    assert forbid.evaluate(NOISY_COUNTS, 8192).passed is False

    tolerant = AllowedStatesAssertion(
        type="allowed_states", states=["00", "11"], max_leakage=0.05
    )
    assert tolerant.evaluate(NOISY_COUNTS, 8192).passed is True


def test_state_probability_window_and_alias():
    a = ADAPTER.validate_python(
        {"type": "state_probability", "state": "00", "min": 0.45, "max": 0.55}
    )
    assert isinstance(a, StateProbabilityAssertion)
    assert a.evaluate(BELL_COUNTS, 8192).passed is True


def test_state_probability_requires_a_bound():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "state_probability", "state": "00"})


def test_state_probability_equals_with_tolerance():
    a = StateProbabilityAssertion(
        type="state_probability", state="00", equals=0.5, tolerance=0.02
    )
    assert a.evaluate(BELL_COUNTS, 8192).passed is True
    assert a.evaluate({"00": 6000, "11": 2192}, 8192).passed is False


def test_expected_rejects_non_binary_key():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {"type": "distribution_tvd", "expected": {"0x": 0.5, "11": 0.5}}
        )


def test_expected_rejects_mixed_widths():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {"type": "chi_square", "expected": {"0": 0.5, "11": 0.5}}
        )


def test_state_rejects_non_binary():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {"type": "state_probability", "state": "2", "min": 0.4}
        )


def test_allowed_states_rejects_malformed_and_mixed_width():
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "allowed_states", "states": ["00", "1z"]})
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "allowed_states", "states": ["0", "11"]})


def test_multiregister_spaced_keys_are_accepted():
    # Qiskit can format multi-register results with spaces; they normalise to a
    # consistent width and must remain valid.
    a = ADAPTER.validate_python(
        {"type": "distribution_tvd", "expected": {"0 1": 0.5, "1 1": 0.5}}
    )
    assert isinstance(a, DistributionTVDAssertion)

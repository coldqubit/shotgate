"""Unit tests for the assertion oracles (no quantum SDK required)."""

from __future__ import annotations

import math

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


def test_kl_divergence_pass_and_diverge():
    a = ADAPTER.validate_python(
        {"type": "kl_divergence", "expected": {"00": 0.5, "11": 0.5}, "max_divergence": 0.05}
    )
    assert a.evaluate(BELL_COUNTS, 8192).passed is True
    # Leakage into a state the expected distribution forbids -> divergence is infinite.
    res = a.evaluate(NOISY_COUNTS, 8192)
    assert res.passed is False
    assert res.metrics["kl_divergence"] == math.inf


def test_shannon_entropy_window_and_requires_bound():
    a = ADAPTER.validate_python({"type": "shannon_entropy", "min": 0.9, "max": 1.1})
    assert a.evaluate(BELL_COUNTS, 8192).passed is True  # H = 1.0 bit
    assert a.evaluate({"00": 8192}, 8192).passed is False  # H = 0
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "shannon_entropy"})


def test_expectation_value_window_equals_and_validation():
    a = ADAPTER.validate_python(
        {"type": "expectation_value", "qubits": [0, 1], "min": 0.95}
    )
    assert a.evaluate(BELL_COUNTS, 8192).passed is True  # <Z0Z1> = +1
    anti = ADAPTER.validate_python(
        {"type": "expectation_value", "qubits": [0, 1], "equals": -1.0, "tolerance": 0.05}
    )
    assert anti.evaluate({"01": 50, "10": 50}, 100).passed is True  # <Z0Z1> = -1
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "expectation_value", "qubits": [0]})
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(
            {"type": "expectation_value", "qubits": [0, 0], "min": 0.0}
        )


def test_most_frequent_outcome():
    a = ADAPTER.validate_python(
        {"type": "most_frequent_outcome", "state": "11", "min_probability": 0.6}
    )
    assert a.evaluate({"11": 70, "00": 30}, 100).passed is True
    assert a.evaluate({"11": 40, "00": 60}, 100).passed is False  # mode is 00


# Real ibm_fez Bell diagnostic counts (docs/hardware-validation.md section 9).
IBM_FEZ_BELL = {"00": 1779, "11": 1764, "10": 304, "01": 249}


def test_chi_square_noise_aware_expected_gates_hardware_counts():
    plain = ADAPTER.validate_python(
        {"type": "chi_square", "expected": {"00": 0.5, "11": 0.5}, "significance": 0.01}
    )
    assert plain.evaluate(IBM_FEZ_BELL, 4096).passed is False  # p = 0 against ideal
    aware = ADAPTER.validate_python(
        {
            "type": "chi_square",
            "expected": {"00": 0.5, "11": 0.5},
            "significance": 0.01,
            "readout_error": {"p0": 0.07, "p1": 0.075},
        }
    )
    res = aware.evaluate(IBM_FEZ_BELL, 4096)
    assert res.passed is True
    assert res.metrics["p_value"] > 0.01


def test_circuit_depth_window_and_validation():
    cm = {"depth": 5, "operations": {"h": 1, "cx": 2, "measure": 3}}
    a = ADAPTER.validate_python({"type": "circuit_depth", "max": 10})
    assert a.evaluate({}, 0, circuit_metrics=cm).passed is True
    tight = ADAPTER.validate_python({"type": "circuit_depth", "max": 3})
    assert tight.evaluate({}, 0, circuit_metrics=cm).passed is False
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"type": "circuit_depth"})  # needs a bound
    # No circuit metrics -> fails closed.
    assert a.evaluate({}, 0, circuit_metrics=None).passed is False


def test_gate_set_membership_auto_allows_measure():
    cm = {"depth": 3, "operations": {"h": 1, "cx": 1, "measure": 2}}
    ok = ADAPTER.validate_python({"type": "gate_set", "allowed": ["h", "cx"]})
    assert ok.evaluate({}, 0, circuit_metrics=cm).passed is True  # measure auto-allowed
    bad = ADAPTER.validate_python({"type": "gate_set", "allowed": ["h"]})
    res = bad.evaluate({}, 0, circuit_metrics=cm)
    assert res.passed is False
    assert "cx" in res.message


def test_structural_oracles_do_not_need_counts():
    from shotgate.validation.assertions import (
        CircuitDepthAssertion,
        GateSetAssertion,
    )

    assert CircuitDepthAssertion.needs_counts is False
    assert GateSetAssertion.needs_counts is False
    assert DistributionTVDAssertion.needs_counts is True


def test_kl_divergence_noise_aware_expected_is_finite_on_hardware_counts():
    plain = ADAPTER.validate_python(
        {"type": "kl_divergence", "expected": {"00": 0.5, "11": 0.5}, "max_divergence": 0.1}
    )
    assert plain.evaluate(IBM_FEZ_BELL, 4096).metrics["kl_divergence"] == math.inf
    aware = ADAPTER.validate_python(
        {
            "type": "kl_divergence",
            "expected": {"00": 0.5, "11": 0.5},
            "max_divergence": 0.1,
            "readout_error": {"p0": 0.07, "p1": 0.075},
        }
    )
    res = aware.evaluate(IBM_FEZ_BELL, 4096)
    assert math.isfinite(res.metrics["kl_divergence"])
    assert res.passed is True

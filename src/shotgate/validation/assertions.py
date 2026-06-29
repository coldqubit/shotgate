# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Declarative, statistically-grounded assertions over quantum measurement counts.

Each assertion is a Pydantic model (so it is self-validating when parsed from a
workflow YAML) that knows how to ``evaluate`` itself against backend counts and
return a structured :class:`AssertionResult`. New oracle types are added by
defining a model with a unique ``type`` literal and registering it in
``ASSERTION_TYPES``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shotgate.validation import metrics


def _validate_bitstring_keys(keys: Iterable[str], *, field: str) -> None:
    """Reject malformed basis-state keys at schema-parse time.

    Keys must be non-empty, contain only ``0``/``1`` (whitespace from multi-register
    formatting is stripped, matching :func:`metrics.clean_key`), and all describe the
    same number of bits. This turns a silently mis-compared distribution (e.g. a
    3-bit key against a 2-qubit circuit, or a typo like ``"0x"``) into a clear
    validation error instead of a wrong-but-green result.
    """
    originals = list(keys)
    cleaned = [k.replace(" ", "") for k in originals]
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    widths: set[int] = set()
    for original, c in zip(originals, cleaned, strict=True):
        if not c or set(c) - {"0", "1"}:
            raise ValueError(
                f"{field} key {original!r} is not a valid bitstring "
                "(non-empty, characters 0/1 only)"
            )
        widths.add(len(c))
    if len(widths) > 1:
        raise ValueError(
            f"{field} mixes bitstring widths {sorted(widths)}; all keys must "
            "describe the same number of bits"
        )


@dataclass
class AssertionResult:
    """Outcome of evaluating a single assertion."""

    type: str
    label: str
    passed: bool
    message: str
    metrics: dict[str, float] = field(default_factory=dict)


class ReadoutErrorSpec(BaseModel):
    """A per-qubit readout (assignment) error model, declared from device calibration.

    Used to make ``chi_square``/``kl_divergence`` noise-aware so they can gate on hardware:
    the ideal ``expected`` distribution is transformed through this channel before
    comparison, giving it nonzero mass on the device's error states. The parameters come
    from the device's readout calibration, not from the measured counts.
    """

    model_config = ConfigDict(extra="forbid")
    p0: float = Field(0.0, ge=0.0, le=1.0)  # P(measure 1 | prepared 0)
    p1: float = Field(0.0, ge=0.0, le=1.0)  # P(measure 0 | prepared 1)


def _noise_aware_expected(
    expected: dict[str, float],
    readout_error: ReadoutErrorSpec | Literal["auto"] | None,
    noise_model: Literal["auto"] | None,
    backend_metadata: dict[str, Any] | None,
) -> tuple[dict[str, float], str]:
    """Resolve the expected distribution a goodness-of-fit oracle compares against.

    Three escalating sources of a noise-aware expected, with ``noise_model`` taking
    precedence (the schema forbids setting both ``noise_model`` and ``readout_error``):

    - ``noise_model: "auto"`` (digital twin): use the device's *full* calibrated noise
      model simulated on the circuit (gate + readout + thermal relaxation), attached to
      ``backend_metadata['noise_model_expected']`` by the backend. This compares the device
      against its own calibrated model, which captures the gate and decoherence leakage a
      readout transform cannot (ADR-0014). A noiseless run carries no twin, so this falls
      back to the ideal ``expected`` (the plain test).
    - ``readout_error`` as a ``ReadoutErrorSpec``: the ideal transformed through that fixed
      per-qubit readout (assignment) model.
    - ``readout_error: "auto"``: the ideal transformed through the device's published
      readout calibration (``backend_metadata['readout_calibration']``), falling back to the
      ideal when none is reported (a noiseless simulator).

    With every option ``None`` the ideal ``expected`` is returned unchanged (the plain test).
    The ``"auto"`` modes are what let one workflow gate with the plain test on a simulator
    and the calibrated/twin one on a QPU, with no per-device editing.

    Returns ``(effective_expected, note)``; ``note`` annotates the result message.
    """
    if noise_model == "auto":
        twin = (backend_metadata or {}).get("noise_model_expected")
        if isinstance(twin, dict) and twin.get("distribution"):
            return (
                dict(twin["distribution"]),
                f" [noise-aware: twin {twin.get('source', 'device')}]",
            )
        return expected, ""
    if readout_error is None:
        return expected, ""
    if readout_error == "auto":
        cal = (backend_metadata or {}).get("readout_calibration")
        if not cal:
            return expected, ""
        eff = metrics.apply_readout_error(expected, float(cal["p0"]), float(cal["p1"]))
        return eff, (
            f" [noise-aware: {cal.get('source', 'device')} "
            f"p0={float(cal['p0']):.3f} p1={float(cal['p1']):.3f}]"
        )
    eff = metrics.apply_readout_error(expected, readout_error.p0, readout_error.p1)
    return eff, " [noise-aware expected]"


class _BaseAssertion(BaseModel):
    """Common configuration shared by every assertion model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    label: str | None = None

    #: Whether this oracle needs measured counts (so the circuit must be executed).
    #: Structural oracles set this False, letting the runner skip execution for a job
    #: whose assertions are all static circuit-property checks.
    needs_counts: ClassVar[bool] = True

    def display_label(self) -> str:
        return self.label or self.default_label()

    def default_label(self) -> str:  # pragma: no cover - overridden by subclasses
        return self.__class__.__name__


class DistributionTVDAssertion(_BaseAssertion):
    """Bound the total variation distance to an expected distribution.

    Robust, interpretable, and shot-count agnostic: ``max_distance`` is the
    largest acceptable statistical "gap" between the measured and expected
    distributions, in ``[0, 1]``.
    """

    type: Literal["distribution_tvd"]
    expected: dict[str, float]
    max_distance: float = Field(0.05, ge=0.0, le=1.0)

    @field_validator("expected")
    @classmethod
    def _check_expected(cls, v: dict[str, float]) -> dict[str, float]:
        _validate_bitstring_keys(v.keys(), field="expected")
        return v

    def default_label(self) -> str:
        return f"TVD <= {self.max_distance}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        probs = metrics.counts_to_probabilities(counts)
        distance = metrics.total_variation_distance(probs, self.expected)
        passed = distance <= self.max_distance
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"total variation distance {distance:.4f} "
            f"({'<=' if passed else '>'} {self.max_distance})",
            metrics={"tvd": distance, "max_distance": self.max_distance},
        )


class HellingerFidelityAssertion(_BaseAssertion):
    """Require a minimum classical (Hellinger) fidelity to an expected distribution."""

    type: Literal["hellinger_fidelity"]
    expected: dict[str, float]
    min_fidelity: float = Field(0.99, ge=0.0, le=1.0)

    @field_validator("expected")
    @classmethod
    def _check_expected(cls, v: dict[str, float]) -> dict[str, float]:
        _validate_bitstring_keys(v.keys(), field="expected")
        return v

    def default_label(self) -> str:
        return f"fidelity >= {self.min_fidelity}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        probs = metrics.counts_to_probabilities(counts)
        fidelity = metrics.hellinger_fidelity(probs, self.expected)
        passed = fidelity >= self.min_fidelity
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"Hellinger fidelity {fidelity:.4f} "
            f"({'>=' if passed else '<'} {self.min_fidelity})",
            metrics={"fidelity": fidelity, "min_fidelity": self.min_fidelity},
        )


class ChiSquareAssertion(_BaseAssertion):
    """Chi-square goodness-of-fit test against an expected distribution.

    Passes when the p-value is at least ``significance``, i.e. we fail to reject
    the hypothesis that the observed counts came from ``expected``. This is the
    classical statistical oracle for quantum output distributions.
    """

    type: Literal["chi_square"]
    expected: dict[str, float]
    significance: float = Field(0.05, gt=0.0, lt=1.0)
    readout_error: ReadoutErrorSpec | Literal["auto"] | None = None
    noise_model: Literal["auto"] | None = None

    @field_validator("expected")
    @classmethod
    def _check_expected(cls, v: dict[str, float]) -> dict[str, float]:
        _validate_bitstring_keys(v.keys(), field="expected")
        return v

    @model_validator(mode="after")
    def _check_noise_aware(self) -> ChiSquareAssertion:
        if self.noise_model is not None and self.readout_error is not None:
            raise ValueError(
                "set only one of noise_model or readout_error: noise_model: auto is the "
                "full device twin (gate + readout + decoherence); readout_error covers "
                "readout only"
            )
        return self

    def default_label(self) -> str:
        return f"chi-square p >= {self.significance}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        expected, suffix = _noise_aware_expected(
            self.expected, self.readout_error, self.noise_model, backend_metadata
        )
        statistic, dof, p_value = metrics.chi_square_test(counts, expected)
        passed = p_value >= self.significance
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"chi-square={statistic:.3f} dof={dof} p-value={p_value:.4f} "
            f"({'>=' if passed else '<'} alpha={self.significance}){suffix}",
            metrics={
                "statistic": statistic,
                "dof": float(dof),
                "p_value": p_value,
                "significance": self.significance,
            },
        )


class StateProbabilityAssertion(_BaseAssertion):
    """Bound the measured probability of a single basis state.

    Use ``min``/``max`` for a window, or ``equals`` with ``tolerance`` for a
    target value.
    """

    type: Literal["state_probability"]
    state: str
    minimum: float | None = Field(None, alias="min", ge=0.0, le=1.0)

    @field_validator("state")
    @classmethod
    def _check_state(cls, v: str) -> str:
        _validate_bitstring_keys([v], field="state")
        return v
    maximum: float | None = Field(None, alias="max", ge=0.0, le=1.0)
    equals: float | None = Field(None, ge=0.0, le=1.0)
    tolerance: float = Field(0.05, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_bounds(self) -> StateProbabilityAssertion:
        if self.equals is None and self.minimum is None and self.maximum is None:
            raise ValueError("state_probability requires one of: min, max, equals")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("min must not exceed max")
        return self

    def default_label(self) -> str:
        if self.equals is not None:
            return f"P({self.state}) ~= {self.equals}"
        bounds = []
        if self.minimum is not None:
            bounds.append(f">= {self.minimum}")
        if self.maximum is not None:
            bounds.append(f"<= {self.maximum}")
        return f"P({self.state}) {' and '.join(bounds)}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        prob = metrics.state_probability(counts, self.state)
        passed = True
        if self.equals is not None:
            passed = abs(prob - self.equals) <= self.tolerance
        if self.minimum is not None:
            passed = passed and prob >= self.minimum
        if self.maximum is not None:
            passed = passed and prob <= self.maximum
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"P({self.state}) = {prob:.4f}",
            metrics={"probability": prob},
        )


class AllowedStatesAssertion(_BaseAssertion):
    """Structural oracle: bound the probability mass outside an allowed support.

    A perfect GHZ state, for instance, should only produce all-zeros or all-ones;
    any other outcome is leakage and is bounded by ``max_leakage``.
    """

    type: Literal["allowed_states"]
    states: list[str] = Field(min_length=1)
    max_leakage: float = Field(0.0, ge=0.0, le=1.0)

    @field_validator("states")
    @classmethod
    def _check_states(cls, v: list[str]) -> list[str]:
        _validate_bitstring_keys(v, field="states")
        return v

    def default_label(self) -> str:
        return f"leakage <= {self.max_leakage}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        leakage = metrics.support_leakage(counts, self.states)
        passed = leakage <= self.max_leakage
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"support leakage {leakage:.4f} "
            f"({'<=' if passed else '>'} {self.max_leakage})",
            metrics={"leakage": leakage, "max_leakage": self.max_leakage},
        )


class KLDivergenceAssertion(_BaseAssertion):
    """Bound the Kullback-Leibler divergence ``D(observed || expected)`` in bits.

    Like ``chi_square``, this diverges (fails) when ``expected`` assigns zero
    probability to an observed outcome, so it is simulator-oriented unless ``expected``
    is noise-aware.
    """

    type: Literal["kl_divergence"]
    expected: dict[str, float]
    max_divergence: float = Field(0.05, ge=0.0)
    readout_error: ReadoutErrorSpec | Literal["auto"] | None = None
    noise_model: Literal["auto"] | None = None

    @field_validator("expected")
    @classmethod
    def _check_expected(cls, v: dict[str, float]) -> dict[str, float]:
        _validate_bitstring_keys(v.keys(), field="expected")
        return v

    @model_validator(mode="after")
    def _check_noise_aware(self) -> KLDivergenceAssertion:
        if self.noise_model is not None and self.readout_error is not None:
            raise ValueError(
                "set only one of noise_model or readout_error: noise_model: auto is the "
                "full device twin (gate + readout + decoherence); readout_error covers "
                "readout only"
            )
        return self

    def default_label(self) -> str:
        return f"KL <= {self.max_divergence}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        probs = metrics.counts_to_probabilities(counts)
        expected, note = _noise_aware_expected(
            self.expected, self.readout_error, self.noise_model, backend_metadata
        )
        divergence = metrics.kl_divergence(probs, expected)
        passed = divergence <= self.max_divergence
        if math.isfinite(divergence):
            message = (
                f"KL divergence {divergence:.4f} bits "
                f"({'<=' if passed else '>'} {self.max_divergence}){note}"
            )
        else:
            message = (
                "KL divergence diverged: expected assigns probability 0 to an observed "
                "outcome (use a noise-aware expected distribution on hardware)"
            )
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=message,
            metrics={"kl_divergence": divergence, "max_divergence": self.max_divergence},
        )


class ShannonEntropyAssertion(_BaseAssertion):
    """Bound the Shannon entropy (in bits) of the measured distribution."""

    type: Literal["shannon_entropy"]
    minimum: float | None = Field(None, alias="min", ge=0.0)
    maximum: float | None = Field(None, alias="max", ge=0.0)

    @model_validator(mode="after")
    def _check_bounds(self) -> ShannonEntropyAssertion:
        if self.minimum is None and self.maximum is None:
            raise ValueError("shannon_entropy requires one of: min, max")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("min must not exceed max")
        return self

    def default_label(self) -> str:
        bounds = []
        if self.minimum is not None:
            bounds.append(f">= {self.minimum}")
        if self.maximum is not None:
            bounds.append(f"<= {self.maximum}")
        return f"entropy {' and '.join(bounds)} bits"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        entropy = metrics.shannon_entropy(counts)
        passed = True
        if self.minimum is not None:
            passed = passed and entropy >= self.minimum
        if self.maximum is not None:
            passed = passed and entropy <= self.maximum
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"Shannon entropy {entropy:.4f} bits",
            metrics={"entropy": entropy},
        )


class ExpectationValueAssertion(_BaseAssertion):
    """Bound the Pauli-Z product expectation ``<Z_{q0} Z_{q1} ...>`` in ``[-1, 1]``.

    Use ``min``/``max`` for a window, or ``equals`` with ``tolerance`` for a target.
    A perfect Bell pair has ``<Z0 Z1> = +1``.
    """

    type: Literal["expectation_value"]
    qubits: list[int] = Field(min_length=1)
    minimum: float | None = Field(None, alias="min", ge=-1.0, le=1.0)
    maximum: float | None = Field(None, alias="max", ge=-1.0, le=1.0)
    equals: float | None = Field(None, ge=-1.0, le=1.0)
    tolerance: float = Field(0.05, ge=0.0, le=2.0)

    @field_validator("qubits")
    @classmethod
    def _check_qubits(cls, v: list[int]) -> list[int]:
        if any(q < 0 for q in v):
            raise ValueError("qubit indices must be non-negative")
        if len(set(v)) != len(v):
            raise ValueError("qubit indices must be unique")
        return v

    @model_validator(mode="after")
    def _check_bounds(self) -> ExpectationValueAssertion:
        if self.equals is None and self.minimum is None and self.maximum is None:
            raise ValueError("expectation_value requires one of: min, max, equals")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("min must not exceed max")
        return self

    def _operator(self) -> str:
        return "<" + "".join(f"Z{q}" for q in self.qubits) + ">"

    def default_label(self) -> str:
        if self.equals is not None:
            return f"{self._operator()} ~= {self.equals}"
        bounds = []
        if self.minimum is not None:
            bounds.append(f">= {self.minimum}")
        if self.maximum is not None:
            bounds.append(f"<= {self.maximum}")
        return f"{self._operator()} {' and '.join(bounds)}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        value = metrics.z_expectation(counts, self.qubits)
        passed = True
        if self.equals is not None:
            passed = abs(value - self.equals) <= self.tolerance
        if self.minimum is not None:
            passed = passed and value >= self.minimum
        if self.maximum is not None:
            passed = passed and value <= self.maximum
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"{self._operator()} = {value:.4f}",
            metrics={"expectation": value},
        )


class MostFrequentOutcomeAssertion(_BaseAssertion):
    """Assert the modal measured outcome is a given state, optionally above a probability.

    Useful for algorithms with a single intended answer (e.g. Grover's marked state).
    """

    type: Literal["most_frequent_outcome"]
    state: str
    min_probability: float | None = Field(None, ge=0.0, le=1.0)

    @field_validator("state")
    @classmethod
    def _check_state(cls, v: str) -> str:
        _validate_bitstring_keys([v], field="state")
        return v

    def default_label(self) -> str:
        base = f"mode == {self.state}"
        if self.min_probability is not None:
            return f"{base} (P >= {self.min_probability})"
        return base

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        state, prob = metrics.most_frequent_outcome(counts)
        passed = metrics.clean_key(state) == metrics.clean_key(self.state)
        if self.min_probability is not None:
            passed = passed and prob >= self.min_probability
        detail = "" if passed else f" (wanted {self.state})"
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"modal outcome {state} at P={prob:.4f}{detail}",
            metrics={"probability": prob},
        )


# Operations that are not logical gates; always permitted by gate_set.
_STRUCTURAL_OPS = frozenset({"measure", "barrier", "snapshot", "delay"})


class CircuitDepthAssertion(_BaseAssertion):
    """Bound the depth of the authored circuit.

    A static, output-independent check (it reads circuit telemetry, not measured
    counts), useful to catch a circuit that grew past a complexity budget.
    """

    type: Literal["circuit_depth"]
    needs_counts: ClassVar[bool] = False
    minimum: int | None = Field(None, alias="min", ge=0)
    maximum: int | None = Field(None, alias="max", ge=0)

    @model_validator(mode="after")
    def _check_bounds(self) -> CircuitDepthAssertion:
        if self.minimum is None and self.maximum is None:
            raise ValueError("circuit_depth requires one of: min, max")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("min must not exceed max")
        return self

    def default_label(self) -> str:
        bounds = []
        if self.minimum is not None:
            bounds.append(f">= {self.minimum}")
        if self.maximum is not None:
            bounds.append(f"<= {self.maximum}")
        return f"depth {' and '.join(bounds)}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        if not circuit_metrics or "depth" not in circuit_metrics:
            return AssertionResult(
                type=self.type,
                label=self.display_label(),
                passed=False,
                message="circuit metrics unavailable (depth could not be measured)",
                metrics={},
            )
        depth = int(circuit_metrics["depth"])
        passed = True
        if self.minimum is not None:
            passed = passed and depth >= self.minimum
        if self.maximum is not None:
            passed = passed and depth <= self.maximum
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"circuit depth {depth}",
            metrics={"depth": float(depth)},
        )


class GateSetAssertion(_BaseAssertion):
    """Require the authored circuit to use only an allowed set of gate names.

    Measurement, barrier, and similar structural operations are always permitted;
    list only the logical gates. A static, output-independent check, useful to catch
    an unexpected gate or to enforce a target device's basis before execution.
    """

    type: Literal["gate_set"]
    needs_counts: ClassVar[bool] = False
    allowed: list[str] = Field(min_length=1)

    def default_label(self) -> str:
        return f"gates in {self.allowed}"

    def evaluate(
        self,
        counts: dict[str, int],
        shots: int,
        circuit_metrics: dict[str, Any] | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> AssertionResult:
        if not circuit_metrics or "operations" not in circuit_metrics:
            return AssertionResult(
                type=self.type,
                label=self.display_label(),
                passed=False,
                message="circuit metrics unavailable (gate set could not be read)",
                metrics={},
            )
        used = set(circuit_metrics["operations"]) - _STRUCTURAL_OPS
        disallowed = sorted(used - set(self.allowed))
        passed = not disallowed
        message = (
            f"gates {sorted(used)} within the allowed set"
            if passed
            else f"disallowed gate(s): {disallowed} (allowed: {self.allowed})"
        )
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=message,
            metrics={"gate_count": float(len(used))},
        )


# Discriminated union: Pydantic dispatches on the ``type`` field when parsing.
Assertion = Annotated[
    DistributionTVDAssertion
    | HellingerFidelityAssertion
    | ChiSquareAssertion
    | StateProbabilityAssertion
    | AllowedStatesAssertion
    | KLDivergenceAssertion
    | ShannonEntropyAssertion
    | ExpectationValueAssertion
    | MostFrequentOutcomeAssertion
    | CircuitDepthAssertion
    | GateSetAssertion,
    Field(discriminator="type"),
]

ASSERTION_TYPES = (
    "distribution_tvd",
    "hellinger_fidelity",
    "chi_square",
    "state_probability",
    "allowed_states",
    "kl_divergence",
    "shannon_entropy",
    "expectation_value",
    "most_frequent_outcome",
    "circuit_depth",
    "gate_set",
)

__all__ = [
    "ASSERTION_TYPES",
    "AllowedStatesAssertion",
    "Assertion",
    "AssertionResult",
    "ChiSquareAssertion",
    "CircuitDepthAssertion",
    "DistributionTVDAssertion",
    "ExpectationValueAssertion",
    "GateSetAssertion",
    "HellingerFidelityAssertion",
    "KLDivergenceAssertion",
    "MostFrequentOutcomeAssertion",
    "ReadoutErrorSpec",
    "ShannonEntropyAssertion",
    "StateProbabilityAssertion",
]

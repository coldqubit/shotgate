# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 coldqubit
"""Declarative, statistically-grounded assertions over quantum measurement counts.

Each assertion is a Pydantic model (so it is self-validating when parsed from a
workflow YAML) that knows how to ``evaluate`` itself against backend counts and
return a structured :class:`AssertionResult`. New oracle types are added by
defining a model with a unique ``type`` literal and registering it in
``ASSERTION_TYPES``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shotgate.validation import metrics


@dataclass
class AssertionResult:
    """Outcome of evaluating a single assertion."""

    type: str
    label: str
    passed: bool
    message: str
    metrics: dict[str, float] = field(default_factory=dict)


class _BaseAssertion(BaseModel):
    """Common configuration shared by every assertion model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    label: str | None = None

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

    def default_label(self) -> str:
        return f"TVD <= {self.max_distance}"

    def evaluate(self, counts: dict[str, int], shots: int) -> AssertionResult:
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

    def default_label(self) -> str:
        return f"fidelity >= {self.min_fidelity}"

    def evaluate(self, counts: dict[str, int], shots: int) -> AssertionResult:
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

    def default_label(self) -> str:
        return f"chi-square p >= {self.significance}"

    def evaluate(self, counts: dict[str, int], shots: int) -> AssertionResult:
        statistic, dof, p_value = metrics.chi_square_test(counts, self.expected)
        passed = p_value >= self.significance
        return AssertionResult(
            type=self.type,
            label=self.display_label(),
            passed=passed,
            message=f"chi-square={statistic:.3f} dof={dof} p-value={p_value:.4f} "
            f"({'>=' if passed else '<'} alpha={self.significance})",
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

    def evaluate(self, counts: dict[str, int], shots: int) -> AssertionResult:
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

    def default_label(self) -> str:
        return f"leakage <= {self.max_leakage}"

    def evaluate(self, counts: dict[str, int], shots: int) -> AssertionResult:
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


# Discriminated union: Pydantic dispatches on the ``type`` field when parsing.
Assertion = Annotated[
    DistributionTVDAssertion
    | HellingerFidelityAssertion
    | ChiSquareAssertion
    | StateProbabilityAssertion
    | AllowedStatesAssertion,
    Field(discriminator="type"),
]

ASSERTION_TYPES = (
    "distribution_tvd",
    "hellinger_fidelity",
    "chi_square",
    "state_probability",
    "allowed_states",
)

__all__ = [
    "ASSERTION_TYPES",
    "AllowedStatesAssertion",
    "Assertion",
    "AssertionResult",
    "ChiSquareAssertion",
    "DistributionTVDAssertion",
    "HellingerFidelityAssertion",
    "StateProbabilityAssertion",
]

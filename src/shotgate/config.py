# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Declarative workflow schema: "quantum workflow as code".

A shotgate workflow is a Kubernetes-style YAML document validated by these Pydantic
models. Keeping the schema strict (``extra="forbid"``) means typos in a workflow
file fail fast with a clear error instead of being silently ignored.

Example
-------
.. code-block:: yaml

    apiVersion: shotgate.dev/v1alpha1
    kind: QuantumWorkflow
    metadata:
      name: bell-state
    defaults:
      backend:
        provider: local-aer
        shots: 4096
        seed: 1234
    jobs:
      - name: bell-pair
        circuit:
          format: qasm2
          path: bell.qasm
        assertions:
          - type: distribution_tvd
            expected: { "00": 0.5, "11": 0.5 }
            max_distance: 0.05
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from shotgate.validation.assertions import Assertion

API_VERSION = "shotgate.dev/v1alpha1"
KIND = "QuantumWorkflow"

# Only providers with an implemented backend are selectable. Braket is planned
# (roadmap) and intentionally excluded so a workflow can't request a backend that
# does not exist; selecting it fails fast at schema validation.
ProviderName = Literal["local-aer", "ibm"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metadata(_Strict):
    name: str = Field(min_length=1, max_length=63)
    description: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class CircuitSpec(_Strict):
    """How to obtain the circuit for a job.

    Exactly one of ``path`` (an OpenQASM file, resolved relative to the workflow
    file) or ``inline`` (an OpenQASM string) must be provided.
    """

    format: Literal["qasm2", "qasm3"] = "qasm2"
    path: str | None = None
    inline: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> CircuitSpec:
        if bool(self.path) == bool(self.inline):
            raise ValueError("circuit requires exactly one of 'path' or 'inline'")
        return self


class NoiseSpec(_Strict):
    """A simple, declarative noise model for the local Aer simulator.

    Lets a workflow exercise the noise-aware (``*-hardware``) thresholds in CI without a
    QPU: it applies a uniform depolarizing error per 1- and 2-qubit gate and a (possibly
    asymmetric) readout error. Non-simulator backends ignore it (real devices are noisy).
    """

    depolarizing_1q: float = Field(0.0, ge=0.0, le=1.0)  # per single-qubit gate
    depolarizing_2q: float = Field(0.0, ge=0.0, le=1.0)  # per two-qubit gate
    readout_p0: float = Field(0.0, ge=0.0, le=1.0)  # P(measure 1 | prepared 0)
    readout_p1: float = Field(0.0, ge=0.0, le=1.0)  # P(measure 0 | prepared 1)


class BackendSpec(_Strict):
    """Where and how to execute a circuit."""

    provider: ProviderName = "local-aer"
    shots: int = Field(4096, ge=1, le=1_000_000)
    seed: int | None = None
    name: str | None = None  # device/backend name for cloud providers
    options: dict[str, Any] = Field(default_factory=dict)
    noise: NoiseSpec | None = None  # local-aer only: simulate device noise

    def merged_with_defaults(self, defaults: BackendSpec | None) -> BackendSpec:
        """Return a backend spec where unset fields fall back to ``defaults``."""
        if defaults is None:
            return self
        data = defaults.model_dump()
        # Only override defaults with fields the job explicitly set.
        explicit = self.model_dump(exclude_unset=True)
        data.update(explicit)
        return BackendSpec(**data)


class Defaults(_Strict):
    backend: BackendSpec | None = None


class JobSpec(_Strict):
    name: str = Field(min_length=1, max_length=63)
    circuit: CircuitSpec
    backend: BackendSpec = Field(default_factory=BackendSpec)
    assertions: list[Assertion] = Field(default_factory=list)

    # Track whether the user explicitly set a backend so defaults can apply.
    model_config = ConfigDict(extra="forbid")


class Workflow(_Strict):
    api_version: Literal["shotgate.dev/v1alpha1"] = Field(alias="apiVersion")
    kind: Literal["QuantumWorkflow"]
    metadata: Metadata
    defaults: Defaults | None = None
    jobs: list[JobSpec] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _unique_job_names(self) -> Workflow:
        names = [job.name for job in self.jobs]
        if len(names) != len(set(names)):
            raise ValueError("job names must be unique within a workflow")
        return self

    def effective_backend(self, job: JobSpec) -> BackendSpec:
        """Resolve a job's backend against workflow-level defaults."""
        default_backend = self.defaults.backend if self.defaults else None
        return job.backend.merged_with_defaults(default_backend)


class LoadedWorkflow:
    """A parsed workflow together with the directory it was loaded from.

    The base directory is needed to resolve circuit ``path`` references relative
    to the workflow file rather than the process working directory.
    """

    def __init__(self, workflow: Workflow, base_dir: Path) -> None:
        self.workflow = workflow
        self.base_dir = base_dir


def parse_workflow(document: dict[str, Any]) -> Workflow:
    """Validate a raw mapping into a :class:`Workflow`."""
    return Workflow.model_validate(document)


def load_workflow(path: str | Path) -> LoadedWorkflow:
    """Load and validate a workflow YAML file."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"workflow file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"workflow file {path} must contain a YAML mapping")
    workflow = parse_workflow(document)
    return LoadedWorkflow(workflow=workflow, base_dir=path.parent)


__all__ = [
    "API_VERSION",
    "KIND",
    "BackendSpec",
    "CircuitSpec",
    "Defaults",
    "JobSpec",
    "LoadedWorkflow",
    "Metadata",
    "NoiseSpec",
    "Workflow",
    "load_workflow",
    "parse_workflow",
]

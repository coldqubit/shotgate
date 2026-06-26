# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Workflow orchestration: load → execute → validate → report.

The :class:`Runner` ties the pieces together. It is deliberately backend- and
SDK-agnostic: it asks the registry for a backend, executes each job's circuit,
then evaluates the declared assertions against the returned counts. Any failure
(missing dependency, bad circuit, failed assertion) is captured per-job so a
single broken job never aborts the whole report.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from shotgate.backends.registry import get_backend
from shotgate.circuits.loader import load_circuit
from shotgate.config import BackendSpec, LoadedWorkflow
from shotgate.telemetry import circuit_metrics
from shotgate.validation.assertions import AssertionResult


@dataclass
class JobReport:
    name: str
    provider: str
    backend_name: str
    shots: int
    passed: bool
    assertions: list[AssertionResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    duration_s: float = 0.0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["assertions"] = [asdict(a) for a in self.assertions]
        return data


@dataclass
class WorkflowReport:
    name: str
    passed: bool
    started_at: str
    duration_s: float
    jobs: list[JobReport] = field(default_factory=list)

    @property
    def total_assertions(self) -> int:
        return sum(len(job.assertions) for job in self.jobs)

    @property
    def failed_assertions(self) -> int:
        return sum(
            1 for job in self.jobs for a in job.assertions if not a.passed
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "started_at": self.started_at,
            "duration_s": self.duration_s,
            "summary": {
                "jobs": len(self.jobs),
                "jobs_failed": sum(1 for j in self.jobs if not j.passed),
                "assertions": self.total_assertions,
                "assertions_failed": self.failed_assertions,
            },
            "jobs": [job.as_dict() for job in self.jobs],
        }


class Runner:
    """Execute a loaded workflow and produce a :class:`WorkflowReport`."""

    def __init__(
        self,
        loaded: LoadedWorkflow,
        backend_override: str | None = None,
        shots_override: int | None = None,
        allow_empty: bool = False,
    ) -> None:
        self.loaded = loaded
        self.backend_override = backend_override
        self.shots_override = shots_override
        self.allow_empty = allow_empty

    def run(self) -> WorkflowReport:
        workflow = self.loaded.workflow
        started = datetime.now(timezone.utc)
        wall_start = time.perf_counter()

        jobs: list[JobReport] = []
        for job in workflow.jobs:
            backend_spec = self._resolve_backend(workflow.effective_backend(job))
            jobs.append(self._run_job(job.name, job, backend_spec))

        return WorkflowReport(
            name=workflow.metadata.name,
            passed=all(job.passed for job in jobs),
            started_at=started.isoformat(),
            duration_s=round(time.perf_counter() - wall_start, 6),
            jobs=jobs,
        )

    def _resolve_backend(self, spec: BackendSpec) -> BackendSpec:
        data = spec.model_dump()
        if self.backend_override:
            data["provider"] = self.backend_override
        if self.shots_override:
            data["shots"] = self.shots_override
        return BackendSpec(**data)

    def _run_job(self, name: str, job: Any, backend_spec: BackendSpec) -> JobReport:
        job_start = time.perf_counter()
        report = JobReport(
            name=name,
            provider=backend_spec.provider,
            backend_name=backend_spec.name or backend_spec.provider,
            shots=backend_spec.shots,
            passed=False,
        )
        try:
            circuit = load_circuit(job.circuit, self.loaded.base_dir)
            cmetrics = circuit_metrics(circuit).as_dict()
            report.metrics.update(cmetrics)

            # A job whose assertions are all static (structural) needs no execution:
            # skip the backend entirely, so circuit-property gates run with no shots,
            # no QPU time, and no backend dependency. An empty gate still executes (it
            # may exist only to capture counts/telemetry under --allow-empty).
            requires_execution = not job.assertions or any(
                a.needs_counts for a in job.assertions
            )
            counts: dict[str, int] = {}
            run_shots = backend_spec.shots
            bmeta: dict[str, Any] | None = None
            if requires_execution:
                backend = get_backend(backend_spec)
                result = backend.run(
                    circuit, shots=backend_spec.shots, seed=backend_spec.seed
                )
                counts = result.counts
                run_shots = result.shots
                bmeta = result.metadata
                report.counts = result.counts
                report.backend_name = result.backend_name
                report.metrics["backend_metadata"] = result.metadata
            else:
                report.metrics["executed"] = False

            outcomes = [
                assertion.evaluate(
                    counts, run_shots, circuit_metrics=cmetrics, backend_metadata=bmeta
                )
                for assertion in job.assertions
            ]
            report.assertions = outcomes
            if outcomes:
                report.passed = all(o.passed for o in outcomes)
            elif self.allow_empty:
                report.passed = True
            else:
                report.passed = False
                report.error = (
                    "no assertions declared: a quality gate must check something. "
                    "Add assertions, or allow an intentionally empty gate with "
                    "--allow-empty (CLI) or allow_empty=True (Runner)."
                )
        except Exception as exc:
            report.error = f"{type(exc).__name__}: {exc}"
            report.passed = False
        finally:
            report.duration_s = round(time.perf_counter() - job_start, 6)
        return report


__all__ = ["JobReport", "Runner", "WorkflowReport"]

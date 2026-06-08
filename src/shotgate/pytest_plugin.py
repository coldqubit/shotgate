# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Pytest plugin: collect shotgate workflows and gate each assertion as a test.

This exposes the same statistical oracles the ``shotgate`` CLI uses (the
``validation/`` metrics, run through :class:`shotgate.runner.Runner`) as native
pytest items, so a workflow can be gated from an ordinary ``pytest`` run without a
container. No metric logic is duplicated here: the plugin parses the workflow,
runs it through the shared runner, and maps each assertion outcome onto one pytest
item, reusing the exact detail string the CLI prints.

Collection
----------
- Opt in with ``--shotgate=PATH`` (a workflow file or a directory; repeatable) or
  the ``shotgate_paths`` ini key.
- Files named exactly ``workflow.yaml`` are auto-collected wherever pytest already
  walks. The exact-name match is deliberate: a ``*.workflow.yaml`` glob would miss
  the ``workflow.yaml`` files this project ships under ``examples/``.

SDK safety
----------
Importing this plugin and collecting workflows touches only the SDK-free core
(``config`` plus ``validation/``); no quantum SDK is imported. When a job's
backend dependencies are absent (mirroring the lazy import in ``backends/``), its
assertion items skip with a reason naming the extra to install, rather than
erroring.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from shotgate.config import LoadedWorkflow
    from shotgate.runner import WorkflowReport

WORKFLOW_FILENAME = "workflow.yaml"
_EXPLICIT_FILES_ATTR = "_shotgate_explicit_files"
_BACKEND_CACHE_ATTR = "_shotgate_backend_cache"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("shotgate", "shotgate quantum workflow gating")
    group.addoption(
        "--shotgate",
        action="append",
        dest="shotgate_paths",
        default=[],
        metavar="PATH",
        help="Collect a shotgate workflow file or directory as pytest tests "
        "(repeatable). Files named workflow.yaml are also auto-collected.",
    )
    parser.addini(
        "shotgate_paths",
        type="args",
        default=[],
        help="shotgate workflow files or directories to always collect, resolved "
        "relative to the rootdir.",
    )


def _resolve(raw: str, base: Path) -> Path:
    candidate = Path(raw)
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def pytest_configure(config: pytest.Config) -> None:
    """Resolve configured workflow paths and add them as collection roots.

    ``--shotgate`` paths resolve against the invocation directory; ini paths
    resolve against the rootdir. Files (any name) are recorded so the collector
    accepts them even when not named ``workflow.yaml``; directories are added as
    roots so their ``workflow.yaml`` children are auto-collected.
    """
    explicit_files: set[Path] = set()
    invocation_dir = Path(config.invocation_params.dir)

    configured: list[tuple[str, Path]] = [
        (raw, invocation_dir) for raw in config.getoption("shotgate_paths") or []
    ]
    configured += [(raw, config.rootpath) for raw in config.getini("shotgate_paths") or []]

    for raw, base in configured:
        path = _resolve(raw, base)
        if path.is_file():
            explicit_files.add(path)
        arg = str(path)
        if arg not in config.args:
            config.args.append(arg)

    setattr(config, _EXPLICIT_FILES_ATTR, explicit_files)


def _should_collect(config: pytest.Config, file_path: Path) -> bool:
    if file_path.name == WORKFLOW_FILENAME:
        return True
    explicit: set[Path] = getattr(config, _EXPLICIT_FILES_ATTR, set())
    return file_path.resolve() in explicit


def pytest_collect_file(parent: pytest.Collector, file_path: Path):
    if _should_collect(parent.config, file_path):
        return ShotgateFile.from_parent(parent, path=file_path)
    return None


def _backend_available(config: pytest.Config, provider: str) -> bool:
    cache: dict[str, bool] | None = getattr(config, _BACKEND_CACHE_ATTR, None)
    if cache is None:
        from shotgate.backends.registry import available_backends

        cache = available_backends()
        setattr(config, _BACKEND_CACHE_ATTR, cache)
    return cache.get(provider, False)


class ShotgateFile(pytest.File):
    """A parsed workflow file; yields one item per declared assertion."""

    def collect(self):
        from shotgate.config import load_workflow

        loaded: LoadedWorkflow = load_workflow(self.path)
        self._loaded = loaded
        self._report: WorkflowReport | None = None

        workflow = loaded.workflow
        for job in workflow.jobs:
            provider = workflow.effective_backend(job).provider
            for index, assertion in enumerate(job.assertions):
                label = assertion.display_label()
                yield ShotgateItem.from_parent(
                    self,
                    name=f"{job.name}[{index}] {label}",
                    job_name=job.name,
                    assertion_index=index,
                    provider=provider,
                )

    def workflow_report(self) -> WorkflowReport:
        """Execute the workflow once and cache the report for sibling items."""
        if self._report is None:
            from shotgate.runner import Runner

            self._report = Runner(self._loaded).run()
        return self._report


class ShotgateItem(pytest.Item):
    """One assertion of one job, gated as a single pass/fail/skip."""

    def __init__(
        self,
        *,
        name: str,
        parent: ShotgateFile,
        job_name: str,
        assertion_index: int,
        provider: str,
    ) -> None:
        super().__init__(name=name, parent=parent)
        self.job_name = job_name
        self.assertion_index = assertion_index
        self.provider = provider

    def runtest(self) -> None:
        if not _backend_available(self.config, self.provider):
            from shotgate.backends.registry import extra_for_provider

            extra = extra_for_provider(self.provider)
            pytest.skip(
                f"backend {self.provider!r} unavailable: its dependencies are not "
                f"installed; install the matching extra, "
                f"e.g. pip install 'shotgate[{extra}]'"
            )

        parent = self.parent
        assert isinstance(parent, ShotgateFile)
        report = parent.workflow_report()
        job = next(j for j in report.jobs if j.name == self.job_name)
        if job.error is not None:
            pytest.fail(
                f"job {self.job_name!r} did not execute: {job.error}", pytrace=False
            )

        result = job.assertions[self.assertion_index]
        if not result.passed:
            # Same detail string the CLI prints in its Detail column.
            pytest.fail(result.message, pytrace=False)

    def reportinfo(self) -> tuple[Any, int, str]:
        return self.path, 0, f"{self.path.name}::{self.name}"

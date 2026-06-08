# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Command-line interface for shotgate.

Commands
--------
- ``shotgate run WORKFLOW``      execute a workflow and gate CI on the result.
- ``shotgate validate WORKFLOW`` schema-validate a workflow without executing it.
- ``shotgate backends``          list backends and whether their deps are installed.

Exit codes: ``0`` if all assertions pass, ``1`` if any fail, ``2`` for usage or
load errors. This makes ``shotgate run`` a drop-in CI quality gate.
"""

from __future__ import annotations

from pathlib import Path

import click

from shotgate import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="shotgate")
def main() -> None:
    """Container-native CI/CD quality gates for quantum circuits."""


@main.command()
@click.argument("workflow", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--backend", "backend", default=None, help="Override the backend provider.")
@click.option("--shots", type=int, default=None, help="Override shot count for all jobs.")
@click.option(
    "--junit",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write a JUnit XML report to this path.",
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write a JSON report to this path.",
)
@click.option(
    "--markdown",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write a Markdown summary to this path (e.g. $GITHUB_STEP_SUMMARY).",
)
@click.option("--quiet", is_flag=True, help="Suppress the console table.")
def run(
    workflow: Path,
    backend: str | None,
    shots: int | None,
    junit: Path | None,
    json_path: Path | None,
    markdown: Path | None,
    quiet: bool,
) -> None:
    """Execute WORKFLOW: run each job, validate output, and report."""
    import typing

    from shotgate.config import ProviderName, load_workflow
    from shotgate.report import render_console, to_json, to_junit_xml, to_markdown
    from shotgate.runner import Runner

    valid_backends = typing.get_args(ProviderName)
    if backend is not None and backend not in valid_backends:
        raise click.ClickException(
            f"unknown backend {backend!r}; valid backends: {', '.join(valid_backends)}"
        )

    try:
        loaded = load_workflow(workflow)
    except Exception as exc:
        raise click.ClickException(f"failed to load workflow: {exc}") from exc

    report = Runner(loaded, backend_override=backend, shots_override=shots).run()

    if not quiet:
        render_console(report)

    if junit:
        junit.write_text(to_junit_xml(report), encoding="utf-8")
    if json_path:
        json_path.write_text(to_json(report), encoding="utf-8")
    if markdown:
        markdown.write_text(to_markdown(report), encoding="utf-8")

    raise SystemExit(0 if report.passed else 1)


@main.command()
@click.argument("workflow", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate(workflow: Path) -> None:
    """Schema-validate WORKFLOW without executing any circuit."""
    from shotgate.config import load_workflow

    try:
        loaded = load_workflow(workflow)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    wf = loaded.workflow
    click.secho(f"✓ valid workflow: {wf.metadata.name}", fg="green")
    for job in wf.jobs:
        spec = wf.effective_backend(job)
        click.echo(
            f"  - job {job.name}: {len(job.assertions)} assertion(s), "
            f"backend={spec.provider}, shots={spec.shots}"
        )


@main.command()
def backends() -> None:
    """List available backends and whether their dependencies are installed."""
    from shotgate.backends.registry import available_backends

    for provider, ready in available_backends().items():
        mark = click.style("ready", fg="green") if ready else click.style(
            "missing deps", fg="yellow"
        )
        click.echo(f"  {provider:<12} {mark}")


if __name__ == "__main__":  # pragma: no cover
    main()

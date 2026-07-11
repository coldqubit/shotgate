# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Command-line interface for shotgate.

Commands
--------
- ``shotgate run WORKFLOW``      execute a workflow and gate CI on the result.
- ``shotgate validate WORKFLOW`` schema-validate a workflow without executing it.
- ``shotgate backends``          list backends and whether their deps are installed.
- ``shotgate shots``             plan a shot count for a target CI margin or detection power.

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
@click.option(
    "--allow-empty",
    is_flag=True,
    help="Allow a job with no assertions to pass (default: an empty gate fails).",
)
def run(
    workflow: Path,
    backend: str | None,
    shots: int | None,
    junit: Path | None,
    json_path: Path | None,
    markdown: Path | None,
    quiet: bool,
    allow_empty: bool,
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

    report = Runner(
        loaded,
        backend_override=backend,
        shots_override=shots,
        allow_empty=allow_empty,
    ).run()

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


@main.command()
@click.option(
    "--p",
    "p",
    type=float,
    default=0.5,
    show_default=True,
    help="Expected proportion (use 0.5, the worst case, if unknown).",
)
@click.option("--margin", type=float, help="Target Wilson-interval half-width.")
@click.option(
    "--effect-size",
    "effect_size",
    type=float,
    help="Smallest proportion shift the gate must reliably detect.",
)
@click.option(
    "--alpha",
    type=float,
    default=0.05,
    show_default=True,
    help="Significance level (used with --effect-size).",
)
@click.option(
    "--power",
    type=float,
    default=0.9,
    show_default=True,
    help="Statistical power (used with --effect-size).",
)
@click.option(
    "--confidence",
    type=float,
    default=0.95,
    show_default=True,
    help="Confidence level (used with --margin).",
)
def shots(
    p: float,
    margin: float | None,
    effect_size: float | None,
    alpha: float,
    power: float,
    confidence: float,
) -> None:
    """Plan a shot count for a target precision or detection power.

    Give exactly one of --margin (how tight a confidence interval you want on a measured
    probability) or --effect-size (the smallest true shift you need the gate to catch).
    """
    from shotgate.validation import metrics

    if (margin is None) == (effect_size is None):
        raise click.ClickException("pass exactly one of --margin or --effect-size")
    try:
        if margin is not None:
            n = metrics.shots_for_margin(p, margin, confidence=confidence)
            click.echo(
                f"{n} shots -> a {confidence:.0%} Wilson interval of +/-{margin} "
                f"around p={p}"
            )
        else:
            assert effect_size is not None
            n = metrics.shots_for_power(effect_size, alpha=alpha, power=power)
            click.echo(
                f"{n} shots -> {power:.0%} power to detect a shift of {effect_size} "
                f"at alpha={alpha}"
            )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover
    main()

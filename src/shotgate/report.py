# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 coldqubit
"""Reporters: turn a :class:`~shotgate.runner.WorkflowReport` into CI-friendly output.

- JUnit XML: consumed natively by GitHub Actions, GitLab, Jenkins, etc.
- JSON: machine-readable artifact for dashboards and trend analysis.
- Markdown: rendered into a GitHub Actions step summary or PR comment.
- Rich console: human-friendly local output.
"""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from shotgate.runner import WorkflowReport


def to_json(report: WorkflowReport, *, indent: int = 2) -> str:
    return json.dumps(report.as_dict(), indent=indent, sort_keys=False)


def to_junit_xml(report: WorkflowReport) -> str:
    """Map the workflow to a JUnit document.

    Each job becomes a ``<testsuite>`` and each assertion a ``<testcase>``. A job
    that errored before assertions ran is recorded as a single errored testcase.
    """
    total_tests = 0
    total_failures = 0
    total_errors = 0
    suites: list[ET.Element] = []

    for job in report.jobs:
        suite = ET.Element(
            "testsuite",
            {
                "name": job.name,
                "time": f"{job.duration_s:.6f}",
                "hostname": job.backend_name,
            },
        )
        tests = failures = errors = 0

        if job.error is not None:
            tests += 1
            errors += 1
            case = ET.SubElement(
                suite, "testcase", {"name": "execution", "classname": job.name}
            )
            error_el = ET.SubElement(case, "error", {"message": job.error})
            error_el.text = job.error

        for assertion in job.assertions:
            tests += 1
            case = ET.SubElement(
                suite,
                "testcase",
                {
                    "name": f"{assertion.type}: {assertion.label}",
                    "classname": job.name,
                },
            )
            if not assertion.passed:
                failures += 1
                failure = ET.SubElement(
                    case, "failure", {"message": assertion.message}
                )
                failure.text = assertion.message

        suite.set("tests", str(tests))
        suite.set("failures", str(failures))
        suite.set("errors", str(errors))
        suites.append(suite)
        total_tests += tests
        total_failures += failures
        total_errors += errors

    root = ET.Element(
        "testsuites",
        {
            "name": report.name,
            "tests": str(total_tests),
            "failures": str(total_failures),
            "errors": str(total_errors),
            "time": f"{report.duration_s:.6f}",
        },
    )
    root.extend(suites)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def to_markdown(report: WorkflowReport) -> str:
    """Markdown summary suitable for a GitHub Actions step summary or PR comment."""
    status = "✅ passed" if report.passed else "❌ failed"
    lines = [
        f"## shotgate: `{report.name}` — {status}",
        "",
        f"- Jobs: **{len(report.jobs)}**, "
        f"failed: **{sum(1 for j in report.jobs if not j.passed)}**",
        f"- Assertions: **{report.total_assertions}**, "
        f"failed: **{report.failed_assertions}**",
        f"- Duration: **{report.duration_s:.3f}s**",
        "",
        "| Job | Backend | Shots | Assertion | Result | Detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for job in report.jobs:
        if job.error is not None:
            lines.append(
                f"| `{job.name}` | {job.backend_name} | {job.shots} "
                f"| _execution_ | 🛑 error | {job.error} |"
            )
            continue
        if not job.assertions:
            lines.append(
                f"| `{job.name}` | {job.backend_name} | {job.shots} "
                f"| _(none)_ | — | no assertions declared |"
            )
        for assertion in job.assertions:
            mark = "✅" if assertion.passed else "❌"
            lines.append(
                f"| `{job.name}` | {job.backend_name} | {job.shots} "
                f"| {escape(assertion.label)} | {mark} | {escape(assertion.message)} |"
            )
    lines.append("")
    return "\n".join(lines)


def render_console(report: WorkflowReport, console=None) -> None:
    """Pretty-print the report to a Rich console (falls back to plain print)."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:  # pragma: no cover - rich is a core dependency
        _render_plain(report)
        return

    console = console or Console()
    title_color = "green" if report.passed else "red"
    console.rule(f"[bold {title_color}]shotgate :: {report.name}")

    for job in report.jobs:
        table = Table(
            title=f"job: {job.name}  ·  {job.backend_name}  ·  {job.shots} shots",
            title_justify="left",
            expand=False,
        )
        table.add_column("Assertion", style="cyan", no_wrap=False)
        table.add_column("Result", justify="center")
        table.add_column("Detail", style="dim")

        if job.error is not None:
            table.add_row("execution", "[bold red]ERROR", job.error)
        for assertion in job.assertions:
            mark = "[green]PASS" if assertion.passed else "[bold red]FAIL"
            table.add_row(assertion.label, mark, assertion.message)
        console.print(table)

    summary_style = "bold green" if report.passed else "bold red"
    verdict = "PASSED" if report.passed else "FAILED"
    console.print(
        f"[{summary_style}]{verdict}[/] · "
        f"{report.total_assertions - report.failed_assertions}/"
        f"{report.total_assertions} assertions · "
        f"{report.duration_s:.3f}s"
    )


def _render_plain(report: WorkflowReport) -> None:
    print(f"shotgate :: {report.name} :: {'PASSED' if report.passed else 'FAILED'}")
    for job in report.jobs:
        print(f"  job {job.name} [{job.backend_name}, {job.shots} shots]")
        if job.error:
            print(f"    ERROR: {job.error}")
        for assertion in job.assertions:
            mark = "PASS" if assertion.passed else "FAIL"
            print(f"    [{mark}] {assertion.label} — {assertion.message}")


__all__ = ["render_console", "to_json", "to_junit_xml", "to_markdown"]

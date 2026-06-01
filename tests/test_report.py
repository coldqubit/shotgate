"""Tests for the reporters, using a hand-built report (no execution needed)."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from shotgate.report import to_json, to_junit_xml, to_markdown
from shotgate.runner import JobReport, WorkflowReport
from shotgate.validation.assertions import AssertionResult


def _sample_report() -> WorkflowReport:
    passing = AssertionResult(
        type="distribution_tvd", label="TVD <= 0.05", passed=True, message="tvd 0.01"
    )
    failing = AssertionResult(
        type="chi_square", label="chi-square p >= 0.05", passed=False, message="p=0.001"
    )
    good = JobReport(
        name="bell",
        provider="local-aer",
        backend_name="aer_simulator",
        shots=8192,
        passed=True,
        assertions=[passing],
        duration_s=0.12,
    )
    bad = JobReport(
        name="ghz",
        provider="local-aer",
        backend_name="aer_simulator",
        shots=8192,
        passed=False,
        assertions=[failing],
        duration_s=0.20,
    )
    return WorkflowReport(
        name="demo",
        passed=False,
        started_at="2026-06-01T00:00:00+00:00",
        duration_s=0.32,
        jobs=[good, bad],
    )


def test_junit_xml_is_wellformed_and_counts_failures():
    xml = to_junit_xml(_sample_report())
    root = ET.fromstring(xml)
    assert root.tag == "testsuites"
    assert root.attrib["tests"] == "2"
    assert root.attrib["failures"] == "1"
    suites = root.findall("testsuite")
    assert {s.attrib["name"] for s in suites} == {"bell", "ghz"}
    # The failing assertion is recorded as a <failure>.
    failures = root.findall(".//failure")
    assert len(failures) == 1


def test_json_roundtrips_and_summarises():
    payload = json.loads(to_json(_sample_report()))
    assert payload["passed"] is False
    assert payload["summary"]["jobs"] == 2
    assert payload["summary"]["assertions_failed"] == 1


def test_markdown_contains_status_and_rows():
    md = to_markdown(_sample_report())
    assert "shotgate: `demo`" in md
    assert "❌ failed" in md
    assert "`bell`" in md and "`ghz`" in md

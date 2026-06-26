"""End-to-end runner tests.

These require a quantum SDK (qiskit + qiskit-aer) and are skipped automatically
when it is not installed. In CI they run inside the shotgate container, which has
the ``aer`` extra. Run locally with ``pip install -e .[aer,dev]``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shotgate.backends.registry import available_backends
from shotgate.config import load_workflow
from shotgate.runner import Runner

pytestmark = pytest.mark.integration

AER_AVAILABLE = available_backends().get("local-aer", False)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
@pytest.mark.parametrize("example", ["bell-state", "ghz-state", "grover-2q"])
def test_example_workflows_pass(example: str):
    loaded = load_workflow(EXAMPLES / example / "workflow.yaml")
    report = Runner(loaded).run()
    assert report.passed, [
        (j.name, a.label, a.message)
        for j in report.jobs
        for a in j.assertions
        if not a.passed
    ] or [(j.name, j.error) for j in report.jobs if j.error]


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_inline_circuit_runs():
    from shotgate.config import parse_workflow

    wf = parse_workflow(
        {
            "apiVersion": "shotgate.dev/v1alpha1",
            "kind": "QuantumWorkflow",
            "metadata": {"name": "inline"},
            "jobs": [
                {
                    "name": "plus",
                    "circuit": {
                        "format": "qasm2",
                        "inline": (
                            'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
                            "qreg q[1];\ncreg c[1];\nh q[0];\nmeasure q -> c;\n"
                        ),
                    },
                    "backend": {"provider": "local-aer", "shots": 8192, "seed": 1},
                    "assertions": [
                        {
                            "type": "state_probability",
                            "state": "0",
                            "min": 0.45,
                            "max": 0.55,
                        }
                    ],
                }
            ],
        }
    )
    from shotgate.config import LoadedWorkflow

    report = Runner(LoadedWorkflow(wf, EXAMPLES)).run()
    assert report.passed


def _empty_gate_workflow():
    from shotgate.config import parse_workflow

    return parse_workflow(
        {
            "apiVersion": "shotgate.dev/v1alpha1",
            "kind": "QuantumWorkflow",
            "metadata": {"name": "empty-gate"},
            "jobs": [
                {
                    "name": "no-checks",
                    "circuit": {
                        "format": "qasm2",
                        "inline": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n',
                    },
                    "backend": {"provider": "local-aer", "shots": 1024, "seed": 1},
                    "assertions": [],
                }
            ],
        }
    )


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_empty_gate_fails_by_default():
    from shotgate.config import LoadedWorkflow

    report = Runner(LoadedWorkflow(_empty_gate_workflow(), EXAMPLES)).run()
    assert not report.passed
    assert "no assertions" in (report.jobs[0].error or "").lower()


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_empty_gate_allowed_with_flag():
    from shotgate.config import LoadedWorkflow

    report = Runner(
        LoadedWorkflow(_empty_gate_workflow(), EXAMPLES), allow_empty=True
    ).run()
    assert report.passed
    assert report.jobs[0].error is None

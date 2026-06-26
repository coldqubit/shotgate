"""AWS Braket backend tests: local simulation only (no AWS account required).

Skipped when qiskit-braket-provider is not installed. The cloud path (named devices)
needs AWS credentials and Braket access and is not exercised here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from shotgate.config import LoadedWorkflow, parse_workflow
from shotgate.runner import Runner

pytestmark = pytest.mark.integration

BRAKET_AVAILABLE = importlib.util.find_spec("qiskit_braket_provider") is not None
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

BELL_QASM2 = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
    "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"
)


@pytest.mark.skipif(
    not BRAKET_AVAILABLE, reason="qiskit-braket-provider not installed"
)
def test_braket_local_simulation_bell():
    wf = parse_workflow(
        {
            "apiVersion": "shotgate.dev/v1alpha1",
            "kind": "QuantumWorkflow",
            "metadata": {"name": "braket-local"},
            "jobs": [
                {
                    "name": "bell",
                    "circuit": {"format": "qasm2", "inline": BELL_QASM2},
                    "backend": {"provider": "braket", "shots": 4096},
                    "assertions": [
                        {"type": "allowed_states", "states": ["00", "11"], "max_leakage": 0.0},
                        {"type": "state_probability", "state": "00", "min": 0.4, "max": 0.6},
                    ],
                }
            ],
        }
    )
    report = Runner(LoadedWorkflow(wf, EXAMPLES)).run()
    assert report.passed, [
        (j.name, j.error) for j in report.jobs if j.error
    ] or [
        (a.label, a.message)
        for j in report.jobs
        for a in j.assertions
        if not a.passed
    ]
    assert report.jobs[0].metrics["backend_metadata"]["provider"] == "braket"

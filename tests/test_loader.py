"""Circuit-loader tests: OpenQASM 2 and 3 parsing.

These require qiskit (and, for the qasm3 path, qiskit-qasm3-import) and are
skipped when the SDK is not installed. In CI they run inside the shotgate
container, which has the ``aer`` extra. Run locally with
``pip install -e '.[aer,dev]'``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from shotgate.backends.registry import available_backends
from shotgate.circuits.loader import load_circuit
from shotgate.config import CircuitSpec, load_workflow
from shotgate.runner import Runner

pytestmark = pytest.mark.integration

AER_AVAILABLE = available_backends().get("local-aer", False)
QASM3_AVAILABLE = importlib.util.find_spec("qiskit_qasm3_import") is not None
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

QASM3_BELL = (
    "OPENQASM 3.0;\n"
    'include "stdgates.inc";\n'
    "qubit[2] q;\nbit[2] c;\nh q[0];\ncx q[0], q[1];\nc = measure q;\n"
)


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit not installed")
def test_qasm2_inline_appends_measurement():
    # A circuit with no classical register gets a full measurement appended so
    # the backend produces counts.
    spec = CircuitSpec(
        format="qasm2",
        inline='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n',
    )
    circuit = load_circuit(spec, EXAMPLES)
    assert circuit.num_qubits == 1
    assert circuit.num_clbits >= 1


@pytest.mark.skipif(
    not (AER_AVAILABLE and QASM3_AVAILABLE),
    reason="qiskit / qiskit-qasm3-import not installed",
)
def test_qasm3_inline_loads():
    spec = CircuitSpec(format="qasm3", inline=QASM3_BELL)
    circuit = load_circuit(spec, EXAMPLES)
    assert circuit.num_qubits == 2
    assert circuit.num_clbits == 2


@pytest.mark.skipif(
    not (AER_AVAILABLE and QASM3_AVAILABLE),
    reason="qiskit / qiskit-qasm3-import not installed",
)
def test_qasm3_example_workflow_passes():
    loaded = load_workflow(EXAMPLES / "bell-state-qasm3" / "workflow.yaml")
    report = Runner(loaded).run()
    assert report.passed, [(j.name, j.error) for j in report.jobs if j.error] or [
        (a.label, a.message)
        for j in report.jobs
        for a in j.assertions
        if not a.passed
    ]

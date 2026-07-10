"""End-to-end runner tests.

These require a quantum SDK (qiskit + qiskit-aer) and are skipped automatically
when it is not installed. In CI they run inside the shotgate container, which has
the ``aer`` extra. Run locally with ``pip install -e .[aer,dev]``.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from shotgate.backends.registry import available_backends
from shotgate.config import load_workflow
from shotgate.runner import Runner

pytestmark = pytest.mark.integration

AER_AVAILABLE = available_backends().get("local-aer", False)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

BELL_QASM2 = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
    "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"
)


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
@pytest.mark.parametrize(
    "example",
    [
        "bell-state",
        "ghz-state",
        "grover-2q",
        "bell-state-observables",
        "bell-state-noisy-sim",
        "bell-state-structural",
        "bell-state-differential",
    ],
)
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


def _bell_workflow(noise: dict | None = None):
    from shotgate.config import parse_workflow

    backend: dict = {"provider": "local-aer", "shots": 8192, "seed": 7}
    if noise is not None:
        backend["noise"] = noise
    return parse_workflow(
        {
            "apiVersion": "shotgate.dev/v1alpha1",
            "kind": "QuantumWorkflow",
            "metadata": {"name": "bell-noise"},
            "jobs": [
                {
                    "name": "bell",
                    "circuit": {"format": "qasm2", "inline": BELL_QASM2},
                    "backend": backend,
                    "assertions": [],
                }
            ],
        }
    )


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_noise_model_degrades_distribution_into_device_regime():
    from shotgate.config import LoadedWorkflow
    from shotgate.validation import metrics

    ideal = {"00": 0.5, "11": 0.5}
    clean = (
        Runner(LoadedWorkflow(_bell_workflow(), EXAMPLES), allow_empty=True)
        .run()
        .jobs[0]
    )
    noisy = (
        Runner(
            LoadedWorkflow(
                _bell_workflow(
                    {
                        "depolarizing_1q": 0.004,
                        "depolarizing_2q": 0.012,
                        "readout_p0": 0.06,
                        "readout_p1": 0.07,
                    }
                ),
                EXAMPLES,
            ),
            allow_empty=True,
        )
        .run()
        .jobs[0]
    )

    clean_tvd = metrics.total_variation_distance(
        metrics.counts_to_probabilities(clean.counts), ideal
    )
    noisy_tvd = metrics.total_variation_distance(
        metrics.counts_to_probabilities(noisy.counts), ideal
    )
    # Noise moves the clean (~0) distribution into the real-device regime.
    assert clean_tvd < 0.01 < noisy_tvd
    assert clean.metrics["backend_metadata"]["noisy"] is False
    assert noisy.metrics["backend_metadata"]["noisy"] is True
    # The noisy run leaks into the forbidden |01>/|10> states; the clean one does not.
    assert metrics.support_leakage(noisy.counts, ["00", "11"]) > 0.05


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit not installed")
def test_structural_only_job_skips_execution():
    from shotgate.config import LoadedWorkflow, parse_workflow

    wf = parse_workflow(
        {
            "apiVersion": "shotgate.dev/v1alpha1",
            "kind": "QuantumWorkflow",
            "metadata": {"name": "structural"},
            "jobs": [
                {
                    "name": "shape",
                    "circuit": {"format": "qasm2", "inline": BELL_QASM2},
                    "backend": {"provider": "local-aer"},
                    "assertions": [
                        {"type": "circuit_depth", "max": 6},
                        {"type": "gate_set", "allowed": ["h", "cx"]},
                    ],
                }
            ],
        }
    )
    report = Runner(LoadedWorkflow(wf, EXAMPLES)).run()
    job = report.jobs[0]
    assert report.passed
    # The backend was never run: no counts, no backend metadata, executed=False.
    assert job.metrics.get("executed") is False
    assert "backend_metadata" not in job.metrics
    assert job.counts == {}
    assert job.metrics["depth"] == 3  # h, cx, measure


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_kl_auto_readout_uses_noise_block_calibration():
    from shotgate.config import LoadedWorkflow, parse_workflow

    # A noisy local-aer run attaches its readout calibration; kl_divergence picks it up
    # automatically (no config) so the divergence stays finite despite the leakage (ADR-0015).
    doc = {
        "apiVersion": "shotgate.dev/v1alpha1",
        "kind": "QuantumWorkflow",
        "metadata": {"name": "auto"},
        "jobs": [
            {
                "name": "bell",
                "circuit": {"format": "qasm2", "inline": BELL_QASM2},
                "backend": {
                    "provider": "local-aer",
                    "shots": 8192,
                    "seed": 7,
                    "noise": {"readout_p0": 0.06, "readout_p1": 0.07},
                },
                "assertions": [
                    {
                        "type": "kl_divergence",
                        "expected": {"00": 0.5, "11": 0.5},
                        "max_divergence": 0.5,
                    }
                ],
            }
        ],
    }
    a = Runner(LoadedWorkflow(parse_workflow(doc), EXAMPLES)).run().jobs[0].assertions[0]
    # auto pulled the simulated readout calibration from the noise block; KL is finite.
    assert math.isfinite(a.metrics["kl_divergence"])
    assert "readout-aware" in a.message and "noise-model" in a.message


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_chi_square_runs_on_local_aer_simulator():
    from shotgate.config import LoadedWorkflow, parse_workflow

    # local-aer reports simulator=True, so chi_square evaluates normally (it is not blocked).
    doc = {
        "apiVersion": "shotgate.dev/v1alpha1",
        "kind": "QuantumWorkflow",
        "metadata": {"name": "sim-chi"},
        "jobs": [
            {
                "name": "bell",
                "circuit": {"format": "qasm2", "inline": BELL_QASM2},
                "backend": {"provider": "local-aer", "shots": 8192, "seed": 7},
                "assertions": [
                    {
                        "type": "chi_square",
                        "expected": {"00": 0.5, "11": 0.5},
                        "significance": 0.01,
                    }
                ],
            }
        ],
    }
    job = Runner(LoadedWorkflow(parse_workflow(doc), EXAMPLES)).run().jobs[0]
    assert job.metrics["backend_metadata"]["simulator"] is True
    assert job.assertions[0].passed
    assert "simulators only" not in job.assertions[0].message


# A circuit whose output distribution is far from a Bell pair's, for the differential
# fail case: all-zero rather than a 50/50 superposition over |00>/|11>.
ALL_ZERO_QASM2 = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
    "qreg q[2];\ncreg c[2];\nmeasure q -> c;\n"
)


def _differential_workflow(
    second_circuit: str, max_distance: float = 0.05, against: str = "baseline"
):
    from shotgate.config import parse_workflow

    return parse_workflow(
        {
            "apiVersion": "shotgate.dev/v1alpha1",
            "kind": "QuantumWorkflow",
            "metadata": {"name": "differential"},
            "jobs": [
                {
                    "name": "baseline",
                    "circuit": {"format": "qasm2", "inline": BELL_QASM2},
                    "backend": {"provider": "local-aer", "shots": 8192, "seed": 1},
                    "assertions": [],
                },
                {
                    "name": "shadow",
                    "circuit": {"format": "qasm2", "inline": second_circuit},
                    "backend": {"provider": "local-aer", "shots": 8192, "seed": 2},
                    "assertions": [
                        {
                            "type": "differential",
                            "against_job": against,
                            "max_distance": max_distance,
                        }
                    ],
                },
            ],
        }
    )


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_differential_passes_when_the_second_run_agrees():
    from shotgate.config import LoadedWorkflow

    wf = _differential_workflow(BELL_QASM2)  # same circuit, a different seed
    report = Runner(LoadedWorkflow(wf, EXAMPLES), allow_empty=True).run()
    assert report.passed
    shadow = report.jobs[1].assertions[0]
    assert shadow.passed
    assert "baseline" in shadow.message


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_differential_fails_when_the_second_run_diverges():
    from shotgate.config import LoadedWorkflow

    wf = _differential_workflow(ALL_ZERO_QASM2)  # a genuinely different circuit
    report = Runner(LoadedWorkflow(wf, EXAMPLES), allow_empty=True).run()
    assert not report.passed
    shadow = report.jobs[1].assertions[0]
    assert not shadow.passed
    assert shadow.metrics["tvd"] > 0.4


@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_differential_fails_closed_on_a_forward_or_missing_reference():
    from shotgate.config import LoadedWorkflow

    # "shadow" itself has not finished executing when its own assertion evaluates, and
    # "nonexistent" was never declared: both must fail closed, not raise.
    for target in ("shadow", "nonexistent"):
        wf = _differential_workflow(BELL_QASM2, against=target)
        report = Runner(LoadedWorkflow(wf, EXAMPLES), allow_empty=True).run()
        assert not report.passed
        shadow = report.jobs[1].assertions[0]
        assert not shadow.passed
        assert "no counts" in shadow.message

"""Tests for the shotgate pytest plugin.

The collection, entry-point, and unavailable-backend tests run without a quantum
SDK: collection only parses the workflow (the SDK-free core), and backend
availability is probed with ``importlib.util.find_spec`` rather than an import. The
end-to-end pass/fail cases need the Aer simulator and are marked ``integration``.

Each inner run uses pytest's ``pytester`` fixture and ``runpytest_subprocess`` so
the plugin is loaded through its installed ``pytest11`` entry point, exactly as a
consumer would get it after ``pip install shotgate``.
"""

from __future__ import annotations

import textwrap

import pytest

from shotgate.backends.registry import available_backends

AER_AVAILABLE = available_backends().get("local-aer", False)

# A Bell pair on the local Aer simulator: two assertions, both expected to pass at
# 8192 shots, seed 1234 (TVD <= 0.05 and zero support leakage outside {00, 11}).
BELL_WORKFLOW = textwrap.dedent(
    """
    apiVersion: shotgate.dev/v1alpha1
    kind: QuantumWorkflow
    metadata:
      name: bell
    defaults:
      backend: { provider: local-aer, shots: 8192, seed: 1234 }
    jobs:
      - name: bell-pair
        circuit:
          format: qasm2
          inline: |
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[2];
            creg c[2];
            h q[0];
            cx q[0], q[1];
            measure q -> c;
        assertions:
          - type: distribution_tvd
            expected: { "00": 0.5, "11": 0.5 }
            max_distance: 0.05
          - type: allowed_states
            states: ["00", "11"]
            max_leakage: 0.0
    """
)

# Same Bell pair, but a TVD assertion that must fail: the expected distribution is
# a single state ("01") the circuit never produces, so TVD is 1.0 against a 0.0
# bound.
BELL_FAILING_WORKFLOW = textwrap.dedent(
    """
    apiVersion: shotgate.dev/v1alpha1
    kind: QuantumWorkflow
    metadata:
      name: bell-fail
    defaults:
      backend: { provider: local-aer, shots: 8192, seed: 1234 }
    jobs:
      - name: bell-pair
        circuit:
          format: qasm2
          inline: |
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[2];
            creg c[2];
            h q[0];
            cx q[0], q[1];
            measure q -> c;
        assertions:
          - type: distribution_tvd
            expected: { "01": 1.0 }
            max_distance: 0.0
    """
)

# Targets the ibm backend, whose dependency (qiskit-ibm-runtime) is not part of the
# [aer,dev] test environment, so its item must skip rather than error.
IBM_WORKFLOW = textwrap.dedent(
    """
    apiVersion: shotgate.dev/v1alpha1
    kind: QuantumWorkflow
    metadata:
      name: ibm-gate
    jobs:
      - name: ibm-job
        backend: { provider: ibm }
        circuit:
          format: qasm2
          inline: |
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[1];
            creg c[1];
            h q[0];
            measure q -> c;
        assertions:
          - type: state_probability
            state: "0"
            min: 0.4
            max: 0.6
    """
)


def test_entry_point_registered():
    """`pip install shotgate` exposes the plugin via the pytest11 entry point."""
    from importlib.metadata import entry_points

    mapping = {ep.name: ep.value for ep in entry_points(group="pytest11")}
    assert mapping.get("shotgate") == "shotgate.pytest_plugin"


def test_collect_only_one_item_per_assertion(pytester):
    """A workflow.yaml is auto-collected, one pytest item per assertion."""
    pytester.makefile(".yaml", workflow=BELL_WORKFLOW)
    result = pytester.runpytest_subprocess("--collect-only", "-q", "workflow.yaml")
    out = result.stdout.str()
    assert "bell-pair[0] TVD <= 0.05" in out
    assert "bell-pair[1] leakage <= 0.0" in out
    assert out.count("bell-pair[") == 2


def test_explicit_shotgate_file_with_custom_name(pytester):
    """--shotgate accepts a workflow file whose name is not workflow.yaml."""
    pytester.makefile(".yaml", gate=BELL_WORKFLOW)
    result = pytester.runpytest_subprocess(
        "--collect-only", "-q", "--shotgate", "gate.yaml"
    )
    out = result.stdout.str()
    assert out.count("bell-pair[") == 2


def test_ini_key_collects_workflow(pytester):
    """The shotgate_paths ini key collects a custom-named workflow file."""
    pytester.makefile(".ini", pytest="[pytest]\nshotgate_paths = gate.yaml\n")
    pytester.makefile(".yaml", gate=BELL_WORKFLOW)
    result = pytester.runpytest_subprocess("--collect-only", "-q")
    out = result.stdout.str()
    assert out.count("bell-pair[") == 2


def test_unavailable_backend_skips_with_reason(pytester):
    """A workflow needing an absent backend skips, naming the extra to install."""
    pytester.makefile(".yaml", workflow=IBM_WORKFLOW)
    result = pytester.runpytest_subprocess("-rs", "workflow.yaml")
    result.assert_outcomes(skipped=1)
    out = result.stdout.str()
    assert "backend 'ibm' unavailable" in out
    assert "shotgate[ibm]" in out


@pytest.mark.integration
@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_assertions_pass_on_aer(pytester):
    """Each passing assertion becomes a passing pytest item on the Aer backend."""
    pytester.makefile(".yaml", workflow=BELL_WORKFLOW)
    result = pytester.runpytest_subprocess("workflow.yaml")
    result.assert_outcomes(passed=2)


@pytest.mark.integration
@pytest.mark.skipif(not AER_AVAILABLE, reason="qiskit-aer not installed")
def test_failing_assertion_reports_cli_detail(pytester):
    """A failing assertion fails its item and shows the CLI Detail string."""
    pytester.makefile(".yaml", workflow=BELL_FAILING_WORKFLOW)
    result = pytester.runpytest_subprocess("-rf", "workflow.yaml")
    result.assert_outcomes(failed=1)
    assert "total variation distance" in result.stdout.str()

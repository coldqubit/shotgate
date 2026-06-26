"""Unit tests for workflow schema parsing and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from shotgate.config import BackendSpec, load_workflow, parse_workflow

VALID = {
    "apiVersion": "shotgate.dev/v1alpha1",
    "kind": "QuantumWorkflow",
    "metadata": {"name": "demo"},
    "defaults": {"backend": {"provider": "local-aer", "shots": 2048, "seed": 1}},
    "jobs": [
        {
            "name": "bell",
            "circuit": {"format": "qasm2", "inline": "OPENQASM 2.0;"},
            "assertions": [
                {"type": "distribution_tvd", "expected": {"00": 0.5, "11": 0.5}}
            ],
        }
    ],
}


def test_parse_valid_workflow():
    wf = parse_workflow(VALID)
    assert wf.metadata.name == "demo"
    assert wf.jobs[0].name == "bell"


def test_defaults_merge_into_job_backend():
    wf = parse_workflow(VALID)
    effective = wf.effective_backend(wf.jobs[0])
    # job did not set a backend -> inherits defaults
    assert effective.provider == "local-aer"
    assert effective.shots == 2048
    assert effective.seed == 1


def test_job_backend_overrides_defaults():
    doc = {**VALID}
    doc = {
        **VALID,
        "jobs": [
            {
                **VALID["jobs"][0],
                "backend": {"shots": 1024},
            }
        ],
    }
    wf = parse_workflow(doc)
    effective = wf.effective_backend(wf.jobs[0])
    assert effective.shots == 1024  # explicit override
    assert effective.provider == "local-aer"  # inherited
    assert effective.seed == 1  # inherited


def test_circuit_requires_exactly_one_source():
    bad = {**VALID["jobs"][0]["circuit"], "path": "x.qasm"}  # inline + path
    doc = {**VALID, "jobs": [{**VALID["jobs"][0], "circuit": bad}]}
    with pytest.raises(ValidationError):
        parse_workflow(doc)


def test_duplicate_job_names_rejected():
    doc = {**VALID, "jobs": [VALID["jobs"][0], VALID["jobs"][0]]}
    with pytest.raises(ValidationError):
        parse_workflow(doc)


def test_unknown_api_version_rejected():
    doc = {**VALID, "apiVersion": "shotgate.dev/v2"}
    with pytest.raises(ValidationError):
        parse_workflow(doc)


def test_extra_top_level_field_rejected():
    doc = {**VALID, "spec": {}}
    with pytest.raises(ValidationError):
        parse_workflow(doc)


def test_backend_merge_helper():
    base = BackendSpec(provider="local-aer", shots=4096, seed=99)
    override = BackendSpec.model_validate({"shots": 100})
    merged = override.merged_with_defaults(base)
    assert merged.shots == 100
    assert merged.seed == 99


def test_noise_spec_parses_and_is_strict():
    doc = {
        **VALID,
        "defaults": {
            "backend": {
                "provider": "local-aer",
                "noise": {"depolarizing_1q": 0.01, "readout_p0": 0.05},
            }
        },
    }
    wf = parse_workflow(doc)
    assert wf.defaults is not None
    assert wf.defaults.backend is not None
    assert wf.defaults.backend.noise is not None
    assert wf.defaults.backend.noise.depolarizing_1q == 0.01


def test_noise_spec_rejects_unknown_field_and_out_of_range():
    bad = {
        **VALID,
        "defaults": {"backend": {"provider": "local-aer", "noise": {"bogus": 0.1}}},
    }
    with pytest.raises(ValidationError):
        parse_workflow(bad)
    oob = {
        **VALID,
        "defaults": {
            "backend": {"provider": "local-aer", "noise": {"readout_p0": 1.5}}
        },
    }
    with pytest.raises(ValidationError):
        parse_workflow(oob)


def test_noise_merges_from_defaults_into_job_backend():
    doc = {
        **VALID,
        "defaults": {
            "backend": {"provider": "local-aer", "noise": {"depolarizing_2q": 0.02}}
        },
    }
    wf = parse_workflow(doc)
    effective = wf.effective_backend(wf.jobs[0])
    assert effective.noise is not None
    assert effective.noise.depolarizing_2q == 0.02


def test_load_workflow_from_disk(tmp_path: Path):
    wf_file = tmp_path / "wf.yaml"
    wf_file.write_text(
        textwrap.dedent(
            """
            apiVersion: shotgate.dev/v1alpha1
            kind: QuantumWorkflow
            metadata:
              name: from-disk
            jobs:
              - name: j1
                circuit:
                  inline: "OPENQASM 2.0;"
                assertions: []
            """
        ),
        encoding="utf-8",
    )
    loaded = load_workflow(wf_file)
    assert loaded.workflow.metadata.name == "from-disk"
    assert loaded.base_dir == tmp_path

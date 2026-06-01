"""Tests for the IBM Runtime backend's counts extraction.

The error paths use lightweight fakes (no quantum SDK). The happy path is validated
against a *real* Qiskit V2 result (``StatevectorSampler`` produces the same
``DataBin``/``BitArray`` container that ``qiskit_ibm_runtime.SamplerV2`` returns), so
the extraction logic is exercised without needing IBM credentials. A real-hardware
smoke test is included but skipped unless ``SHOTGATE_IBM_TOKEN`` is set.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from shotgate.backends.ibm_runtime import extract_counts

QISKIT = importlib.util.find_spec("qiskit") is not None


# --------------------------------------------------------------------------- #
# Error / disambiguation paths — pure Python, no SDK required.
# --------------------------------------------------------------------------- #


class _FakeBitArray:
    def __init__(self, counts):
        self._counts = counts

    def get_counts(self):
        return self._counts


class _FakeDataBin:
    def __init__(self, registers):
        self._registers = registers

    def keys(self):
        return list(self._registers)

    def __getitem__(self, key):
        return self._registers[key]


class _FakePub:
    def __init__(self, registers):
        self.data = _FakeDataBin(registers)


def test_single_register_is_used():
    pub = _FakePub({"c": _FakeBitArray({"00": 5, "11": 7})})
    assert extract_counts(pub) == {"00": 5, "11": 7}


def test_explicit_register_selected():
    pub = _FakePub(
        {"c0": _FakeBitArray({"0": 3}), "c1": _FakeBitArray({"1": 4})}
    )
    assert extract_counts(pub, register="c1") == {"1": 4}


def test_missing_requested_register_raises():
    pub = _FakePub({"c": _FakeBitArray({"00": 1})})
    with pytest.raises(RuntimeError, match="not found"):
        extract_counts(pub, register="nope")


def test_no_register_raises():
    pub = _FakePub({})
    with pytest.raises(RuntimeError, match="no classical register"):
        extract_counts(pub)


def test_ambiguous_registers_raise():
    pub = _FakePub(
        {"c0": _FakeBitArray({"0": 1}), "c1": _FakeBitArray({"1": 1})}
    )
    with pytest.raises(RuntimeError, match="multiple classical registers"):
        extract_counts(pub)


# --------------------------------------------------------------------------- #
# Happy path against a genuine Qiskit V2 result container.
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.skipif(not QISKIT, reason="qiskit not installed")
def test_extract_counts_against_real_databin():
    from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister
    from qiskit.primitives import StatevectorSampler

    qr, cr = QuantumRegister(2, "q"), ClassicalRegister(2, "c")
    qc = QuantumCircuit(qr, cr)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    pub = StatevectorSampler().run([qc], shots=1024).result()[0]
    counts = extract_counts(pub)
    assert sum(counts.values()) == 1024
    assert set(counts) <= {"00", "11"}

    # measure_all() produces a register named "meas" — still handled.
    qc2 = QuantumCircuit(2)
    qc2.h(0)
    qc2.cx(0, 1)
    qc2.measure_all()
    pub2 = StatevectorSampler().run([qc2], shots=512).result()[0]
    assert sum(extract_counts(pub2).values()) == 512


# --------------------------------------------------------------------------- #
# Real-hardware smoke test — only runs when a token is present.
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("SHOTGATE_IBM_TOKEN"),
    reason="set SHOTGATE_IBM_TOKEN to run the real IBM hardware smoke test",
)
def test_ibm_hardware_smoke():
    """Submit a Bell pair to a real IBM backend and gate on a loose fidelity bound.

    This consumes real QPU time/queue; it is opt-in via SHOTGATE_IBM_TOKEN. Thresholds
    are intentionally noise-tolerant (see docs/hardware-validation.md).
    """
    from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister

    from shotgate.backends.ibm_runtime import IBMRuntimeBackend
    from shotgate.validation.metrics import hellinger_fidelity

    qr, cr = QuantumRegister(2, "q"), ClassicalRegister(2, "c")
    qc = QuantumCircuit(qr, cr)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    backend = IBMRuntimeBackend(name=os.environ.get("SHOTGATE_IBM_BACKEND"))
    result = backend.run(qc, shots=2048)
    fidelity = hellinger_fidelity(result.counts, {"00": 0.5, "11": 0.5})
    assert fidelity >= 0.7, f"unexpectedly low device fidelity: {fidelity:.3f}"

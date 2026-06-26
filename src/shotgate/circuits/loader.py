# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Load quantum circuits from a :class:`~shotgate.config.CircuitSpec`.

OpenQASM (2.0 or 3.0) is the interchange format: it is portable across SDKs and
keeps workflows free of executable Python, which matters for a tool that runs
untrusted circuits in CI. Qiskit is imported lazily so the validation core stays
dependency-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shotgate.config import CircuitSpec


def load_circuit(spec: CircuitSpec, base_dir: Path) -> Any:
    """Return a Qiskit ``QuantumCircuit`` for ``spec``.

    If the loaded circuit has no classical bits, a full measurement is appended so
    that the backend produces counts.
    """
    text = _read_source(spec, base_dir)
    circuit = _parse_qasm(text, spec.format)

    if circuit.num_clbits == 0:
        circuit.measure_all()
    return circuit


def _read_source(spec: CircuitSpec, base_dir: Path) -> str:
    if spec.inline is not None:
        return spec.inline
    assert spec.path is not None  # guaranteed by CircuitSpec validation
    circuit_path = (base_dir / spec.path).expanduser()
    if not circuit_path.is_file():
        raise FileNotFoundError(f"circuit file not found: {circuit_path}")
    return circuit_path.read_text(encoding="utf-8")


def _parse_qasm(text: str, fmt: str) -> Any:
    if fmt == "qasm2":
        from qiskit import qasm2

        return qasm2.loads(
            text, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS
        )
    if fmt == "qasm3":
        from qiskit import qasm3
        from qiskit.exceptions import MissingOptionalLibraryError

        try:
            return qasm3.loads(text)
        except MissingOptionalLibraryError as exc:
            raise RuntimeError(
                "OpenQASM 3 parsing requires the 'qiskit-qasm3-import' package. "
                "Install a backend extra that bundles it: "
                "pip install 'shotgate[aer]' (or 'shotgate[ibm]'); the published "
                "ghcr.io/coldqubit/shotgate images already include it."
            ) from exc
    raise ValueError(f"unsupported circuit format: {fmt!r}")


__all__ = ["load_circuit"]

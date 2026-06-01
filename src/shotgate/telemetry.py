# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 coldqubit
"""Lightweight circuit/execution telemetry for benchmarking and observability.

These metrics (width, depth, gate composition, wall-clock runtime) let teams track
regressions across commits — e.g. a transpiler change that doubles two-qubit gate
count — directly from CI. The functions duck-type Qiskit circuits and therefore do
not import any quantum SDK themselves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CircuitMetrics:
    num_qubits: int
    num_clbits: int
    depth: int
    size: int
    operations: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def circuit_metrics(circuit: Any) -> CircuitMetrics:
    """Extract structural metrics from a Qiskit-like circuit object."""
    return CircuitMetrics(
        num_qubits=int(circuit.num_qubits),
        num_clbits=int(circuit.num_clbits),
        depth=int(circuit.depth()),
        size=int(circuit.size()),
        operations={str(k): int(v) for k, v in dict(circuit.count_ops()).items()},
    )


__all__ = ["CircuitMetrics", "circuit_metrics"]

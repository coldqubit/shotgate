# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 coldqubit
"""Local Qiskit Aer simulator backend.

This is the default, zero-cost, fully-offline execution target: it runs entirely
inside the shotgate container with no cloud credentials. Ideal for fast CI gating on
small circuits (the report's "5-8 qubits, zero local RAM" MVP target).
"""

from __future__ import annotations

import importlib.util
from typing import Any

from shotgate.backends.base import Backend, BackendResult


class LocalAerBackend(Backend):
    provider = "local-aer"

    @classmethod
    def is_available(cls) -> bool:
        return (
            importlib.util.find_spec("qiskit") is not None
            and importlib.util.find_spec("qiskit_aer") is not None
        )

    def run(self, circuit: Any, shots: int, seed: int | None = None) -> BackendResult:
        from qiskit import transpile
        from qiskit_aer import AerSimulator

        simulator = AerSimulator(**self.options)
        compiled = transpile(circuit, simulator)
        result = simulator.run(compiled, shots=shots, seed_simulator=seed).result()
        counts = {str(k): int(v) for k, v in result.get_counts().items()}

        return BackendResult(
            counts=counts,
            shots=shots,
            backend_name=self.name or "aer_simulator",
            metadata={
                "provider": self.provider,
                "method": simulator.options.get("method", "automatic"),
                "seed": seed,
            },
        )

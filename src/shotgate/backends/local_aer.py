# SPDX-License-Identifier: Apache-2.0
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

# Gate names that carry the declarative depolarizing error. Gates outside these sets
# stay noiseless; the model is an approximate, uniform device proxy, not a calibration.
_ONE_QUBIT_GATES = ("h", "x", "y", "z", "sx", "rx", "ry", "rz", "s", "sdg", "t", "tdg", "u", "p")
_TWO_QUBIT_GATES = ("cx", "cz", "cy", "ecr", "cp", "swap", "rzz", "rxx", "ryy")


def _build_noise_model(noise: dict[str, Any]) -> Any | None:
    """Build a Qiskit Aer ``NoiseModel`` from a declarative :class:`NoiseSpec` mapping.

    Returns ``None`` when every parameter is zero, so a noise spec of all-zeros behaves
    exactly like the noiseless simulator.
    """
    from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

    d1 = float(noise.get("depolarizing_1q", 0.0))
    d2 = float(noise.get("depolarizing_2q", 0.0))
    p0 = float(noise.get("readout_p0", 0.0))
    p1 = float(noise.get("readout_p1", 0.0))
    if not (d1 > 0.0 or d2 > 0.0 or p0 > 0.0 or p1 > 0.0):
        return None

    model = NoiseModel()
    if d1 > 0.0:
        model.add_all_qubit_quantum_error(
            depolarizing_error(d1, 1), list(_ONE_QUBIT_GATES)
        )
    if d2 > 0.0:
        model.add_all_qubit_quantum_error(
            depolarizing_error(d2, 2), list(_TWO_QUBIT_GATES)
        )
    if p0 > 0.0 or p1 > 0.0:
        model.add_all_qubit_readout_error(
            ReadoutError([[1.0 - p0, p0], [p1, 1.0 - p1]])
        )
    return model


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

        # The noise spec (if any) was injected into options by the registry; it is not
        # an AerSimulator kwarg, so separate it before constructing the simulator.
        sim_kwargs = dict(self.options)
        noise = sim_kwargs.pop("noise", None)
        noise_model = _build_noise_model(noise) if noise else None
        if noise_model is not None:
            sim_kwargs["noise_model"] = noise_model

        simulator = AerSimulator(**sim_kwargs)
        compiled = transpile(circuit, simulator)
        result = simulator.run(compiled, shots=shots, seed_simulator=seed).result()
        counts = {str(k): int(v) for k, v in result.get_counts().items()}

        metadata: dict[str, Any] = {
            "provider": self.provider,
            "method": simulator.options.get("method", "automatic"),
            "seed": seed,
            "noisy": noise_model is not None,
        }
        # Expose the simulated readout error so `readout_error: auto` oracles can use it
        # (a noiseless run reports none, so `auto` falls back to the ideal expected).
        if noise:
            p0 = float(noise.get("readout_p0", 0.0))
            p1 = float(noise.get("readout_p1", 0.0))
            if p0 > 0.0 or p1 > 0.0:
                metadata["readout_calibration"] = {
                    "p0": p0,
                    "p1": p1,
                    "source": "noise-model",
                }

        return BackendResult(
            counts=counts,
            shots=shots,
            backend_name=self.name or "aer_simulator",
            metadata=metadata,
        )

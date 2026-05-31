"""IBM Quantum backend (real QPUs and cloud simulators) via Qiskit Runtime.

Credentials are read, in order of precedence, from the backend ``options`` token,
the ``QFORGE_IBM_TOKEN`` environment variable, or the ``QISKIT_IBM_TOKEN``
environment variable. Nothing is ever written to disk by qforge.

This backend is optional; install it with ``pip install qforge[ibm]``.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any

from qforge.backends.base import Backend, BackendResult, BackendUnavailableError


class IBMRuntimeBackend(Backend):
    provider = "ibm"

    @classmethod
    def is_available(cls) -> bool:
        return (
            importlib.util.find_spec("qiskit") is not None
            and importlib.util.find_spec("qiskit_ibm_runtime") is not None
        )

    def _token(self) -> str:
        token = (
            self.options.get("token")
            or os.environ.get("QFORGE_IBM_TOKEN")
            or os.environ.get("QISKIT_IBM_TOKEN")
        )
        if not token:
            raise BackendUnavailableError(
                "IBM backend requires an API token via backend.options.token, "
                "QFORGE_IBM_TOKEN, or QISKIT_IBM_TOKEN"
            )
        return token

    def run(self, circuit: Any, shots: int, seed: int | None = None) -> BackendResult:
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        channel = self.options.get("channel", "ibm_quantum_platform")
        instance = self.options.get("instance")
        service = QiskitRuntimeService(
            channel=channel, token=self._token(), instance=instance
        )

        if self.name:
            backend = service.backend(self.name)
        else:
            backend = service.least_busy(operational=True, simulator=False)

        pass_manager = generate_preset_pass_manager(
            optimization_level=int(self.options.get("optimization_level", 1)),
            backend=backend,
        )
        isa_circuit = pass_manager.run(circuit)

        sampler = SamplerV2(mode=backend)
        job = sampler.run([isa_circuit], shots=shots)
        pub_result = job.result()[0]

        # Extract counts from the (single) classical register of the result.
        data = pub_result.data
        register = next(iter(data.__dict__)) if hasattr(data, "__dict__") else "meas"
        bit_array = getattr(data, register)
        counts = {str(k): int(v) for k, v in bit_array.get_counts().items()}

        return BackendResult(
            counts=counts,
            shots=shots,
            backend_name=backend.name,
            metadata={
                "provider": self.provider,
                "job_id": job.job_id(),
                "channel": channel,
            },
        )

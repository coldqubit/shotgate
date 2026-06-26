# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""AWS Braket backend via the qiskit-braket-provider.

Two execution paths share one provider name:

- **Local simulation** (default): runs on Braket's ``LocalSimulator`` entirely on the host,
  with **no AWS account or credentials**. Omit ``backend.name`` or set it to ``"local"``.
- **Cloud devices / on-demand simulators**: set ``backend.name`` to a Braket device (e.g.
  ``"SV1"`` or a device ARN). This path requires **configured AWS credentials and Braket
  access** and is billed by AWS.

Install with ``pip install shotgate[braket]``. The SDK is imported lazily so the validation
core stays dependency-free.

Status: the local-simulation path is validated; the cloud path is implemented but its
validation requires an AWS account (see ADR-0011).
"""

from __future__ import annotations

import importlib.util
from typing import Any

from shotgate.backends.base import Backend, BackendResult, BackendUnavailableError

_LOCAL_ALIASES = {"local", "default", "braket_sv", "local_simulator"}


class BraketBackend(Backend):
    provider = "braket"

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("qiskit_braket_provider") is not None

    def _select_backend(self) -> Any:
        name = self.name
        if name is None or name.lower() in _LOCAL_ALIASES:
            from qiskit_braket_provider import BraketLocalBackend

            return BraketLocalBackend()

        from qiskit_braket_provider import BraketProvider

        try:
            return BraketProvider().get_backend(name)
        except Exception as exc:
            raise BackendUnavailableError(
                f"Braket device {name!r} is not available. Local simulation needs no AWS "
                "account (omit backend.name or set it to 'local'); cloud devices require "
                f"configured AWS credentials and Braket access. Original error: {exc}"
            ) from exc

    def run(self, circuit: Any, shots: int, seed: int | None = None) -> BackendResult:
        backend = self._select_backend()
        job = backend.run(circuit, shots=shots)
        result = job.result()
        counts = {
            str(k).replace(" ", ""): int(v) for k, v in result.get_counts().items()
        }
        return BackendResult(
            counts=counts,
            shots=shots,
            backend_name=getattr(backend, "name", None) or self.name or "braket-local",
            metadata={
                "provider": self.provider,
                "device": self.name or "local",
                # Braket does not honor a simulator seed through this path; runs are
                # not deterministic. Recorded for traceability only.
                "seed_requested": seed,
            },
        )

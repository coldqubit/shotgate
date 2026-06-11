# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""IBM Quantum backend (real QPUs and cloud simulators) via Qiskit Runtime.

Credentials are read, in order of precedence, from the backend ``options`` token,
the ``SHOTGATE_IBM_TOKEN`` environment variable, or the ``QISKIT_IBM_TOKEN``
environment variable. Nothing is ever written to disk by shotgate.

This backend is optional; install it with ``pip install shotgate[ibm]`` or use the
``ghcr.io/coldqubit/shotgate:<ver>-ibm`` image variant.

Status: **validated on real hardware** (``ibm_fez``, 2026-06-11: Bell, GHZ, and
Grover hardware gates passed at 4096 shots). See ``docs/hardware-validation.md``
for the runbook and the measured baseline.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any

from shotgate.backends.base import Backend, BackendResult, BackendUnavailableError


def _field(data: Any, name: str) -> Any:
    """Access a DataBin field by name, tolerating mapping- or attribute-style access."""
    try:
        return data[name]
    except (TypeError, KeyError):
        return getattr(data, name)


def _register_names(data: Any) -> list[str]:
    """Return the classical-register field names of a Qiskit V2 ``DataBin``.

    Recent qiskit exposes them via ``keys()``; we fall back to attribute discovery
    for older/edge shapes.
    """
    if hasattr(data, "keys"):
        try:
            return list(data.keys())
        except Exception:
            # Fall through to attribute discovery for older/edge DataBin shapes.
            pass
    return [n for n in dir(data) if not n.startswith("_")]


def extract_counts(pub_result: Any, register: str | None = None) -> dict[str, int]:
    """Robustly read measurement counts from a Qiskit Runtime SamplerV2 pub result.

    A V2 result's ``.data`` is a ``DataBin`` whose fields are the circuit's classical
    registers (e.g. ``c`` from ``creg c[2]``, or ``meas`` from ``measure_all``); each
    field is a ``BitArray`` exposing ``get_counts()``.

    - If ``register`` is given, that register is used (error if absent).
    - If exactly one register carries counts, it is used.
    - Zero or multiple ambiguous registers raise a clear error rather than guessing.
    """
    data = pub_result.data
    names = _register_names(data)
    counts_fields = [
        n for n in names if hasattr(_field(data, n), "get_counts")
    ]

    if register is not None:
        if register not in counts_fields:
            raise RuntimeError(
                f"requested classical register {register!r} not found in result; "
                f"available registers with counts: {counts_fields or names}"
            )
        chosen = register
    elif len(counts_fields) == 1:
        chosen = counts_fields[0]
    elif not counts_fields:
        raise RuntimeError(
            "no classical register with counts found in the Sampler result "
            f"(fields seen: {names}); ensure the circuit contains measurements"
        )
    else:
        raise RuntimeError(
            f"multiple classical registers {counts_fields} found; disambiguate by "
            "setting backend.options.register to one of them"
        )

    bit_array = _field(data, chosen)
    return {str(k): int(v) for k, v in bit_array.get_counts().items()}


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
            or os.environ.get("SHOTGATE_IBM_TOKEN")
            or os.environ.get("QISKIT_IBM_TOKEN")
        )
        if not token:
            raise BackendUnavailableError(
                "IBM backend requires an API token via backend.options.token, "
                "SHOTGATE_IBM_TOKEN, or QISKIT_IBM_TOKEN"
            )
        return token

    def run(self, circuit: Any, shots: int, seed: int | None = None) -> BackendResult:
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        # "ibm_quantum_platform" is the current channel; the legacy "ibm_quantum"
        # name was removed in qiskit-ibm-runtime. Override via options if needed.
        channel = self.options.get("channel", "ibm_quantum_platform")
        instance = self.options.get("instance")
        service = QiskitRuntimeService(
            channel=channel, token=self._token(), instance=instance
        )

        if self.name:
            try:
                backend = service.backend(self.name)
            except Exception as exc:
                # A pinned device that is not visible to this account/instance (a
                # different plan, region, or instance exposes a different device set)
                # otherwise fails with an opaque lookup error. List what is reachable
                # so the fix is obvious, and point at the least_busy default.
                available = sorted(
                    b.name
                    for b in service.backends(operational=True, simulator=False)
                )
                raise BackendUnavailableError(
                    f"device {self.name!r} is not available to this account; "
                    f"reachable real devices: {available or '(none operational)'}. "
                    "Omit backend.name to use least_busy, or pick one of the above."
                ) from exc
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

        # Robustly read counts from the named classical register(s) of the result.
        counts = extract_counts(pub_result, register=self.options.get("register"))

        return BackendResult(
            counts=counts,
            shots=shots,
            backend_name=backend.name,
            metadata={
                "provider": self.provider,
                "job_id": job.job_id(),
                "channel": channel,
                # seed is honored only on cloud simulators; ignored on real QPUs.
                "seed_requested": seed,
            },
        )

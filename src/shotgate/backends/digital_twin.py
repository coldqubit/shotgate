# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Compute a *digital-twin* expected distribution from a device noise model.

A goodness-of-fit oracle (``chi_square``, ``kl_divergence``) on real hardware fails
against the *ideal* distribution because the device leaks probability mass onto error
states the ideal assigns zero (mechanism: ``docs/hardware-validation.md``). A per-qubit
readout (assignment) error transform (``readout_error: auto``) only covers measurement
error; the dominant leakage on today's devices is gate and decoherence error, which a
readout matrix cannot see.

The digital twin closes that gap: simulate the *same* circuit through the device's full
calibrated noise model (gate + readout + thermal relaxation) and use the resulting
distribution as the expected. The oracle then asks "does the device match its own
calibrated model?" rather than "does it match the ideal?", which is a calibration-drift /
device-health check (see ADR-0014).

This module is the only place that needs Qiskit Aer to *build* an expected distribution,
so it is imported lazily by the backends, never by the SDK-free validation core. The twin
distribution is computed here, attached to ``BackendResult.metadata['noise_model_expected']``,
and consumed downstream as plain probabilities, so the core stays SDK-free.
"""

from __future__ import annotations

from typing import Any

#: Default shot budget for the twin simulation. The twin is the *expected* distribution,
#: so its sampling error must be small against the run under test: at this many shots the
#: per-bin standard error is <= 1/(2*sqrt(2e5)) ~= 0.0011, an order of magnitude below the
#: shot noise of a typical 4096-8192-shot hardware run, so it perturbs the chi-square
#: statistic negligibly. Override via ``backend.options.twin_shots``.
DEFAULT_TWIN_SHOTS = 200_000

#: Fixed simulator seed for twin reproducibility when the run itself has no usable seed
#: (e.g. a real QPU). Keeps a twin-gated workflow deterministic across re-runs.
_TWIN_SEED = 20260630


def twin_distribution(
    isa_circuit: Any,
    noise_model: Any,
    *,
    shots: int = DEFAULT_TWIN_SHOTS,
    seed: int | None = None,
) -> dict[str, float]:
    """Sample ``isa_circuit`` through ``noise_model`` and return a probability distribution.

    Sampling (rather than an analytic density-matrix marginalisation) is deliberate: the
    measured counts come back in the circuit's own classical-register format via
    ``get_counts()``, so the twin distribution is keyed identically to the observed counts
    with no manual marginalisation, qubit-to-clbit mapping, or bit-order handling, and it
    captures readout error (applied at measurement sampling) exactly as the device model
    defines it. Scales like the noiseless simulator (no ``4^n`` density matrix).

    Returns a ``{bitstring: probability}`` mapping over the outcomes that occurred.
    """
    from qiskit_aer import AerSimulator

    simulator = AerSimulator(noise_model=noise_model)
    sim_seed = seed if seed is not None else _TWIN_SEED
    result = simulator.run(isa_circuit, shots=shots, seed_simulator=sim_seed).result()
    counts = {str(k).replace(" ", ""): int(v) for k, v in result.get_counts().items()}
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


__all__ = ["DEFAULT_TWIN_SHOTS", "twin_distribution"]

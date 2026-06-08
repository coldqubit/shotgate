# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Backend abstraction.

A backend executes a circuit and returns measurement counts. The interface is
intentionally minimal so new providers (local simulators, IBM, AWS Braket, …) can
be added without touching the runner or the validation core. Heavy SDKs are
imported lazily inside concrete backends, never at module import time.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackendResult:
    """Result of executing a circuit on a backend."""

    counts: dict[str, int]
    shots: int
    backend_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Backend(abc.ABC):
    """Abstract execution target for a quantum circuit."""

    #: Stable provider identifier used in workflow YAML (e.g. ``"local-aer"``).
    provider: str = "abstract"

    def __init__(
        self,
        name: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.options = options or {}

    @abc.abstractmethod
    def run(self, circuit: Any, shots: int, seed: int | None = None) -> BackendResult:
        """Execute ``circuit`` for ``shots`` repetitions and return counts."""

    @classmethod
    def is_available(cls) -> bool:
        """Whether this backend's optional dependencies are importable."""
        return True


class BackendUnavailableError(RuntimeError):
    """Raised when a backend is selected but its dependencies are missing."""

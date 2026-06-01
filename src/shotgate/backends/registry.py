# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 coldqubit
"""Backend registry with lazy, dependency-free dispatch.

Concrete backends are referenced by import path and only imported when actually
requested, so importing shotgate (and running the validation core) never requires a
quantum SDK to be installed.
"""

from __future__ import annotations

import importlib

from shotgate.backends.base import Backend, BackendUnavailableError
from shotgate.config import BackendSpec

# provider name -> "module:ClassName"
_REGISTRY: dict[str, str] = {
    "local-aer": "shotgate.backends.local_aer:LocalAerBackend",
    "ibm": "shotgate.backends.ibm_runtime:IBMRuntimeBackend",
}


def _load_class(provider: str) -> type[Backend]:
    try:
        target = _REGISTRY[provider]
    except KeyError:
        raise ValueError(
            f"unknown backend provider {provider!r}; "
            f"available: {', '.join(sorted(_REGISTRY))}"
        ) from None
    module_name, class_name = target.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def get_backend(spec: BackendSpec) -> Backend:
    """Instantiate the backend described by ``spec``.

    Raises :class:`BackendUnavailableError` if the backend's optional
    dependencies are not installed.
    """
    backend_cls = _load_class(spec.provider)
    if not backend_cls.is_available():
        raise BackendUnavailableError(
            f"backend {spec.provider!r} is selected but its dependencies are not "
            f"installed; install the matching extra, e.g. pip install 'shotgate[aer]'"
        )
    return backend_cls(name=spec.name, options=spec.options)


def available_backends() -> dict[str, bool]:
    """Map each known provider to whether its dependencies are importable."""
    status: dict[str, bool] = {}
    for provider in _REGISTRY:
        try:
            status[provider] = _load_class(provider).is_available()
        except Exception:
            status[provider] = False
    return status


def register_backend(provider: str, target: str) -> None:
    """Register a third-party backend as ``"module:ClassName"`` (plugin hook)."""
    _REGISTRY[provider] = target


__all__ = [
    "BackendUnavailableError",
    "available_backends",
    "get_backend",
    "register_backend",
]

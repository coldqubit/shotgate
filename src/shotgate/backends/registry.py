# SPDX-License-Identifier: Apache-2.0
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

# provider name -> pip extra that supplies its dependencies
_PROVIDER_EXTRA: dict[str, str] = {
    "local-aer": "aer",
    "ibm": "ibm",
}


def extra_for_provider(provider: str) -> str:
    """Return the pip extra (``shotgate[<extra>]``) that supplies a provider's deps."""
    return _PROVIDER_EXTRA.get(provider, provider)


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
        extra = extra_for_provider(spec.provider)
        raise BackendUnavailableError(
            f"backend {spec.provider!r} is selected but its dependencies are not "
            f"installed. Install the matching extra to use shotgate from a pip "
            f"install (CLI or pytest plugin): pip install 'shotgate[{extra}]'. "
            f"The published image ghcr.io/coldqubit/shotgate bakes the aer backend "
            f"in (use the :latest-ibm tag for ibm)."
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
    "extra_for_provider",
    "get_backend",
    "register_backend",
]

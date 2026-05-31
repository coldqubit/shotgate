"""Pluggable execution backends for quantum circuits."""

from qforge.backends.base import Backend, BackendResult, BackendUnavailableError
from qforge.backends.registry import (
    available_backends,
    get_backend,
    register_backend,
)

__all__ = [
    "Backend",
    "BackendResult",
    "BackendUnavailableError",
    "available_backends",
    "get_backend",
    "register_backend",
]

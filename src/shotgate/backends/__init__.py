# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Pluggable execution backends for quantum circuits."""

from shotgate.backends.base import Backend, BackendResult, BackendUnavailableError
from shotgate.backends.registry import (
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

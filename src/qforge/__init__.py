"""qforge — container-native CI/CD quality gates for quantum circuits.

qforge validates the *probabilistic* output of quantum circuits using statistical
oracles (total variation distance, Hellinger fidelity, chi-square goodness-of-fit)
so that quantum programs can be tested in ordinary CI/CD pipelines, across
simulators and real QPUs, defined entirely as code.
"""

from __future__ import annotations

__version__ = "0.1.0"

from qforge.config import Workflow, load_workflow
from qforge.validation import Assertion, AssertionResult

__all__ = [
    "Assertion",
    "AssertionResult",
    "Workflow",
    "__version__",
    "load_workflow",
]

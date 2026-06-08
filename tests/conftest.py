"""Shared test configuration.

Enables pytest's ``pytester`` fixture so the shotgate pytest plugin can be
exercised in isolated, in-tree pytest runs.
"""

pytest_plugins = ["pytester"]

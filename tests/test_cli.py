# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Unit tests for the shotgate CLI's SDK-free commands (no quantum SDK required)."""

from __future__ import annotations

from click.testing import CliRunner

from shotgate.cli import main


def test_shots_margin_plans_a_sample_size():
    result = CliRunner().invoke(main, ["shots", "--margin", "0.01"])
    assert result.exit_code == 0
    assert "9604 shots" in result.output


def test_shots_effect_size_plans_a_sample_size():
    result = CliRunner().invoke(
        main, ["shots", "--effect-size", "0.05", "--alpha", "0.01", "--power", "0.9"]
    )
    assert result.exit_code == 0
    assert "5952 shots" in result.output


def test_shots_requires_exactly_one_of_margin_or_effect_size():
    neither = CliRunner().invoke(main, ["shots"])
    assert neither.exit_code != 0

    both = CliRunner().invoke(main, ["shots", "--margin", "0.01", "--effect-size", "0.05"])
    assert both.exit_code != 0


def test_shots_rejects_an_invalid_margin():
    result = CliRunner().invoke(main, ["shots", "--margin", "0"])
    assert result.exit_code != 0

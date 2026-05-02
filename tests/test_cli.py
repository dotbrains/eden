"""Verify the eden CLI entry point works and exposes the init subcommand."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "eden" in result.output.lower()


def test_init_subcommand_exists() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0, result.output

"""Verify the eden CLI entry point works and exposes the init subcommand."""

from __future__ import annotations

from typer.testing import CliRunner

from eden.cli.main import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "eden" in result.output.lower()


def test_init_subcommand_exists() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0, result.output


def test_init_stub_reports_not_implemented() -> None:
    result = runner.invoke(app, ["init"])
    # Stub exits non-zero with a clear message; full scaffolder lands in phase 6.
    assert result.exit_code == 1, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "not implemented" in combined.lower()
    assert "phase 6" in combined.lower()

"""Verify `eden init` validation and non-interactive behavior."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app
from tests.unit.cli.cli_init_helpers import strip_ansi

pytestmark = pytest.mark.unit


def test_init_refuses_overwrite_existing_eden(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    (repo_dir / ".eden").mkdir()
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stderr or "")
    assert "refusing to overwrite" in combined.lower()


def test_init_invalid_sandbox_rejected(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--sandbox", "kvm"],
    )
    assert result.exit_code != 0


def test_init_invalid_agent_rejected(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--agent", "bogus"],
    )
    assert result.exit_code != 0


def test_init_unsupported_template_rejected(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "non-existent-template"],
    )
    assert result.exit_code != 0


def test_init_non_tty_missing_flag_fails_fast(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    """Without --yes and with no TTY, init names the absent flag, not a hang."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    # Normalize: drop color, drop rich's box borders, collapse the wrapping
    # whitespace it inserts, so the message reads as one contiguous string.
    raw = strip_ansi((result.output or "") + (result.stderr or ""))
    combined = re.sub(r"\s+", " ", raw.replace("│", " "))
    assert "--sandbox" in combined
    assert "is required when stdin is not a TTY" in combined
    assert not (repo_dir / ".eden").exists()


def test_init_non_tty_all_flags_succeeds_without_yes(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    """Every option supplied as a flag → fully non-interactive, no --yes."""
    result = runner.invoke(
        app,
        [
            "init",
            "--sandbox",
            "docker",
            "--agent",
            "codex",
            "--model",
            "gpt-5.4",
            "--template",
            "blank",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (repo_dir / ".eden").is_dir()

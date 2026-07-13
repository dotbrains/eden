"""Verify `eden run` real implementation.

The command translates flags into an in-process ``eden.run()`` call, so the
unit tests stub ``eden.run`` and assert the right ``agent``/``sandbox``/
``prompt`` were forwarded. End-to-end execution is covered separately by
``test_run_smoke.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import eden
from eden.cli.main import app

pytestmark = pytest.mark.unit


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace ``eden.run`` with a MagicMock that returns a fake RunResult."""
    fake_result = MagicMock()
    fake_result.completion_signal = "<promise>COMPLETE</promise>"
    fake_result.iterations = [MagicMock()]
    fake_result.branch = "eden/test-branch"
    mock = MagicMock(return_value=fake_result)
    monkeypatch.setattr("eden.cli.run.eden.run", mock)
    return mock


def _kwargs(call: Any) -> dict[str, Any]:
    return dict(call.kwargs)


def test_run_invokes_eden_run_with_simple_loop_prompt(
    runner: CliRunner, fake_run: MagicMock
) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--template",
            "simple-loop",
            "--sandbox",
            "no-sandbox",
            "--agent",
            "claude-code",
            "--backlog",
            "github",
        ],
    )
    assert result.exit_code == 0, result.output
    assert fake_run.call_count == 1
    kw = _kwargs(fake_run.call_args)
    assert isinstance(kw["agent"], eden.Agent)
    assert "<promise>COMPLETE</promise>" in kw["prompt"]
    # The simple-loop prompt embeds the backlog list-tasks command.
    assert "gh issue list" in kw["prompt"]
    assert kw["max_iterations"] == 3
    assert kw["idle_timeout"] == 600.0
    assert kw["completion_timeout"] == 60.0


def test_run_rejects_unknown_template(runner: CliRunner, fake_run: MagicMock) -> None:
    result = runner.invoke(app, ["run", "--template", "bogus", "--sandbox", "no-sandbox"])
    assert result.exit_code != 0
    fake_run.assert_not_called()


def test_run_rejects_unknown_sandbox(runner: CliRunner, fake_run: MagicMock) -> None:
    result = runner.invoke(app, ["run", "--template", "simple-loop", "--sandbox", "bogus"])
    assert result.exit_code != 0
    fake_run.assert_not_called()


def test_run_requires_image_for_docker(runner: CliRunner, fake_run: MagicMock) -> None:
    import re

    result = runner.invoke(
        app,
        ["run", "--template", "simple-loop", "--sandbox", "docker"],
    )
    assert result.exit_code != 0
    # typer/rich wraps option names in per-character ANSI escapes when stderr
    # is treated as a tty (CI macOS runners do, local terminals often don't),
    # which breaks plain substring matches on `--image-name`. Strip ANSI
    # before asserting.
    combined = (result.output or "") + (result.stderr or "")
    plain = re.sub(r"\x1b\[[0-9;]*m", "", combined).lower()
    assert "image-name" in plain
    fake_run.assert_not_called()


def test_run_propagates_max_iterations(runner: CliRunner, fake_run: MagicMock) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--template",
            "simple-loop",
            "--sandbox",
            "no-sandbox",
            "--max-iterations",
            "7",
            "--idle-timeout",
            "30",
            "--completion-timeout",
            "5",
        ],
    )
    assert result.exit_code == 0, result.output
    kw = _kwargs(fake_run.call_args)
    assert kw["max_iterations"] == 7
    assert kw["idle_timeout"] == 30.0
    assert kw["completion_timeout"] == 5.0


def test_run_uses_linear_backlog_prompt(runner: CliRunner, fake_run: MagicMock) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--template",
            "simple-loop",
            "--sandbox",
            "no-sandbox",
            "--backlog",
            "linear",
        ],
    )
    assert result.exit_code == 0, result.output
    kw = _kwargs(fake_run.call_args)
    # Linear backlog uses linear-list helper baked into the dockerfile;
    # the prompt embeds that command literally.
    assert "linear-list" in kw["prompt"]

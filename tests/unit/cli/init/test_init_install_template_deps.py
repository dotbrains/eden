"""Verify `eden init --install-template-deps` behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


def _declare_blank_dependency(monkeypatch: pytest.MonkeyPatch, dependency: str = "zod") -> None:
    from eden.cli import _init_scaffold as scaffold

    monkeypatch.setitem(
        scaffold.__dict__["_TEMPLATE_METADATA"],
        "blank",
        scaffold.__dict__["_TEMPLATE_METADATA"]["blank"].__class__(
            name="blank",
            description="Bare scaffold; write your own prompt and orchestration.",
            dependencies=(dependency,),
        ),
    )


def test_init_install_template_deps_runs_missing_dependency_install(
    runner: CliRunner,
    repo_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repo_dir / "package.json").write_text(
        '{"packageManager": "pnpm@9.0.0"}',
        encoding="utf-8",
    )
    _declare_blank_dependency(monkeypatch)

    with patch("eden.cli._init_dependencies.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0
        result = runner.invoke(app, ["init", "--yes", "--install-template-deps"])

    assert result.exit_code == 0, result.output
    assert "Installing template dependency: pnpm add zod" in result.output
    run_mock.assert_called_once_with(["pnpm", "add", "zod"], check=False)


def test_init_install_template_deps_skips_existing_dependency(
    runner: CliRunner,
    repo_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repo_dir / "package.json").write_text(
        '{"dependencies": {"zod": "^4.0.0"}}',
        encoding="utf-8",
    )
    _declare_blank_dependency(monkeypatch)

    with patch("eden.cli._init_dependencies.subprocess.run") as run_mock:
        result = runner.invoke(app, ["init", "--yes", "--install-template-deps"])

    assert result.exit_code == 0, result.output
    run_mock.assert_not_called()


def test_init_install_template_deps_fails_when_install_fails(
    runner: CliRunner,
    repo_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _declare_blank_dependency(monkeypatch)

    with patch("eden.cli._init_dependencies.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 7
        result = runner.invoke(app, ["init", "--yes", "--install-template-deps"])

    assert result.exit_code == 7
    assert "template dependency install failed" in result.output

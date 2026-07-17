"""Verify `eden init` scaffold output."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


def test_init_writes_5_files_with_yes_defaults(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    assert eden_dir.is_dir()
    expected = {"Dockerfile", "prompt.md", "main.py", ".env.example", ".gitignore"}
    actual = {p.name for p in eden_dir.iterdir()}
    assert actual == expected


def test_init_dockerfile_content(runner: CliRunner, repo_dir: Path) -> None:
    runner.invoke(app, ["init", "--yes"])
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.13-slim" in dockerfile
    assert "WORKDIR /workspace" in dockerfile


def test_init_main_py_threads_claude_code_default(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert "from eden import run, claude_code" in main_py
    assert 'claude_code("claude-opus-4-8")' in main_py


def test_init_main_py_threads_codex_when_selected(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--agent", "codex"],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert "from eden import run, codex" in main_py
    assert 'codex("gpt-5.4")' in main_py


@pytest.mark.parametrize(
    ("agent", "default_model"),
    [
        ("cursor", "claude-sonnet-4-6"),
        ("copilot", "claude-sonnet-4"),
    ],
)
def test_init_main_py_threads_editor_agents_when_selected(
    runner: CliRunner,
    repo_dir: Path,
    agent: str,
    default_model: str,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--agent", agent],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert f"from eden import run, {agent}" in main_py
    assert f'{agent}("{default_model}")' in main_py


def test_init_main_py_threads_podman_sandbox(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--sandbox", "podman"],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert "from eden.sandboxes import podman as sandbox_provider" in main_py


def test_init_podman_writes_containerfile(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(app, ["init", "--yes", "--sandbox", "podman"])
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    assert (eden_dir / "Containerfile").is_file()
    assert not (eden_dir / "Dockerfile").exists()


def test_init_image_name_default_uses_repo_basename(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    """Default image name is `eden:<lowercase-cwd-basename>`."""
    # repo_dir is named "my-repo".
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert 'image="eden:my-repo"' in main_py


def test_init_image_name_explicit_override(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--image-name", "foo:bar"],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert 'image="foo:bar"' in main_py


def test_init_prints_template_metadata_and_matching_build_tool(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(app, ["init", "--yes", "--sandbox", "podman"])
    assert result.exit_code == 0, result.output
    assert "Template: blank - Bare scaffold" in result.output
    assert "podman build --build-arg AGENT_UID=$(id -u)" in result.output
    assert "-f .eden/Containerfile" in result.output


def test_init_gitignore_includes_runtime_dirs(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    gi = (repo_dir / ".eden" / ".gitignore").read_text(encoding="utf-8")
    assert ".eden/logs/" in gi
    assert ".eden/sessions/" in gi
    assert ".env" in gi

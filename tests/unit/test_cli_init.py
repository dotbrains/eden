"""Verify `eden init` real implementation."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a tmp dir, chdir into it, return the path."""
    repo = tmp_path / "my-repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    return repo


def test_init_writes_5_files_with_yes_defaults(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    assert eden_dir.is_dir()
    expected = {"Dockerfile", "prompt.md", "main.py", ".env.example", ".gitignore"}
    actual = {p.name for p in eden_dir.iterdir()}
    assert actual == expected


def test_init_refuses_overwrite_existing_eden(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    (repo_dir / ".eden").mkdir()
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stderr or "")
    assert "refusing to overwrite" in combined.lower()


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
    assert 'claude_code("claude-opus-4-7")' in main_py


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
    assert 'codex("gpt-5")' in main_py


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


def test_init_simple_loop_template_writes_files(
    runner: CliRunner, repo_dir: Path
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    expected = {"Dockerfile", "prompt.md", "main.py", ".env.example", ".gitignore"}
    assert {p.name for p in eden_dir.iterdir()} == expected


def test_init_simple_loop_github_threads_gh_commands(
    runner: CliRunner, repo_dir: Path
) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in prompt
    assert "gh issue view <ID>" in prompt
    assert "gh issue close <ID>" in prompt


def test_init_simple_loop_beads_threads_bd_commands(
    runner: CliRunner, repo_dir: Path
) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "beads"],
    )
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "bd ready --json" in prompt
    assert "bd show <ID>" in prompt
    assert "bd close <ID>" in prompt


def test_init_simple_loop_dockerfile_includes_backlog_install(
    runner: CliRunner, repo_dir: Path
) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "gh" in dockerfile  # gh CLI install line present
    assert "ARG AGENT_UID=1000" in dockerfile
    assert "USER ${AGENT_UID}:${AGENT_GID}" in dockerfile


def test_init_simple_loop_invalid_backlog_rejected(
    runner: CliRunner, repo_dir: Path
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "jira"],
    )
    assert result.exit_code != 0


def test_init_simple_loop_default_backlog_is_github(
    runner: CliRunner, repo_dir: Path
) -> None:
    """Without --backlog, --yes mode falls back to github."""
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in prompt


def test_init_gitignore_includes_runtime_dirs(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    gi = (repo_dir / ".eden" / ".gitignore").read_text(encoding="utf-8")
    assert ".eden/logs/" in gi
    assert ".eden/sessions/" in gi
    assert ".env" in gi

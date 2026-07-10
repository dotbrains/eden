"""Verify `eden init` real implementation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli import init as init_mod
from eden.cli.main import app
from tests.unit.cli_init_helpers import strip_ansi

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.cli_init_fixtures"]


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


def test_init_prints_template_metadata_and_matching_build_tool(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(app, ["init", "--yes", "--sandbox", "podman"])
    assert result.exit_code == 0, result.output
    assert "Template: blank - Bare scaffold" in result.output
    assert "podman build --build-arg AGENT_UID=$(id -u)" in result.output


def test_init_detects_package_manager_from_package_json(repo_dir: Path) -> None:
    (repo_dir / "package.json").write_text(
        '{"packageManager": "pnpm@9.0.0"}',
        encoding="utf-8",
    )
    assert init_mod._detect_package_manager(repo_dir) == "pnpm"


def test_init_detects_package_manager_from_lockfile(repo_dir: Path) -> None:
    (repo_dir / "yarn.lock").write_text("", encoding="utf-8")
    assert init_mod._detect_package_manager(repo_dir) == "yarn"


def test_init_dependency_command_matches_package_manager() -> None:
    assert init_mod._add_dependency_command("bun", "zod") == "bun add zod"
    assert init_mod._add_dependency_command("pnpm", "zod") == "pnpm add zod"
    assert init_mod._add_dependency_command("yarn", "zod") == "yarn add zod"
    assert init_mod._add_dependency_command("npm", "zod") == "npm install zod"


def test_init_detects_existing_host_dependency(repo_dir: Path) -> None:
    (repo_dir / "package.json").write_text(
        '{"devDependencies": {"zod": "^4.0.0"}}',
        encoding="utf-8",
    )
    assert init_mod._has_host_dependency(repo_dir, "zod") is True
    assert init_mod._has_host_dependency(repo_dir, "tsx") is False


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


def test_init_gitignore_includes_runtime_dirs(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    gi = (repo_dir / ".eden" / ".gitignore").read_text(encoding="utf-8")
    assert ".eden/logs/" in gi
    assert ".eden/sessions/" in gi
    assert ".env" in gi


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
            "gpt-5",
            "--template",
            "blank",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (repo_dir / ".eden").is_dir()

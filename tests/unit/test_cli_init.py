"""Verify `eden init` real implementation."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli import init as init_mod
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


def test_init_simple_loop_template_writes_files(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    expected = {"Dockerfile", "prompt.md", "main.py", ".env.example", ".gitignore"}
    assert {p.name for p in eden_dir.iterdir()} == expected


def test_init_simple_loop_github_threads_gh_commands(runner: CliRunner, repo_dir: Path) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in prompt
    assert "gh issue view <ID>" in prompt
    assert "gh issue close <ID>" in prompt


def test_init_simple_loop_beads_threads_bd_commands(runner: CliRunner, repo_dir: Path) -> None:
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


def test_init_simple_loop_invalid_backlog_rejected(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "trello"],
    )
    assert result.exit_code != 0


def test_init_simple_loop_default_backlog_is_github(runner: CliRunner, repo_dir: Path) -> None:
    """Without --backlog, --yes mode falls back to github."""
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in prompt


def test_init_simple_loop_linear_threads_helpers(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "linear"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "linear-list" in prompt
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "linear-list" in dockerfile  # helper script baked into image
    env_ex = (repo_dir / ".eden" / ".env.example").read_text(encoding="utf-8")
    assert "LINEAR_API_KEY" in env_ex


def test_init_simple_loop_jira_threads_jira_cli(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "jira"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "jira issue list" in prompt
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "jira-cli" in dockerfile
    env_ex = (repo_dir / ".eden" / ".env.example").read_text(encoding="utf-8")
    assert "JIRA_API_TOKEN" in env_ex


def test_init_gitignore_includes_runtime_dirs(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    gi = (repo_dir / ".eden" / ".gitignore").read_text(encoding="utf-8")
    assert ".eden/logs/" in gi
    assert ".eden/sessions/" in gi
    assert ".env" in gi


def test_init_github_agent_workflows_writes_workflows_and_factory(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "github-agent-workflows", "--backlog", "github"],
    )
    assert result.exit_code == 0, result.output

    implement = repo_dir / ".github" / "workflows" / "eden-agent-implement.yml"
    review = repo_dir / ".github" / "workflows" / "eden-agent-review.yml"
    factory = repo_dir / ".eden" / "github" / "factory.py"
    assert implement.is_file()
    assert review.is_file()
    assert factory.is_file()

    implement_text = implement.read_text(encoding="utf-8")
    assert "agent:implement" in implement_text
    assert "Detect issue shape" in implement_text
    assert "Preflight existing PR" in implement_text
    assert "gh pr create --draft" in implement_text

    review_text = review.read_text(encoding="utf-8")
    assert "agent:review" in review_text
    assert "Post PR review" in review_text
    assert "Post thread replies" in review_text

    assert "ThreadPoolExecutor" in factory.read_text(encoding="utf-8")


def test_init_github_agent_workflows_custom_backlog_scaffolds_setup_notes(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "github-agent-workflows", "--backlog", "custom"],
    )
    assert result.exit_code == 0, result.output

    setup = (repo_dir / ".eden" / "github" / "SETUP_TRACKER.md").read_text(encoding="utf-8")
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    env_ex = (repo_dir / ".eden" / ".env.example").read_text(encoding="utf-8")
    assert "custom" in setup
    assert "<TODO" in dockerfile
    assert "YOUR_TRACKER_TOKEN" in env_ex


def test_init_github_agent_workflows_refuses_existing_workflow_before_writing_eden(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    workflows = repo_dir / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "eden-agent-implement.yml").write_text("existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "github-agent-workflows", "--backlog", "github"],
    )

    assert result.exit_code == 1
    assert not (repo_dir / ".eden").exists()


def test_init_non_tty_missing_flag_fails_fast(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    """Without --yes and with no TTY, init names the absent flag, not a hang."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "--sandbox" in combined
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

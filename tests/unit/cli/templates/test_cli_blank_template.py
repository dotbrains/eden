"""Verify the blank-template render_blank() function."""

from __future__ import annotations

import pytest

from eden.cli._templates.blank import render_blank

pytestmark = pytest.mark.unit


def _render(**overrides: str) -> dict[str, str]:
    defaults = {
        "sandbox": "docker",
        "agent": "claude-code",
        "model": "claude-opus-4-8",
        "image_name": "eden:my-repo",
    }
    defaults.update(overrides)
    return render_blank(**defaults)


def test_render_blank_returns_five_files() -> None:
    out = _render()
    assert set(out.keys()) == {
        "Dockerfile",
        "prompt.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }


def test_dockerfile_uses_python_3_13_slim() -> None:
    out = _render()
    assert "FROM python:3.13-slim" in out["Dockerfile"]
    assert "nodejs npm" in out["Dockerfile"]


@pytest.mark.parametrize(
    ("agent", "install"),
    [
        ("claude-code", "https://claude.ai/install.sh"),
        ("codex", "@openai/codex"),
        ("opencode", "opencode-ai@latest"),
        ("pi", "@mariozechner/pi-coding-agent"),
        ("cursor", "https://cursor.com/install"),
        ("copilot", "@github/copilot"),
    ],
)
def test_dockerfile_installs_selected_agent(agent: str, install: str) -> None:
    out = _render(agent=agent)
    assert install in out["Dockerfile"]


def test_main_py_includes_claude_code_import_for_claude_code_agent() -> None:
    out = _render(agent="claude-code", model="claude-opus-4-8")
    assert "from eden import run, claude_code" in out["main.py"]
    assert 'claude_code("claude-opus-4-8")' in out["main.py"]


def test_main_py_includes_codex_import_for_codex_agent() -> None:
    out = _render(agent="codex", model="gpt-5.4")
    assert "from eden import run, codex" in out["main.py"]
    assert 'codex("gpt-5.4")' in out["main.py"]


def test_main_py_includes_opencode_import_for_opencode_agent() -> None:
    out = _render(agent="opencode", model="claude-opus-4")
    assert "from eden import run, opencode" in out["main.py"]
    assert 'opencode("claude-opus-4")' in out["main.py"]


def test_main_py_includes_pi_import_for_pi_agent() -> None:
    out = _render(agent="pi", model="pi-3.5")
    assert "from eden import run, pi" in out["main.py"]
    assert 'pi("pi-3.5")' in out["main.py"]


@pytest.mark.parametrize(
    ("agent", "model"),
    [
        ("cursor", "claude-sonnet-4-6"),
        ("copilot", "claude-sonnet-4"),
    ],
)
def test_main_py_includes_editor_agent_imports(agent: str, model: str) -> None:
    out = _render(agent=agent, model=model)
    assert f"from eden import run, {agent}" in out["main.py"]
    assert f'{agent}("{model}")' in out["main.py"]


def test_main_py_threads_docker_sandbox() -> None:
    out = _render(sandbox="docker")
    assert "from eden.sandboxes import docker as sandbox_provider" in out["main.py"]


def test_main_py_threads_podman_sandbox() -> None:
    out = _render(sandbox="podman")
    assert "from eden.sandboxes import podman as sandbox_provider" in out["main.py"]


def test_main_py_threads_image_name() -> None:
    out = _render(image_name="eden:my-test-repo")
    assert 'image="eden:my-test-repo"' in out["main.py"]


def test_main_py_preserves_completion_signal_format_string() -> None:
    """The {result.completion_signal} brace expression must survive .format().

    `BLANK_MAIN_PY` uses Python str.format() with placeholders for
    agent_import/sandbox/etc. The runtime `print(f"...{result.completion_signal}")`
    must remain intact (i.e., NOT be eaten by the template's .format() call).
    """
    out = _render()
    assert "{result.completion_signal}" in out["main.py"]


def test_gitignore_ignores_eden_runtime_dirs() -> None:
    out = _render()
    gi = out[".gitignore"]
    assert ".eden/logs/" in gi
    assert ".eden/sessions/" in gi
    assert ".eden/worktrees/" in gi
    assert ".eden/isolated/" in gi
    assert ".env" in gi


def test_env_example_documents_anthropic_and_openai_keys() -> None:
    out = _render()
    env = out[".env.example"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" in env
    assert "ANTHROPIC_API_KEY" in env
    assert "OPENAI_API_KEY" in env


def test_prompt_md_mentions_substitution_syntax() -> None:
    out = _render()
    md = out["prompt.md"]
    assert "{{SOURCE_BRANCH}}" in md
    assert "{{TARGET_BRANCH}}" in md

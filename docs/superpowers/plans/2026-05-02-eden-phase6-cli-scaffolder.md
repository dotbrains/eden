# Eden Phase 6 — `eden init` CLI Scaffolder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 1 stub at `eden/cli/init.py` with a real `eden init` scaffolder that writes `.eden/Dockerfile`, `prompt.md`, `main.py`, `.env.example`, `.gitignore`. Refuses to overwrite an existing `.eden/`.

**Architecture:** Two pieces. (1) `eden/cli/_templates/blank.py` exports five string constants + a `render_blank()` function returning `{filename: contents}`. (2) `eden/cli/init.py` parses Typer flags, prompts interactively when not `--yes`, validates, refuses overwrite, writes the 5 files. Templates `simple-loop`, `sequential-reviewer`, `parallel-planner`, `parallel-planner-with-review` are deferred to Phase 7+.

**Tech Stack:** Python 3.11+, `typer` (already in deps), `rich` (already in deps for the existing CLI). No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-05-02-eden-phase6-cli-scaffolder-design.md`

**Phase 5 base:** assumes commit `3b4bd5c` or later on `main`. Baseline: 426 unit+e2e tests passing, mypy strict clean, ruff clean.

---

## File structure

```
eden/cli/
├── init.py                          # MODIFY — replace stub with real impl
└── _templates/                      # NEW directory
    ├── __init__.py                  # NEW (empty)
    └── blank.py                     # NEW — string constants + render_blank()

tests/
├── unit/
│   └── test_cli_init.py             # NEW — tests for the real implementation
└── test_cli.py                      # MODIFY — remove test_init_stub_reports_not_implemented

README.md                            # MODIFY — bump status to phase 6 complete
```

---

## Pre-flight

- [ ] **Step 1: Confirm Phase 5 baseline**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  git status -s && git log --oneline -1 && \
  .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3
```
Expected: clean tree, on main, 426 tests passing.

---

## Task 1: Templates module — `_templates/blank.py`

**Files:**
- Create: `eden/cli/_templates/__init__.py`
- Create: `eden/cli/_templates/blank.py`
- Create: `tests/unit/test_cli_blank_template.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_blank_template.py`:

```python
"""Verify the blank-template render_blank() function."""

from __future__ import annotations

import pytest

from eden.cli._templates.blank import render_blank

pytestmark = pytest.mark.unit


def _render(**overrides: str) -> dict[str, str]:
    defaults = {
        "sandbox": "docker",
        "agent": "claude-code",
        "model": "claude-opus-4-7",
        "image_name": "eden:my-repo",
    }
    defaults.update(overrides)
    return render_blank(**defaults)  # type: ignore[arg-type]


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


def test_main_py_includes_claude_code_import_for_claude_code_agent() -> None:
    out = _render(agent="claude-code", model="claude-opus-4-7")
    assert "from eden import run, claude_code" in out["main.py"]
    assert 'claude_code("claude-opus-4-7")' in out["main.py"]


def test_main_py_includes_codex_import_for_codex_agent() -> None:
    out = _render(agent="codex", model="gpt-5")
    assert "from eden import run, codex" in out["main.py"]
    assert 'codex("gpt-5")' in out["main.py"]


def test_main_py_includes_opencode_import_for_opencode_agent() -> None:
    out = _render(agent="opencode", model="claude-opus-4")
    assert "from eden import run, opencode" in out["main.py"]
    assert 'opencode("claude-opus-4")' in out["main.py"]


def test_main_py_includes_pi_import_for_pi_agent() -> None:
    out = _render(agent="pi", model="pi-3.5")
    assert "from eden import run, pi" in out["main.py"]
    assert 'pi("pi-3.5")' in out["main.py"]


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
    assert "ANTHROPIC_API_KEY" in env
    assert "OPENAI_API_KEY" in env


def test_prompt_md_mentions_substitution_syntax() -> None:
    out = _render()
    md = out["prompt.md"]
    assert "{{SOURCE_BRANCH}}" in md
    assert "{{TARGET_BRANCH}}" in md
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_cli_blank_template.py -v`
Expected: FAIL — `eden.cli._templates.blank` not found.

- [ ] **Step 3: Create empty `_templates` package init**

Create `eden/cli/_templates/__init__.py`:

```python
"""CLI scaffolder template strings. Internal — not part of the public API."""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 4: Implement `_templates/blank.py`**

Create `eden/cli/_templates/blank.py`:

```python
"""Blank-template content for `eden init`."""

from __future__ import annotations

BLANK_DOCKERFILE = """\
FROM python:3.13-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    && rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
"""

BLANK_PROMPT_MD = """\
# Eden Prompt

Replace this content with your task description. The agent receives this
file's contents as the prompt at run time.

`{{SOURCE_BRANCH}}` and `{{TARGET_BRANCH}}` substitutions, and `` !`cmd` ``
shell-block expansion, are available — see the eden docs.
"""

BLANK_MAIN_PY = """\
\"\"\"Entry point for this Eden project.

Run with: python .eden/main.py
\"\"\"

from eden import run, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider


if __name__ == "__main__":
    result = run(
        agent={agent_call},
        sandbox=sandbox_provider.provider({image_arg}),
        prompt_file=".eden/prompt.md",
        max_iterations=5,
    )
    print(f"Completion: {{result.completion_signal}}")
"""

BLANK_ENV_EXAMPLE = """\
# Copy this file to .env and fill in the values your agent needs.

# Anthropic API key (required for claude-code)
# ANTHROPIC_API_KEY=sk-ant-...

# OpenAI API key (required for codex)
# OPENAI_API_KEY=sk-...
"""

BLANK_GITIGNORE = """\
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
"""


_AGENT_IMPORT: dict[str, str] = {
    "claude-code": "claude_code",
    "codex": "codex",
    "opencode": "opencode",
    "pi": "pi",
}

_AGENT_CALL: dict[str, str] = {
    "claude-code": 'claude_code("{model}")',
    "codex": 'codex("{model}")',
    "opencode": 'opencode("{model}")',
    "pi": 'pi("{model}")',
}


def render_blank(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the 5 .eden/ files."""
    agent_import = _AGENT_IMPORT[agent]
    agent_call = _AGENT_CALL[agent].format(model=model)
    if sandbox in ("docker", "podman"):
        image_arg = f'image="{image_name}"'
    else:
        image_arg = ""
    return {
        "Dockerfile": BLANK_DOCKERFILE,
        "prompt.md": BLANK_PROMPT_MD,
        "main.py": BLANK_MAIN_PY.format(
            agent_import=agent_import,
            agent_call=agent_call,
            sandbox=sandbox,
            image_arg=image_arg,
        ),
        ".env.example": BLANK_ENV_EXAMPLE,
        ".gitignore": BLANK_GITIGNORE,
    }


__all__ = ["render_blank"]
```

- [ ] **Step 5: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_cli_blank_template.py -v`
Expected: PASS — 13 tests.

- [ ] **Step 6: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/cli/_templates tests/unit/test_cli_blank_template.py && \
.venv/bin/ruff format eden/cli/_templates/__init__.py eden/cli/_templates/blank.py tests/unit/test_cli_blank_template.py && \
.venv/bin/ruff format --check eden/cli/_templates/__init__.py eden/cli/_templates/blank.py tests/unit/test_cli_blank_template.py && \
.venv/bin/ruff check --fix eden/cli/_templates/__init__.py eden/cli/_templates/blank.py tests/unit/test_cli_blank_template.py && \
.venv/bin/ruff check eden/cli/_templates/__init__.py eden/cli/_templates/blank.py tests/unit/test_cli_blank_template.py
```
Expected: All clean.

- [ ] **Step 7: Commit (stage by name — only 3 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/cli/_templates/__init__.py eden/cli/_templates/blank.py tests/unit/test_cli_blank_template.py && \
git commit -m "feat(cli): add blank scaffolder template + render_blank()"
```

DO NOT use `git add eden/cli/_templates`.

---

## Task 2: Replace `init_command` stub with real implementation

**Files:**
- Modify: `eden/cli/init.py` (replace stub)
- Modify: `tests/test_cli.py` (remove `test_init_stub_reports_not_implemented`)
- Create: `tests/unit/test_cli_init.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_init.py`:

```python
"""Verify `eden init` real implementation."""

from __future__ import annotations

import os
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
    runner: CliRunner, repo_dir: Path,
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
    runner: CliRunner, repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert "from eden import run, claude_code" in main_py
    assert 'claude_code("claude-opus-4-7")' in main_py


def test_init_main_py_threads_codex_when_selected(
    runner: CliRunner, repo_dir: Path,
) -> None:
    result = runner.invoke(
        app, ["init", "--yes", "--agent", "codex"],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert "from eden import run, codex" in main_py
    assert 'codex("gpt-5")' in main_py


def test_init_main_py_threads_podman_sandbox(
    runner: CliRunner, repo_dir: Path,
) -> None:
    result = runner.invoke(
        app, ["init", "--yes", "--sandbox", "podman"],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert "from eden.sandboxes import podman as sandbox_provider" in main_py


def test_init_image_name_default_uses_repo_basename(
    runner: CliRunner, repo_dir: Path,
) -> None:
    """Default image name is `eden:<lowercase-cwd-basename>`."""
    # repo_dir is named "my-repo".
    result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert 'image="eden:my-repo"' in main_py


def test_init_image_name_explicit_override(
    runner: CliRunner, repo_dir: Path,
) -> None:
    result = runner.invoke(
        app, ["init", "--yes", "--image-name", "foo:bar"],
    )
    assert result.exit_code == 0, result.output
    main_py = (repo_dir / ".eden" / "main.py").read_text(encoding="utf-8")
    assert 'image="foo:bar"' in main_py


def test_init_invalid_sandbox_rejected(
    runner: CliRunner, repo_dir: Path,
) -> None:
    result = runner.invoke(
        app, ["init", "--yes", "--sandbox", "kvm"],
    )
    assert result.exit_code != 0


def test_init_invalid_agent_rejected(
    runner: CliRunner, repo_dir: Path,
) -> None:
    result = runner.invoke(
        app, ["init", "--yes", "--agent", "bogus"],
    )
    assert result.exit_code != 0


def test_init_unsupported_template_rejected(
    runner: CliRunner, repo_dir: Path,
) -> None:
    result = runner.invoke(
        app, ["init", "--yes", "--template", "simple-loop"],
    )
    assert result.exit_code != 0


def test_init_gitignore_includes_runtime_dirs(
    runner: CliRunner, repo_dir: Path,
) -> None:
    runner.invoke(app, ["init", "--yes"])
    gi = (repo_dir / ".eden" / ".gitignore").read_text(encoding="utf-8")
    assert ".eden/logs/" in gi
    assert ".eden/sessions/" in gi
    assert ".env" in gi
```

- [ ] **Step 2: Remove the stub-asserting test from `tests/test_cli.py`**

Read the current `tests/test_cli.py`. Remove the `test_init_stub_reports_not_implemented` test (the function and its body) since the stub no longer exists. Keep all other tests in that file unchanged.

If the test in question was the LAST one and the file is otherwise empty, leave the file with just the imports + module docstring (do NOT delete the file — `tests/test_cli.py` still tests CLI help).

- [ ] **Step 3: Replace `eden/cli/init.py`**

Replace the entire contents of `eden/cli/init.py` with:

```python
"""`eden init` — scaffold a `.eden/` directory in the current repo."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from eden.cli._templates.blank import render_blank

console = Console(stderr=True)


_VALID_SANDBOXES = ("docker", "podman")
_VALID_AGENTS = ("claude-code", "codex", "opencode", "pi")
_VALID_TEMPLATES = ("blank",)

_DEFAULT_MODEL: dict[str, str] = {
    "claude-code": "claude-opus-4-7",
    "codex": "gpt-5",
    "opencode": "claude-opus-4",
    "pi": "pi-3.5",
}


def init_command(
    sandbox: str | None = typer.Option(None, "--sandbox", help="Container runtime"),
    agent: str | None = typer.Option(None, "--agent", help="Agent factory"),
    model: str | None = typer.Option(None, "--model", help="Model identifier"),
    template: str | None = typer.Option(None, "--template", help="Scaffold template"),
    image_name: str | None = typer.Option(None, "--image-name", help="Docker image tag"),
    yes: bool = typer.Option(False, "--yes", help="Accept all defaults"),
) -> None:
    """Scaffold .eden/ in the current repo."""
    target = Path.cwd() / ".eden"
    if target.exists():
        console.print(f"[red]refusing to overwrite existing {target}[/red]")
        raise typer.Exit(code=1)

    # Resolve flags interactively if not supplied (and not --yes).
    if not yes:
        sandbox = sandbox or typer.prompt("Sandbox", default="docker")
        agent = agent or typer.prompt("Agent", default="claude-code")
        # Default model depends on agent; resolve agent first so the prompt
        # default reflects the chosen agent.
        if agent not in _DEFAULT_MODEL:
            raise typer.BadParameter(
                f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
            )
        model = model or typer.prompt("Model", default=_DEFAULT_MODEL[agent])
        template = template or typer.prompt("Template", default="blank")
    else:
        sandbox = sandbox or "docker"
        agent = agent or "claude-code"
        if agent not in _DEFAULT_MODEL:
            raise typer.BadParameter(
                f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
            )
        model = model or _DEFAULT_MODEL[agent]
        template = template or "blank"

    image_name = image_name or f"eden:{Path.cwd().name.lower()}"

    if sandbox not in _VALID_SANDBOXES:
        raise typer.BadParameter(
            f"sandbox must be one of {list(_VALID_SANDBOXES)}, got {sandbox!r}",
        )
    if agent not in _VALID_AGENTS:
        raise typer.BadParameter(
            f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
        )
    if template not in _VALID_TEMPLATES:
        raise typer.BadParameter(
            f"only the 'blank' template is supported in v1, got {template!r}",
        )

    files = render_blank(
        sandbox=sandbox,
        agent=agent,
        model=model,
        image_name=image_name,
    )
    target.mkdir(parents=True)
    for name, contents in files.items():
        (target / name).write_text(contents, encoding="utf-8")

    typer.secho(f"✓ scaffolded {target}", fg="green")
    typer.echo("Next steps:")
    typer.echo("  1. cp .eden/.env.example .env  # then fill in your API keys")
    typer.echo(f"  2. docker build -t {image_name} -f .eden/Dockerfile .")
    typer.echo("  3. python .eden/main.py")
```

- [ ] **Step 4: Run passing tests**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_cli_init.py tests/test_cli.py -v`
Expected: PASS — 12 new tests + remaining pre-existing test_cli.py tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/cli tests/unit/test_cli_init.py tests/test_cli.py && \
.venv/bin/ruff format eden/cli/init.py tests/unit/test_cli_init.py tests/test_cli.py && \
.venv/bin/ruff format --check eden/cli/init.py tests/unit/test_cli_init.py tests/test_cli.py && \
.venv/bin/ruff check --fix eden/cli/init.py tests/unit/test_cli_init.py tests/test_cli.py && \
.venv/bin/ruff check eden/cli/init.py tests/unit/test_cli_init.py tests/test_cli.py
```
Expected: All clean.

- [ ] **Step 6: Run full unit + e2e suite (regression check)**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3`
Expected: All tests pass. Total: 426 (Phase 5) + 13 (T1) + 12 (T2) - 1 (removed stub-asserting test) = **450 tests**.

- [ ] **Step 7: Commit (stage by name — only 3 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/cli/init.py tests/unit/test_cli_init.py tests/test_cli.py && \
git commit -m "feat(cli): implement eden init scaffolder; replace Phase 1 stub"
```

---

## Task 3: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump status line**

Edit `README.md:5`. Replace the existing status line with:

```markdown
> **Status:** Pre-alpha. Phases 1–6 complete: package skeleton, provider Protocols, worktree manager, `no_sandbox`/`docker`/`podman` bind-mount providers, local `isolated` patch-sync provider, `daytona` and `vercel` cloud providers, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent`/`claude_code`/`codex`/`opencode`/`pi`/`cli_agent`, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, Claude Code session JSONL capture, post-iteration `finalize()` for isolated/cloud handles, and the `eden init` CLI scaffolder (blank template). Full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add README.md && \
git commit -m "docs: bump README status to phase 6 complete"
```

---

## Final verification

- [ ] **Step 1: Full local CI parity check**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/ruff format --check eden tests && \
.venv/bin/ruff check --no-cache eden tests && \
.venv/bin/mypy --strict eden tests && \
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```
Expected: every command Success / PASS. Coverage ≥ 70%.

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

- [ ] **Step 3: Tag the phase**

```bash
git tag -a phase-6 -m "Phase 6: eden init CLI scaffolder (blank template)"
git push origin phase-6
```

---

## Notes for the implementer

- **The Phase 1 stub-test must be removed.** `tests/test_cli.py` had `test_init_stub_reports_not_implemented` — that test asserted exit code 1 + "not implemented" message. After T2, the real impl exits 0 on success; the assertion fails. Remove the test function (and its imports if no longer needed). Other tests in `test_cli.py` (CLI help, version) stay.
- **Templates as Python strings, not on-disk fixtures.** This is intentional — easier to maintain than copying file fixtures. The `BLANK_MAIN_PY` template uses `str.format()` with `{agent_import}`, `{agent_call}`, `{sandbox}`, `{image_arg}` placeholders. The `{{result.completion_signal}}` double-brace escapes the `{}` so `.format()` produces a literal `{result.completion_signal}` for the runtime f-string.
- **`typer.prompt(default=...)`** auto-supplies the default when the user hits Enter. Tests pass `--yes` to avoid interactive prompts.
- **`typer.BadParameter`** triggers Typer's standard error path: prints to stderr, exit code 2.
- **`Path.cwd().name.lower()`** for the default image-name. macOS dev machines often have mixed-case repo dirs; lowercasing matches Docker's image-name conventions.
- **Coverage gate stays at 70%.** Phase 6 adds heavily-tested code; total stays well above gate.
- **No e2e tests in 6.** Running the scaffolded `main.py` requires Docker + API keys; that's user-territory.

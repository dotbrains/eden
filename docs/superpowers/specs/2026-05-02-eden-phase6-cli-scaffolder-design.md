# Eden Phase 6 — `eden init` CLI Scaffolder Design

**Status:** Approved design.

**Predecessors:** Phases 1–5 complete on `main`. Phase 1 shipped a stub `eden init` at `eden/cli/init.py` that reports "not implemented and exits 1." Phase 6 replaces the stub with a real scaffolder.

**Goal:** Implement `eden init` — interactive (or flag-driven) scaffolder that writes a `.eden/` directory with `Dockerfile`, `prompt.md`, `main.py`, `.env.example`, `.gitignore`. Refuses to overwrite an existing `.eden/`. Ships the `blank` template only; other templates from the original design are deferred to Phase 7+ docs as the corresponding patterns stabilize.

**Out of scope (deferred):**
- Templates `simple-loop`, `sequential-reviewer`, `parallel-planner`, `parallel-planner-with-review` (require GitHub API integration or multi-agent patterns not yet exposed; Phase 7+).
- `--force` flag to overwrite existing `.eden/` (none in v1; user removes manually).
- Provider-specific Dockerfile variants beyond `docker` (Phase 7+ if podman needs different tooling).

---

## 1. Public surface

```bash
$ eden init [--sandbox docker|podman] [--agent claude-code|codex|opencode|pi]
            [--model <str>] [--template blank] [--image-name <name>] [--yes]
```

| Flag | Default (interactive) | Default (--yes) | Notes |
|---|---|---|---|
| `--sandbox` | prompt | `docker` | Choices: `docker`, `podman` |
| `--agent` | prompt | `claude-code` | Choices: `claude-code`, `codex`, `opencode`, `pi` |
| `--model` | prompt | agent default | Free-form string |
| `--template` | prompt | `blank` | Choices: `blank` |
| `--image-name` | `eden:<repo-dir-name>` | same | Free-form string |
| `--yes` | n/a | required | Accept all defaults non-interactively |

Behavior:
- If `.eden/` exists, error and exit 1 (no `--force` flag).
- Print a success message + next-step instructions on completion.
- Exit code 0 on success, 1 on user error or overwrite refusal.

---

## 2. Architecture

### 2.1 New + modified files

```
eden/cli/
├── init.py                          # MODIFY — replace stub with real impl
├── _templates/                      # NEW directory
│   ├── __init__.py                  # NEW (empty)
│   └── blank.py                     # NEW — string constants for the 5 files

tests/
├── unit/
│   └── test_cli_init.py             # NEW — replace existing stub-test with real-impl tests
└── test_cli.py                      # already exists from Phase 1; not a stub-test, just exercises CLI help

README.md                            # MODIFY — bump status to phase 6 complete
```

`eden/cli/_templates/__init__.py` is empty; the underscore prevents accidental external use. Templates are Python string constants exported from `_templates/blank.py`.

The existing `tests/test_cli.py` (committed in Phase 1, commit `7a85b6f`) tests CLI help output and is unaffected. The `test_init_stub_reports_not_implemented` test in `tests/test_cli.py` REMOVES in Phase 6 (the stub no longer exists; replaced by the real impl tested in `tests/unit/test_cli_init.py`).

### 2.2 Module responsibilities

- `eden/cli/init.py` — Typer command implementation. Reads flags, prompts interactively where needed, validates, refuses overwrite, materializes `.eden/`. ~120 LoC.
- `eden/cli/_templates/blank.py` — `BLANK_DOCKERFILE`, `BLANK_PROMPT_MD`, `BLANK_MAIN_PY`, `BLANK_ENV_EXAMPLE`, `BLANK_GITIGNORE` string constants. Each is a multi-line string. `BLANK_MAIN_PY` is a template that interpolates `<sandbox>`, `<agent>`, `<model>`, `<image_name>`. ~80 LoC.

### 2.3 Per-invocation flow

```
$ eden init [flags]
        ↓
parse flags via typer
        ↓
if .eden/ exists: error("refuse to overwrite") → exit 1
        ↓
if not --yes:
    for each flag with no value: typer.prompt(...) with default
        ↓
resolve image-name (default: eden:<basename of cwd>)
        ↓
resolve template content:
    template_name = "blank" (only choice for v1)
    files = render_blank(sandbox=..., agent=..., model=..., image_name=...)
        ↓
write .eden/Dockerfile, prompt.md, main.py, .env.example, .gitignore
        ↓
print "✓ scaffolded .eden/" + next-step hints
        ↓
exit 0
```

---

## 3. Component contracts

### 3.1 `init_command` (replaces the stub in `eden/cli/init.py`)

```python
def init_command(
    sandbox: str | None = typer.Option(None, "--sandbox", help="Container runtime"),
    agent: str | None = typer.Option(None, "--agent", help="Agent factory"),
    model: str | None = typer.Option(None, "--model", help="Model identifier"),
    template: str | None = typer.Option(None, "--template", help="Scaffold template"),
    image_name: str | None = typer.Option(None, "--image-name", help="Docker image tag"),
    yes: bool = typer.Option(False, "--yes", help="Accept all defaults"),
) -> None:
    """Scaffold .eden/ in the current repo."""
```

Validation rules:
- `sandbox` must be one of `{"docker", "podman"}`. Reject otherwise via `typer.BadParameter`.
- `agent` must be one of `{"claude-code", "codex", "opencode", "pi"}`.
- `template` must be `"blank"` for v1.
- `image_name` defaults to `eden:<basename of os.getcwd()>` (lowercase, sanitized).
- `model` defaults differ per agent: `claude-code` → `claude-opus-4-7`; `codex` → `gpt-5`; `opencode` → `claude-opus-4`; `pi` → `pi-3.5`.

Pre-condition checks:
- `.eden/` must NOT exist (resolved against `Path.cwd() / ".eden"`).
- The cwd must be writable (implicit — caught by `Path.write_text()` if not).

### 3.2 `_templates/blank.py`

Five string constants:

```python
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


def render_blank(
    *,
    sandbox: str,        # "docker" | "podman"
    agent: str,          # "claude-code" | "codex" | "opencode" | "pi"
    model: str,
    image_name: str,
) -> dict[str, str]:
    """Return {filename: contents} for all 5 .eden/ files."""
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
```

The `{{` / `}}` in `BLANK_MAIN_PY` are escaped braces so the inner `{result.completion_signal}` survives the outer `.format()`.

### 3.3 `init_command` body (after Typer parses flags)

```python
def init_command(...) -> None:
    target = Path.cwd() / ".eden"
    if target.exists():
        typer.secho(f"refusing to overwrite existing {target}", fg="red", err=True)
        raise typer.Exit(code=1)

    # Resolve flags interactively if not supplied.
    if not yes:
        sandbox = sandbox or typer.prompt("Sandbox", default="docker")
        agent = agent or typer.prompt("Agent", default="claude-code")
        model = model or typer.prompt("Model", default=_DEFAULT_MODEL[agent])
        template = template or typer.prompt("Template", default="blank")
    else:
        sandbox = sandbox or "docker"
        agent = agent or "claude-code"
        model = model or _DEFAULT_MODEL[agent]
        template = template or "blank"

    image_name = image_name or f"eden:{Path.cwd().name.lower()}"

    # Validate
    if sandbox not in ("docker", "podman"):
        raise typer.BadParameter(f"sandbox must be docker or podman, got {sandbox!r}")
    if agent not in _DEFAULT_MODEL:
        raise typer.BadParameter(f"agent must be one of {sorted(_DEFAULT_MODEL)}, got {agent!r}")
    if template != "blank":
        raise typer.BadParameter(f"only the 'blank' template is supported in v1, got {template!r}")

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

Where `_DEFAULT_MODEL` is:

```python
_DEFAULT_MODEL: dict[str, str] = {
    "claude-code": "claude-opus-4-7",
    "codex": "gpt-5",
    "opencode": "claude-opus-4",
    "pi": "pi-3.5",
}
```

---

## 4. Error handling

| Failure | Behavior |
|---|---|
| `.eden/` already exists | `typer.echo("refusing to overwrite ...", err=True)` + exit 1 |
| `--sandbox` not in `{docker,podman}` | `typer.BadParameter` (Typer prints + exits 2) |
| `--agent` invalid | same |
| `--template` not `"blank"` | same |
| Cwd not writable | `OSError` from `Path.mkdir()` propagates; Typer formats |
| User declines interactive prompt (Ctrl-C) | Typer raises `Abort` → exit 1 |

The `--yes` flag never combines with interactive prompts; if both are given AND no flag value, the `--yes` default wins.

---

## 5. Concurrency

None. CLI is sync; no threads.

---

## 6. Testing strategy

### 6.1 Unit tests

`tests/unit/test_cli_init.py` (~12 tests):

Setup: each test uses `pytest.tmp_path`, `monkeypatch.chdir(tmp_path)` for cwd isolation, and `typer.testing.CliRunner` to invoke the command.

- `test_init_writes_5_files_with_yes_defaults` — `eden init --yes` creates all 5 files in `.eden/`.
- `test_init_refuses_overwrite_existing_eden` — pre-create `.eden/`; `init --yes` exits 1, prints "refusing to overwrite".
- `test_init_dockerfile_content` — `Dockerfile` matches `BLANK_DOCKERFILE` exactly.
- `test_init_main_py_threads_agent` — `--yes --agent claude-code` produces `main.py` containing `from eden import claude_code` and `claude_code("claude-opus-4-7")`.
- `test_init_main_py_threads_codex` — same with `--agent codex` → `from eden import codex`, `codex("gpt-5")`.
- `test_init_main_py_threads_sandbox` — `--sandbox podman` produces `from eden.sandboxes import podman as sandbox_provider`.
- `test_init_image_name_default` — `--yes` in dir `MyRepo` produces `image="eden:myrepo"`.
- `test_init_image_name_explicit` — `--image-name foo:bar` produces `image="foo:bar"`.
- `test_init_invalid_sandbox_rejected` — `--sandbox kvm` exits 2 (Typer BadParameter).
- `test_init_invalid_agent_rejected` — `--agent foo` exits 2.
- `test_init_invalid_template_rejected` — `--template simple-loop` exits 2 (only `blank` supported).
- `test_init_gitignore_content` — `.gitignore` includes `.eden/logs/` and `.env`.

The existing `test_init_stub_reports_not_implemented` in `tests/test_cli.py` is REMOVED (the stub no longer exists).

### 6.2 No e2e tests

The scaffolded `main.py` references `import eden` and `import eden.sandboxes.docker as ...` — these import paths exist. Actually running `python .eden/main.py` would require docker + an API key; that's user-territory, not CI-territory. Phase 7+ may add a doc-test that imports the rendered `main.py` source string.

### 6.3 Coverage

70% gate retained.

---

## 7. Backwards compatibility

- The Phase 1 stub `init_command` is replaced. The `tests/test_cli.py::test_init_stub_reports_not_implemented` test is removed — that test was ASSERTING the stub state, so removing it as the stub becomes real is correct.
- `eden version` and other CLI commands are unchanged.

---

## 8. Phase boundary

**Lands in 6:** real `eden init` with `blank` template, 5-file scaffolder, flag parsing + interactive prompts.

**Deferred to 7+:** templates `simple-loop`, `sequential-reviewer`, `parallel-planner`, `parallel-planner-with-review`. Real-Docker e2e of the scaffolded `main.py`. `--force` flag.

---

**Estimated effort:** ~2-3 days. Self-contained CLI work; no orchestrator/provider/agent changes.

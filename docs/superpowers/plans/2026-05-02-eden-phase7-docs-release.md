# Eden Phase 7 — Docs & Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the complete user-facing documentation set (14 docs + 3 ADRs + TOC), rewrite README.md for v0.1.0, add a tag-triggered PyPI release workflow with Trusted Publishing, bump the package version, and tag `v0.1.0` for first public release.

**Architecture:** Docs land first as plain markdown rendered natively by GitHub. Each doc has one clear responsibility and a fixed `# Title` + one-sentence TL;DR shape so agents can read them out of order. A single regression test (`tests/unit/test_docs_consistency.py`) asserts every name in `eden.__all__` appears in `docs/python-api.md`, catching drift when public exports change. The release workflow is a single GHA job triggered by tag push `v*`, building sdist+wheel and uploading via PyPI Trusted Publishing (no long-lived secrets).

**Tech Stack:** Markdown (GitHub-flavored), pytest (existing), GitHub Actions (existing), `pypa/gh-action-pypi-publish@release/v1`, `python -m build`, PyPI Trusted Publishing (OIDC).

---

## Pre-flight

- [ ] **Step 1: Verify clean state on `main`**

Run: `git status && git rev-parse --abbrev-ref HEAD`
Expected: `On branch main`, `nothing to commit, working tree clean`, `main`.

- [ ] **Step 2: Run baseline test suite**

Run: `.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70 -q 2>&1 | tail -5`
Expected: `450 passed` and `Required test coverage of 70% reached. Total coverage: 93.04%` (or higher).

- [ ] **Step 3: Confirm public surface size**

Run: `python -c "import eden; print(len(eden.__all__), 'names'); print(sorted(eden.__all__))"`
Expected: `46 names` followed by the sorted list. This list is what `docs/python-api.md` must cover.

- [ ] **Step 4: Confirm current version is 0.0.1**

Run: `grep '^version' pyproject.toml`
Expected: `version = "0.0.1"`.

---

## Task 1: docs/python-api.md + consistency test (TDD pair)

**Files:**
- Create: `tests/unit/test_docs_consistency.py`
- Create: `docs/python-api.md`

**Why this is task 1:** `python-api.md` is the canonical reference; it's the load-bearing doc. Writing it first establishes the public-API source of truth that other docs link to. The consistency test guards against drift.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_docs_consistency.py`:

```python
"""Regression net: every public export is documented in docs/python-api.md."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import eden

pytestmark = pytest.mark.unit


def test_docs_python_api_covers_all_public_exports() -> None:
    api_doc = Path(__file__).resolve().parents[2] / "docs" / "python-api.md"
    text = api_doc.read_text(encoding="utf-8")
    missing = [
        name
        for name in eden.__all__
        if not re.search(rf"\b{re.escape(name)}\b", text)
    ]
    assert missing == [], f"docs/python-api.md missing: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_docs_consistency.py -v`
Expected: FAIL with `FileNotFoundError: [Errno 2] No such file or directory: '.../docs/python-api.md'`.

- [ ] **Step 3: Create docs/python-api.md with the full reference**

Create `docs/python-api.md` with this structure. Every name in `eden.__all__` (the 46 names from Pre-flight Step 3) must appear at least once. Use plain markdown — code blocks fenced as ` ```python `. Each section starts with `## <Section>`.

Required structure and contents:

```markdown
# Python API

Reference for everything importable from the top-level `eden` package.

---

## Importing

```python
from eden import (
    run, create_worktree,
    RunResult, Iteration, Commit, Usage, Timeouts, Mount, FinalizeResult,
    BranchStrategy, StreamEvent, Logging,
    AbortController, AbortSignal, Aborted,
    Agent, IterationContext,
    simulated_agent, claude_code, codex, opencode, pi, cli_agent,
    Hook, HookPhase, Hooks, HostHooks, SandboxHooks,
    IsolatedSandboxHandle,
    EdenError, ConfigError, CwdError, EdenTimeoutError, EnvMergeError,
    HookError, HookFailed, HookTimeout, IdleTimeout, InvalidOptions,
    PromptError, RestAuthError, RestError, RestNotFoundError,
    RestRateLimited, SessionCaptureFailed, StepTimeout,
    __version__,
)
```

## Entry points

### `run(...)`

Document the full signature with all keyword arguments. Reference: read the function signature in `eden/orchestrator/__init__.py` (look for `def run(`). For each parameter, describe: type, default, what it does. Show the return type (`RunResult`).

Include a 15-line minimal example using `simulated_agent` and `no_sandbox` so the snippet runs without external dependencies.

### `create_worktree(...)`

Document signature from `eden/orchestrator/__init__.py`. Describe: cwd argument, branch strategy, returns a worktree handle.

## Configuration types

Document each frozen dataclass: fields, types, defaults, purpose. One H3 per type.

- `Timeouts` — read fields from `eden/_types.py`.
- `Logging` — read from `eden/logging/__init__.py`.
- `Mount` — read from `eden/providers/_types.py`.
- `BranchStrategy` — read from `eden/providers/_types.py`. List each enum value.

## Result types

One H3 per type. Field reference only.

- `RunResult` — read from `eden/_types.py`.
- `Iteration` — fields including `prompt`, `stream`, `commit`, `session_id`, `session_file_path`.
- `Commit` — read from `eden/_types.py`.
- `Usage` — read from `eden/_types.py`.
- `FinalizeResult` — read from `eden/providers/_types.py`.

## Streaming

### `StreamEvent`

Frozen dataclass. Document the four kinds via the `type` field: `text`, `idle_warning`, `tool_call`, `usage`. Read from `eden/streaming/_event.py`.

## Agents

### `Agent` Protocol

Read from `eden/agents/__init__.py`. Document the structural contract: `name: str`, `model: str`, `build_command(ctx) -> list[str]`, `parse_stream(line) -> StreamEvent | None`. Note `captures_sessions: bool` is read via `getattr` if present.

### `IterationContext`

Read from `eden/agents/__init__.py`. Document fields.

### Factories

One H3 per factory. Show signature, default model, when to use.

- `simulated_agent(...)` — read from `eden/agents/simulated/__init__.py`.
- `claude_code(...)` — read from `eden/agents/claude_code/__init__.py`. Note `captures_sessions=True`.
- `codex(...)` — default model `"gpt-5"`.
- `opencode(...)` — default model `"claude-opus-4"`.
- `pi(...)` — default model `"pi-3.5"`.
- `cli_agent(...)` — generic factory; document `name`, `model`, `binary`, `build_argv`, `parse_stream`, `captures_sessions`, `env`, `extra_args`.

## Lifecycle hooks

### `Hook`, `HookPhase`, `Hooks`, `HostHooks`, `SandboxHooks`

Read from `eden/lifecycle/__init__.py`. Document the phases (`pre_setup`, `post_setup`, `pre_iteration`, `post_iteration`, `post_run`), the `HostHooks` vs `SandboxHooks` distinction, and the ordering rules.

## Cancellation

### `AbortController`, `AbortSignal`, `Aborted`

Read from `eden/abort/__init__.py`. Document `controller.abort()`, `signal.aborted`, the `Aborted` exception that the orchestrator raises.

## Provider Protocol re-export

### `IsolatedSandboxHandle`

Read from `eden/providers/_protocols.py`. Document the structural contract; link forward to `custom-providers.md` for full Protocol details.

## Errors

Brief paragraph linking to `errors.md` for the full taxonomy. Then list each error class as a sub-bullet so `test_docs_consistency` finds them:

- `EdenError`
- `ConfigError`
- `CwdError`
- `EdenTimeoutError`
- `EnvMergeError`
- `HookError`
- `HookFailed`
- `HookTimeout`
- `IdleTimeout`
- `InvalidOptions`
- `PromptError`
- `RestAuthError`
- `RestError`
- `RestNotFoundError`
- `RestRateLimited`
- `SessionCaptureFailed`
- `StepTimeout`

## Version

### `__version__`

`eden.__version__` exposes the installed package version (read via `importlib.metadata`).
```

The implementer reads source files for accurate types/signatures. The plan above is the **structural brief**, not the full prose — the implementer fills in 1-3 sentences per H3 from the source.

- [ ] **Step 4: Run consistency test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_docs_consistency.py -v`
Expected: `1 passed`. If any names are missing, the failure message lists them — add them to the doc.

- [ ] **Step 5: Run lint + type gates**

Run: `.venv/bin/ruff format --check eden tests && .venv/bin/ruff check --no-cache eden tests && .venv/bin/mypy --strict eden tests`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_docs_consistency.py docs/python-api.md
git commit -m "docs: add python-api reference + consistency regression test"
```

---

## Task 2: docs/README.md (TOC)

**Files:**
- Create: `docs/README.md`

- [ ] **Step 1: Create docs/README.md with the full TOC**

```markdown
# Eden documentation

Python orchestrator for AI coding agents in sandboxed worktrees.

---

## Getting started

- [What is Eden?](what-is-eden.md) — positioning, feature matrix, when to use it.
- [Quick start](quick-start.md) — `eden init` to first run in five minutes.

## Reference

- [Python API](python-api.md) — every name importable from `eden`.
- [CLI](cli.md) — `eden init`, `eden version`.
- [Configuration](configuration.md) — environment variables, `Logging`, `Timeouts`.
- [Sandbox providers](sandbox-providers.md) — `no_sandbox`, `docker`, `podman`, `isolated`, `daytona`, `vercel`.
- [Agents](agents.md) — `simulated_agent`, `claude_code`, `codex`, `opencode`, `pi`, `cli_agent`.
- [Prompts](prompts.md) — `PromptSource`, args, shell blocks, built-ins.
- [Templates](templates.md) — the `blank` scaffolder template.
- [Errors](errors.md) — the `EdenError` hierarchy.

## Concepts

- [How it works](how-it-works.md) — branch strategies, worktrees, sandbox lifecycle, iteration loop.
- [Custom providers](custom-providers.md) — implementing the `IsolatedSandboxHandle` Protocol.
- [Development](development.md) — repo layout, test markers, lint and type gates, contributing.

## Architecture decision records

- [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md)
- [ADR 0002 — Sync-first public API](adr/0002-sync-first-public-api.md)
- [ADR 0003 — One agent per file](adr/0003-one-agent-per-file.md)
```

- [ ] **Step 2: Commit**

```bash
git add docs/README.md
git commit -m "docs: add docs/ table of contents"
```

Cross-links won't all resolve yet — they will after later tasks. GitHub renders dead relative links as text, not errors.

---

## Task 3: docs/what-is-eden.md + docs/quick-start.md

**Files:**
- Create: `docs/what-is-eden.md`
- Create: `docs/quick-start.md`

- [ ] **Step 1: Create docs/what-is-eden.md**

Required content:

```markdown
# What is Eden?

Eden orchestrates AI coding agents inside sandboxed git worktrees so that an agent's edits land on a real branch without contaminating your main checkout.

---

## The problem

When you let an AI agent edit files in your working tree, three things go wrong:

1. **Cross-contamination** — the agent's WIP edits mix with yours.
2. **Untracked side effects** — `pip install`, `npm install`, or schema migrations the agent ran against your real environment.
3. **No commit boundary** — partial work lives in your tree until you decide to keep or discard it.

## How Eden solves it

Eden creates a fresh git worktree on a new branch, mounts it into a container (or syncs it to a remote sandbox), runs the agent inside, captures its output, then commits the changes back. You get a branch with one clean commit per iteration, ready to review or merge.

## Feature matrix

| Capability | Status |
|---|---|
| Local providers (`no_sandbox`, `docker`, `podman`) | Stable |
| Local `isolated` provider (patch-sync) | Stable |
| Cloud providers (`daytona`, `vercel`) | Stable |
| Agents (`claude_code`, `codex`, `opencode`, `pi`, `cli_agent`) | Stable |
| Lifecycle hooks (host + sandbox) | Stable |
| Idle / abort / completion handling | Stable |
| Claude Code session JSONL capture | Stable |
| `eden init` scaffolder | Stable (blank template) |
| Additional `eden init` templates | Roadmap (v0.2+) |
| Real-binary integration tests for `codex`/`opencode`/`pi` | Roadmap (v0.2+) |

## When to use it

Use Eden when you want an agent to make real, committable changes against a real codebase but you don't want it editing the working tree you have open in your editor. It's especially valuable when running multiple agent iterations in parallel.

## When not to use it

Eden does not run agents — it orchestrates them. You still need the agent's CLI installed and authenticated. If you don't have an agent CLI yet, start with `simulated_agent` to learn the orchestrator's shape.

## See also

- [Quick start](quick-start.md)
- [Python API](python-api.md)
- [How it works](how-it-works.md)
```

- [ ] **Step 2: Create docs/quick-start.md**

Required content:

```markdown
# Quick start

Get from zero to a committed agent run in under five minutes.

---

## Install

```bash
pip install eden-agent
```

Eden requires Python 3.11+.

## Run the simulated agent (no external CLI needed)

The `simulated_agent` echoes a fixed transcript so you can verify the orchestrator works without installing a real agent CLI.

Save as `eden_smoke.py`:

```python
from pathlib import Path

from eden import run, simulated_agent

result = run(
    cwd=Path.cwd(),
    sandbox="no_sandbox",
    agent=simulated_agent(
        transcript=["hello from the simulated agent"],
        completion_signal="done",
    ),
    prompt="ignored by the simulated agent",
    iterations=1,
)

print(f"branch: {result.branch}")
print(f"iterations: {len(result.iterations)}")
print(f"final commit: {result.iterations[-1].commit.sha if result.iterations[-1].commit else 'none'}")
```

Run it:

```bash
python eden_smoke.py
```

You should see a new branch (e.g., `eden/run-<timestamp>`) with one commit.

## Scaffold a real project

```bash
eden init --sandbox docker --agent claude-code --yes
```

This writes `.eden/Dockerfile`, `.eden/prompt.md`, `.eden/main.py`, `.eden/.env.example`, and `.eden/.gitignore`. Edit `prompt.md` for your task, then:

```bash
python .eden/main.py
```

Make sure your agent CLI (`claude`, `codex`, `opencode`, `pi`) is installed and authenticated first.

## Where to go next

- [Python API](python-api.md) — full reference for `run(...)` and friends.
- [Sandbox providers](sandbox-providers.md) — pick the right sandbox for your workload.
- [Agents](agents.md) — choose between `claude_code`, `codex`, `opencode`, `pi`.
- [Prompts](prompts.md) — beyond a literal string: shell blocks, args, file sources.
```

- [ ] **Step 3: Verify the simulated-agent example matches the real API surface**

Cross-check the snippet against `eden/orchestrator/__init__.py` — confirm `run` accepts `cwd`, `sandbox`, `agent`, `prompt`, `iterations` keyword arguments, and that `simulated_agent` accepts `transcript` and `completion_signal`. Confirm `RunResult` has `.branch` and `.iterations`, and `Iteration` has `.commit` (with `.sha`). If any mismatch, update the snippet to reflect the actual signatures before committing.

- [ ] **Step 4: Commit**

```bash
git add docs/what-is-eden.md docs/quick-start.md
git commit -m "docs: add what-is-eden and quick-start guides"
```

---

## Task 4: docs/how-it-works.md + docs/prompts.md

**Files:**
- Create: `docs/how-it-works.md`
- Create: `docs/prompts.md`

- [ ] **Step 1: Create docs/how-it-works.md**

Required structure and content:

```markdown
# How Eden works

Eden's run loop has four phases: worktree setup, sandbox creation, agent iteration, and finalize.

---

## Worktree setup

`create_worktree()` (called internally by `run()`) creates a fresh git worktree under your repo's `.git/worktrees/` directory on a new branch. Three branch strategies are available — see `BranchStrategy` in [python-api.md](python-api.md).

Read source: `eden/worktree/_create.py`. Document the worktree lock (`_lock.py`) — explain why concurrent runs need it.

## Sandbox creation

The worktree path is handed to a `SandboxProvider`, which creates an environment where the agent runs.

- **Bind-mount providers** (`no_sandbox`, `docker`, `podman`) — the worktree path is mounted directly into the sandbox. Reads and writes happen in-place.
- **Patch-sync providers** (`isolated`) — files are copied into the sandbox. After the agent runs, `finalize()` returns a diff that's applied back to the host worktree.
- **Cloud providers** (`daytona`, `vercel`) — files are uploaded via REST. After the agent runs, `finalize()` downloads the diff.

See [sandbox-providers.md](sandbox-providers.md) for the full provider matrix.

## Agent iteration

For each iteration (default 1):

1. The orchestrator renders the prompt (see [prompts.md](prompts.md)).
2. It invokes `agent.build_command(ctx)` to get the argv.
3. It spawns the agent process inside the sandbox via `provider.exec(...)`.
4. It streams stdout line-by-line, calling `agent.parse_stream(line)` for each.
5. Yielded `StreamEvent`s drive logging, idle detection, completion-signal matching, and tool-call accounting.
6. When the agent exits (or hits idle/abort/timeout), the orchestrator commits any changes on the worktree branch.

## Finalize

For non-bind-mount providers, `finalize()` runs after the last iteration. It returns a `FinalizeResult` whose patch is applied to the host worktree. Bind-mount providers skip this — their changes are already on disk.

## Lifecycle hooks

Hooks fire at five phases: `pre_setup`, `post_setup`, `pre_iteration`, `post_iteration`, `post_run`. Hooks come in two flavors:

- **Host hooks** (`HostHooks`) run on your machine.
- **Sandbox hooks** (`SandboxHooks`) run inside the sandbox via `provider.exec(...)`.

See [python-api.md](python-api.md#lifecycle-hooks) for the type reference.

## Iteration loop diagram

```
run()
 ├── create_worktree()           ← new branch, fresh tree
 ├── HostHooks.pre_setup
 ├── create_sandbox()
 │    └── SandboxHooks.pre_setup
 ├── HostHooks.post_setup
 │    └── SandboxHooks.post_setup
 ├── for each iteration:
 │    ├── HostHooks.pre_iteration
 │    ├── render prompt
 │    ├── agent.build_command(ctx)
 │    ├── provider.exec(argv)    ← stream stdout → StreamEvents
 │    ├── commit changes
 │    └── HostHooks.post_iteration
 ├── provider.finalize()         ← patch back if not bind-mount
 ├── HostHooks.post_run
 └── return RunResult
```
```

- [ ] **Step 2: Create docs/prompts.md**

Required content:

```markdown
# Prompts

Eden's `run()` accepts either a literal string or a structured `PromptSource` that's rendered before each iteration.

---

## Literal string

```python
run(..., prompt="Refactor the cache module to use LRU eviction.")
```

The string is passed as-is. Best for one-shot tasks with no dynamic content.

## File source

Read the prompt from a file. Re-rendered before every iteration, so editing the file between iterations updates the prompt.

```python
from pathlib import Path
run(..., prompt=Path(".eden/prompt.md"))
```

## Args

Substitute `{name}` placeholders in the prompt:

```python
run(
    ...,
    prompt="Add tests for {module}.",
    prompt_args={"module": "auth"},
)
```

Read source: `eden/prompt/_render.py`. Document escaping rules: `{{` and `}}` are literal braces.

## Shell blocks

Inline shell command output:

```python
prompt = "Current branch: $(git rev-parse --abbrev-ref HEAD). Fix the failing tests."
```

Shell blocks (`$(...)`) execute on the host before the prompt is sent to the agent. Read source: `eden/prompt/_shell.py`. Document timeout behavior.

## Built-ins

Eden provides built-in placeholders for common values:

- `{eden.branch}` — current run's branch name.
- `{eden.iteration}` — 1-indexed iteration counter.
- `{eden.cwd}` — repo root.

Read source: `eden/prompt/_render.py`.

## Composition

You can mix all four forms. Example: a file source whose body contains `{module}` placeholders and `$(...)` shell blocks.
```

- [ ] **Step 3: Commit**

```bash
git add docs/how-it-works.md docs/prompts.md
git commit -m "docs: add how-it-works and prompts references"
```

---

## Task 5: docs/cli.md + docs/templates.md + docs/configuration.md

**Files:**
- Create: `docs/cli.md`
- Create: `docs/templates.md`
- Create: `docs/configuration.md`

- [ ] **Step 1: Create docs/cli.md**

```markdown
# CLI

Eden ships a small CLI primarily for project scaffolding. The orchestrator itself is invoked from Python.

---

## `eden init`

Scaffold a new `.eden/` directory in the current working directory.

```bash
eden init --sandbox docker --agent claude-code --yes
```

### Flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `--sandbox` | yes (or interactive) | — | One of `docker`, `podman`. |
| `--agent` | yes (or interactive) | — | One of `claude-code`, `codex`, `opencode`, `pi`. |
| `--model` | no | per-agent default | Model identifier passed to the agent factory. |
| `--template` | no | `blank` | Template to scaffold. v0.1 ships `blank` only. |
| `--image-name` | no | `eden:<cwd-basename-lowercase>` | Container image name (used by `docker`/`podman` builds). |
| `--yes` | no | false | Skip interactive prompts; use defaults for any missing flag. |

### Files written

- `.eden/Dockerfile` — minimal Dockerfile for the chosen sandbox.
- `.eden/prompt.md` — prompt body (edit this).
- `.eden/main.py` — entry-point invoking `eden.run(...)`.
- `.eden/.env.example` — template for environment variables.
- `.eden/.gitignore` — excludes `.env`.

`eden init` refuses to overwrite an existing `.eden/` directory.

## `eden version`

Print the installed Eden version.

```bash
eden version
```
```

- [ ] **Step 2: Create docs/templates.md**

```markdown
# Templates

`eden init` scaffolds a project from a template. v0.1 ships one template; more land in v0.2+.

---

## `blank`

Minimal scaffold with just the moving parts wired up. Edit `.eden/prompt.md`, then `python .eden/main.py`.

### File contents

The exact rendered files depend on `--sandbox`, `--agent`, `--model`, and `--image-name`. See `eden/cli/_templates/blank.py` for the literal template strings.

### Customizing

`.eden/main.py` is a plain Python file. Edit it to add hooks, change iteration count, swap providers, or wrap `eden.run(...)` in your own logic.
```

- [ ] **Step 3: Create docs/configuration.md**

```markdown
# Configuration

Eden reads configuration from three places: function arguments to `run()`, environment variables, and the optional `Logging` / `Timeouts` dataclasses.

---

## Environment variables

| Variable | Effect |
|---|---|
| `EDEN_AGENT_EXEC_MODE` | Set to `simulated` to force the agent into simulated mode regardless of the factory used. Useful for orchestrator-level tests. |
| `EDEN_DAYTONA_API_KEY` | API key for the Daytona cloud provider. |
| `EDEN_DAYTONA_API_URL` | Override the Daytona API endpoint (defaults to the public API). |
| `VERCEL_TOKEN` | API token for the Vercel sandbox provider. |

Read source: `eden/sandboxes/daytona/__init__.py`, `eden/sandboxes/vercel/__init__.py`.

## `Timeouts`

Frozen dataclass passed to `run(timeouts=...)`. See [python-api.md](python-api.md#configuration-types) for fields. Defaults are sane for most workloads — override only when you have a specific reason.

## `Logging`

Frozen dataclass passed to `run(logging=...)` controlling stream-event logging. Fields:

- `path` — file path to write logs to. `None` disables.
- `level` — `"info"` (default) or `"debug"`.

When `path` is set, every `StreamEvent` is written to the file as a JSON line.

## Sandbox-specific configuration

Each sandbox provider accepts its own keyword arguments. See the provider section in [sandbox-providers.md](sandbox-providers.md).
```

- [ ] **Step 4: Commit**

```bash
git add docs/cli.md docs/templates.md docs/configuration.md
git commit -m "docs: add cli, templates, configuration references"
```

---

## Task 6: docs/sandbox-providers.md + docs/agents.md

**Files:**
- Create: `docs/sandbox-providers.md`
- Create: `docs/agents.md`

- [ ] **Step 1: Create docs/sandbox-providers.md**

```markdown
# Sandbox providers

Eden ships six providers covering local, isolated, and cloud sandboxes.

---

## Provider matrix

| Provider | Mounts host? | Network? | Side effects on host? | When to use |
|---|---|---|---|---|
| `no_sandbox` | yes (process cwd) | yes | yes | Trusted code, fastest iteration. |
| `docker` | yes (bind mount) | configurable | confined to mount | Untrusted code on Linux/macOS. |
| `podman` | yes (bind mount) | configurable | confined to mount | Same as `docker`, rootless. |
| `isolated` | no (copy + diff) | yes | none until `finalize()` | Strong isolation on a single host. |
| `daytona` | no (REST upload) | yes | none until `finalize()` | Burstable cloud capacity. |
| `vercel` | no (REST upload) | yes | none until `finalize()` | Vercel-managed sandboxes. |

## `no_sandbox`

```python
run(..., sandbox="no_sandbox")
```

Runs the agent in your real `cwd` with your real environment. Fastest, least safe.

## `docker`

```python
run(..., sandbox="docker", image="my-eden-image:latest")
```

Bind-mounts the worktree into a container built from your Dockerfile. Read source: `eden/sandboxes/docker/__init__.py`.

## `podman`

Same surface as `docker`, uses the `podman` binary. Read source: `eden/sandboxes/podman/__init__.py`.

## `isolated`

```python
run(..., sandbox="isolated")
```

Creates a temporary sandbox directory, copies the worktree in, runs the agent there, then `finalize()` returns a patch applied to the host worktree. Read source: `eden/sandboxes/isolated/__init__.py`.

## `daytona`

```python
run(..., sandbox="daytona", api_key=os.environ["EDEN_DAYTONA_API_KEY"])
```

Provisions a Daytona cloud sandbox via REST. Files are uploaded base64-encoded. Read source: `eden/sandboxes/daytona/__init__.py`. See [ADR 0001](adr/0001-finalizing-vs-direct-handles.md) for finalize semantics.

## `vercel`

```python
run(..., sandbox="vercel", token=os.environ["VERCEL_TOKEN"])
```

Provisions a Vercel sandbox via REST. Same finalize semantics as `daytona`. Read source: `eden/sandboxes/vercel/__init__.py`.

## See also

- [Custom providers](custom-providers.md) — implementing your own.
- [Python API: `Mount`, `BranchStrategy`](python-api.md#configuration-types) — provider-agnostic types.
```

- [ ] **Step 2: Create docs/agents.md**

```markdown
# Agents

An agent factory returns an object satisfying the `Agent` Protocol. Eden ships factories for every major coding-agent CLI plus a generic `cli_agent` for anything else.

---

## Factory matrix

| Factory | Backed by | Default model | Session capture | Notes |
|---|---|---|---|---|
| `simulated_agent` | none (in-process) | n/a | no | Echoes a fixed transcript. Use for testing the orchestrator. |
| `claude_code` | `claude` CLI | `claude-opus-4-7` | yes | Captures `~/.claude/projects/<slug>/<id>.jsonl`. |
| `codex` | `codex` CLI | `gpt-5` | no | OpenAI Codex CLI. |
| `opencode` | `opencode` CLI | `claude-opus-4` | no | sst/opencode. |
| `pi` | `pi` CLI | `pi-3.5` | no | Inflection's pi. |
| `cli_agent` | any | required arg | configurable | Generic line-streaming CLI shim. |

## `simulated_agent`

```python
from eden import simulated_agent
agent = simulated_agent(transcript=["line one", "line two"], completion_signal="done")
```

Read source: `eden/agents/simulated/__init__.py`. Use to verify orchestrator behavior without an installed agent CLI.

## `claude_code`

```python
from eden import claude_code
agent = claude_code(model="claude-opus-4-7")
```

Wraps the `claude` CLI. Captures session JSONL by default — `Iteration.session_id` and `Iteration.session_file_path` are populated on each iteration. Read source: `eden/agents/claude_code/__init__.py`.

## `codex` / `opencode` / `pi`

Thin wrappers over `cli_agent` with `binary=` and a default `model=`. Each accepts `model`, `env`, `extra_args`. Read source: `eden/agents/codex/__init__.py`, `opencode/__init__.py`, `pi/__init__.py`.

## `cli_agent`

```python
from eden import cli_agent
agent = cli_agent(
    name="my-tool",
    model="some-model",
    binary="my-tool",
    extra_args=("--quiet",),
)
```

Generic factory for any line-streaming CLI. Pass `build_argv` for custom argv composition; pass `parse_stream` for binary-specific structured-output parsing. Read source: `eden/agents/cli/__init__.py`.

## Authentication

Each agent reads its own credentials from environment variables, per its own documentation. Eden does not manage agent auth.
```

- [ ] **Step 3: Commit**

```bash
git add docs/sandbox-providers.md docs/agents.md
git commit -m "docs: add sandbox-providers and agents catalogs"
```

---

## Task 7: docs/custom-providers.md + docs/errors.md

**Files:**
- Create: `docs/custom-providers.md`
- Create: `docs/errors.md`

- [ ] **Step 1: Create docs/custom-providers.md**

```markdown
# Custom providers

Implement the `IsolatedSandboxHandle` Protocol to plug in your own sandbox.

---

## The Protocol

```python
from typing import Protocol, runtime_checkable
from eden import IsolatedSandboxHandle  # re-exported from eden.providers._protocols
```

Read the full Protocol from `eden/providers/_protocols.py`. Required methods:

- `exec(argv, *, env, cwd, stdout, stderr) -> ExecResult` — run a command in the sandbox.
- `finalize(target) -> FinalizeResult` — post-iteration sync to host.
- `cleanup() -> None` — release resources.

## Skeleton

```python
from dataclasses import dataclass
from pathlib import Path

from eden.providers._types import FinalizeResult


@dataclass
class MySandboxHandle:
    workspace: Path

    def exec(self, argv, *, env=None, cwd=None, stdout=None, stderr=None):
        # subprocess or REST or whatever — return ExecResult
        ...

    def finalize(self, target: Path) -> FinalizeResult:
        # produce a patch that, applied to `target`, mirrors the sandbox state
        ...

    def cleanup(self) -> None:
        ...
```

## Helpers

`eden/providers/_helpers.py` exposes:

- `make_bind_mount_provider(...)` — for bind-mount-style sandboxes.
- `make_isolated_provider(...)` — for patch-sync-style sandboxes.

Use these unless you need full control. Read source: `eden/providers/_helpers.py`.

## Plugging in

Pass your factory to `run(sandbox=my_factory)` instead of a string. The factory returns the handle; the orchestrator calls `exec`/`finalize`/`cleanup` for the lifetime of the run.

## Worked examples

- Bind-mount: `eden/sandboxes/docker/__init__.py`.
- Patch-sync local: `eden/sandboxes/isolated/__init__.py`.
- REST cloud: `eden/sandboxes/daytona/__init__.py`.

## Related

- [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md).
```

- [ ] **Step 2: Create docs/errors.md**

```markdown
# Errors

Every error Eden raises descends from `EdenError`. Catch the base class to handle anything; catch a specific subclass to handle one failure mode.

---

## Hierarchy

```
EdenError
├── ConfigError
├── CwdError
├── EdenTimeoutError
│   ├── IdleTimeout
│   └── StepTimeout
├── EnvMergeError
├── HookError
│   ├── HookFailed
│   └── HookTimeout
├── InvalidOptions
├── PromptError
├── RestError
│   ├── RestAuthError
│   ├── RestNotFoundError
│   └── RestRateLimited
└── SessionCaptureFailed
```

Read source: `eden/errors/__init__.py`.

## When each fires

| Error | Fires when |
|---|---|
| `EdenError` | Base; catch this to handle anything from Eden. |
| `ConfigError` | Invalid configuration passed to `run()` (e.g., unknown `sandbox=` string). |
| `CwdError` | The `cwd` argument is not inside a git repo, or is a worktree of one. |
| `EdenTimeoutError` | Base for all timeout-related failures. |
| `IdleTimeout` | Agent stopped emitting output for longer than the idle threshold. |
| `StepTimeout` | A single subprocess (hook, sandbox exec) exceeded its step timeout. |
| `EnvMergeError` | Conflicting environment variables across host + sandbox + hook layers. |
| `HookError` | Base for hook failures. |
| `HookFailed` | A hook exited non-zero. |
| `HookTimeout` | A hook exceeded its timeout. |
| `InvalidOptions` | Mutually exclusive or missing-required arguments to `run()`. |
| `PromptError` | Prompt rendering failed (missing arg substitution, shell-block error). |
| `RestError` | Base for cloud-provider REST failures. |
| `RestAuthError` | Invalid or missing API credentials. |
| `RestNotFoundError` | Resource not found (sandbox revoked, project missing). |
| `RestRateLimited` | Provider returned 429. Retryable. |
| `SessionCaptureFailed` | Claude Code session JSONL capture failed (permissions, IO). Non-fatal — orchestrator logs and continues. |

## Recovery patterns

Most errors are terminal — fix the cause and retry. Two are notably recoverable:

- `RestRateLimited` — retry with backoff.
- `SessionCaptureFailed` — already non-fatal; continue.

Hook timeouts can be raised by either misconfiguration or a genuine slow operation; bump the relevant timeout in `Timeouts(...)`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/custom-providers.md docs/errors.md
git commit -m "docs: add custom-providers and errors references"
```

---

## Task 8: docs/development.md

**Files:**
- Create: `docs/development.md`

- [ ] **Step 1: Create docs/development.md**

```markdown
# Development

Local setup, test markers, lint and type gates, and how to publish a release.

---

## Local setup

```bash
git clone https://github.com/dotbrains/eden.git
cd eden
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Repo layout

```
eden/
├── _types.py              # public dataclasses (RunResult, Iteration, Commit, Usage, Timeouts)
├── _version.py            # version string from importlib.metadata
├── abort/                 # AbortController, AbortSignal, Aborted
├── agents/                # one subpackage per agent factory
├── cli/                   # `eden init` + `eden version`
├── errors/                # error hierarchy
├── lifecycle/             # hook types + hook runner
├── logging/               # log routing
├── orchestrator/          # `run()` + `create_worktree()` + iteration loop
├── prompt/                # PromptSource, args, shell blocks, built-ins
├── providers/             # SandboxProvider Protocol + factory helpers
├── sandboxes/             # one subpackage per sandbox provider
├── session/               # session JSONL capture
├── streaming/             # StreamEvent + line buffer
└── worktree/              # git worktree create + lock
```

## Test markers

```bash
.venv/bin/pytest -m unit           # fast, no subprocess
.venv/bin/pytest -m e2e            # in-process orchestrator e2e
.venv/bin/pytest -m integration    # real Docker/Podman; Linux only in CI
.venv/bin/pytest -m "unit or e2e"  # what CI runs by default
```

## Quality gates

The CI workflow (`.github/workflows/ci.yml`) runs all of these:

```bash
.venv/bin/ruff format --check eden tests
.venv/bin/ruff check eden tests
.venv/bin/mypy --strict eden tests
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```

Coverage gate is 70%. Current actual is 90%+.

## Releasing a new version

1. Bump `pyproject.toml` `version` (semver).
2. Commit: `chore: bump version to vX.Y.Z`.
3. Push to `main`. CI must be green.
4. Tag from `main`:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. The `.github/workflows/release.yml` workflow runs automatically and publishes to PyPI via Trusted Publishing. No tokens needed.

### First-time setup of PyPI Trusted Publishing

Required once, before the first publish:

1. Visit https://pypi.org/manage/project/eden-agent/settings/publishing/ (project owner only).
2. Add a new pending publisher:
   - Owner: `dotbrains`
   - Repository: `eden`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. Save. The first tag push will succeed.

### Test releases

Tag with a `-rc` suffix (e.g., `v0.1.0-rc1`) to publish to TestPyPI instead of production PyPI. The workflow's branch logic routes rc tags to the test repository.

## Contributing

- Open an issue first for non-trivial changes.
- Follow conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`.
- All checks (ruff format, ruff check, mypy --strict, pytest) must pass before merge.
- New public exports must be documented in `docs/python-api.md` (enforced by `tests/unit/test_docs_consistency.py`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/development.md
git commit -m "docs: add development guide"
```

---

## Task 9: ADRs

**Files:**
- Create: `docs/adr/0001-finalizing-vs-direct-handles.md`
- Create: `docs/adr/0002-sync-first-public-api.md`
- Create: `docs/adr/0003-one-agent-per-file.md`

- [ ] **Step 1: Create ADR 0001**

```markdown
# ADR 0001 — Finalizing vs. direct handles

**Status:** Accepted (2026-05-02).

## Context

Sandbox providers fall into two shapes:

- **Bind-mount** — the worktree path is mounted into the sandbox; the agent reads and writes the host filesystem directly.
- **Detached** — the sandbox lives elsewhere (a separate directory, a remote VM). Files are copied in, the agent writes locally, then the diff has to come back.

For detached providers we needed a way to express "now sync your changes back to the host." Two options were considered:

1. **Streaming sync** — the sandbox handle exposes a file-watcher that mirrors writes back continuously.
2. **Post-iteration `finalize()`** — the handle exposes one method that, when called, returns a `FinalizeResult` containing a diff to apply.

## Decision

Adopt option 2. The Protocol is `IsolatedSandboxHandle.finalize(target) -> FinalizeResult`.

## Consequences

- Sandbox-side code stays simple — providers don't need a write watcher.
- Iteration semantics match between bind-mount and detached: every iteration ends with the host worktree at a known state.
- Per-iteration sync works (the orchestrator calls `finalize()` after each iteration); no streaming partial-write states are observable.
- The downside: detached sandboxes pay a sync cost at each iteration boundary. For typical agent runs (seconds to minutes per iteration) this is negligible.
```

- [ ] **Step 2: Create ADR 0002**

```markdown
# ADR 0002 — Sync-first public API

**Status:** Accepted (2026-05-02).

## Context

The original Eden was Rust + Tokio. The Python rewrite faced a choice: expose `async def run(...)` or `def run(...)`?

Arguments for async:
- Aligns with modern Python idioms.
- Composes with FastAPI / async tooling without an event-loop wrapper.

Arguments for sync:
- The dominant use case is "one host process orchestrates one agent run."
- Subprocess + threading already gives us concurrency primitives that compose with sync code.
- An async wrapper over a sync core is trivial; a sync wrapper over an async core requires either `asyncio.run()` (forbids re-entry) or `nest_asyncio` (fragile).

## Decision

Make the public API sync. Use `subprocess.Popen` + `threading.Event` + `Queue` internally. Provide no built-in async wrapper; users who need one can `asyncio.to_thread(eden.run, ...)`.

## Consequences

- Callers don't need an event loop running.
- Re-entrancy works inside Jupyter, REPLs, scripts, and Pytest without ceremony.
- Lifecycle hooks are sync callables — straightforward to author.
- Multi-agent parallelism is the user's responsibility (use `concurrent.futures.ThreadPoolExecutor` or `asyncio.to_thread`).
- A future async API can land additively without breaking the sync surface.
```

- [ ] **Step 3: Create ADR 0003**

```markdown
# ADR 0003 — One agent per file

**Status:** Accepted (2026-05-02).

## Context

Eden ships agent factories for `simulated_agent`, `claude_code`, `codex`, `opencode`, `pi`, plus the generic `cli_agent`. Two layouts were considered:

1. **Single registry file** — `eden/agents.py` containing all factories.
2. **One subpackage per agent** — `eden/agents/<name>/__init__.py`.

## Decision

Adopt option 2. Each agent lives in its own subpackage:

```
eden/agents/
├── __init__.py          # re-exports + Agent Protocol + IterationContext
├── cli/                 # generic cli_agent foundation
├── claude_code/         # claude-code-specific (session capture)
├── codex/               # 5-line wrapper over cli_agent
├── opencode/
├── pi/
└── simulated/
```

## Consequences

- Each agent file stays small (well under the project's ~300-LoC budget).
- Adding a new agent doesn't touch any existing agent file (no merge conflicts).
- Agent-specific test files mirror the layout: `tests/unit/test_<agent>_agent.py`.
- The `claude_code` agent owns its session-capture logic (`captures_sessions=True`); generic agents don't import it.
- The `__init__.py` re-exports give users a flat import surface: `from eden import claude_code, codex, opencode, pi, cli_agent, simulated_agent`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/adr/0001-finalizing-vs-direct-handles.md docs/adr/0002-sync-first-public-api.md docs/adr/0003-one-agent-per-file.md
git commit -m "docs: add ADRs 0001-0003"
```

---

## Task 10: README.md rewrite + pyproject.toml version bump

**Files:**
- Modify: `README.md` (full rewrite)
- Modify: `pyproject.toml` (version + classifier)

- [ ] **Step 1: Rewrite README.md**

Replace the entire contents of `README.md` with:

```markdown
# Eden

[![CI](https://github.com/dotbrains/eden/actions/workflows/ci.yml/badge.svg)](https://github.com/dotbrains/eden/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/eden-agent.svg)](https://pypi.org/project/eden-agent/)
[![Python](https://img.shields.io/pypi/pyversions/eden-agent.svg)](https://pypi.org/project/eden-agent/)
[![License](https://img.shields.io/badge/license-PolyForm%20Shield-blue)](LICENSE)

Python orchestrator for AI coding agents in sandboxed git worktrees.

Eden creates a fresh git worktree on a new branch, runs a coding agent (Claude Code, Codex, opencode, pi, or any line-streaming CLI) inside a sandbox (Docker, Podman, isolated, Daytona, or Vercel), captures its output, and commits the changes back. You get a branch with one clean commit per iteration, ready to review or merge.

## Install

```bash
pip install eden-agent
```

Requires Python 3.11+.

## Quick example

```python
from pathlib import Path

from eden import run, simulated_agent

result = run(
    cwd=Path.cwd(),
    sandbox="no_sandbox",
    agent=simulated_agent(
        transcript=["hello from the simulated agent"],
        completion_signal="done",
    ),
    prompt="ignored by the simulated agent",
    iterations=1,
)

print(f"branch: {result.branch}")
print(f"final commit: {result.iterations[-1].commit.sha if result.iterations[-1].commit else 'none'}")
```

For real agents, scaffold a project:

```bash
eden init --sandbox docker --agent claude-code --yes
python .eden/main.py
```

## Documentation

Full documentation lives in [`docs/`](docs/README.md):

- [What is Eden?](docs/what-is-eden.md)
- [Quick start](docs/quick-start.md)
- [Python API reference](docs/python-api.md)
- [How it works](docs/how-it-works.md)
- [Sandbox providers](docs/sandbox-providers.md)
- [Agents](docs/agents.md)

## License

[PolyForm Shield 1.0.0](LICENSE).
```

- [ ] **Step 2: Bump pyproject.toml version**

Run: `grep -n '^version\|Development Status' pyproject.toml`
Expected output: a line `version = "0.0.1"` and `"Development Status :: 3 - Alpha",`.

Edit `pyproject.toml`:

```diff
- version = "0.0.1"
+ version = "0.1.0"
```

```diff
-     "Development Status :: 3 - Alpha",
+     "Development Status :: 4 - Beta",
```

- [ ] **Step 3: Verify lint + types + tests still pass**

Run:
```bash
.venv/bin/ruff format --check eden tests && \
.venv/bin/ruff check --no-cache eden tests && \
.venv/bin/mypy --strict eden tests && \
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70 -q 2>&1 | tail -3
```
Expected: ruff clean, mypy clean, `451 passed` (450 from Phase 6 + 1 from Task 1).

- [ ] **Step 4: Commit**

```bash
git add README.md pyproject.toml
git commit -m "chore(release): bump version to 0.1.0 and rewrite README"
```

---

## Task 11: .github/workflows/release.yml

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the release workflow**

```yaml
name: release

on:
  push:
    tags: ['v*']

permissions:
  contents: read
  id-token: write

concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false

jobs:
  publish:
    name: build and publish to PyPI
    runs-on: ubuntu-latest
    environment:
      name: ${{ contains(github.ref, '-rc') && 'testpypi' || 'pypi' }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install build
        run: |
          python -m pip install --upgrade pip
          python -m pip install build

      - name: Build sdist + wheel
        run: python -m build

      - name: Publish to TestPyPI
        if: contains(github.ref, '-rc')
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/

      - name: Publish to PyPI
        if: ${{ !contains(github.ref, '-rc') }}
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo OK
```
Expected: `OK`.

- [ ] **Step 3: Run a local build to confirm the package builds**

Run:
```bash
.venv/bin/pip install --upgrade build && .venv/bin/python -m build 2>&1 | tail -10
```
Expected: `Successfully built eden_agent-0.1.0.tar.gz and eden_agent-0.1.0-py3-none-any.whl`.

- [ ] **Step 4: Inspect the wheel contents to confirm the docs and templates are present where expected**

Run:
```bash
.venv/bin/python -m zipfile -l dist/eden_agent-0.1.0-py3-none-any.whl | head -30
```
Expected: includes `eden/__init__.py`, `eden/cli/_templates/blank.py`, the per-agent subpackages.

- [ ] **Step 5: Clean up build artifacts**

Run:
```bash
rm -rf dist/ build/ *.egg-info eden_agent.egg-info
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add tag-triggered PyPI release workflow"
```

---

## Task 12: docs/README.md TOC consistency check + final verification

**Files:**
- Verify: every relative link in `docs/README.md` resolves to an existing file.

- [ ] **Step 1: Verify every TOC link resolves**

Run:
```bash
python <<'PY'
import re
import sys
from pathlib import Path

toc = Path("docs/README.md").read_text()
links = re.findall(r"\]\(([^)]+\.md)\)", toc)
broken = []
for link in links:
    target = (Path("docs") / link).resolve()
    if not target.exists():
        broken.append(link)
print("links checked:", len(links))
print("broken:", broken)
sys.exit(1 if broken else 0)
PY
```
Expected: `links checked: 17`, `broken: []`, exit 0.

- [ ] **Step 2: Verify every link in every doc resolves**

Run:
```bash
python <<'PY'
import re
import sys
from pathlib import Path

broken = []
for md in Path("docs").rglob("*.md"):
    if "superpowers" in md.parts:
        continue
    text = md.read_text()
    for match in re.finditer(r"\]\(([^):]+\.md(?:#[^)]+)?)\)", text):
        link = match.group(1).split("#")[0]
        target = (md.parent / link).resolve()
        if not target.exists():
            broken.append(f"{md}: {link}")
print("broken:", broken)
sys.exit(1 if broken else 0)
PY
```
Expected: `broken: []`, exit 0. Fix any reported broken links by adjusting the relative path (paths in subdirs like `docs/adr/` need `../` prefixes).

- [ ] **Step 3: Run the full quality gate**

Run:
```bash
.venv/bin/ruff format --check eden tests && \
.venv/bin/ruff check --no-cache eden tests && \
.venv/bin/mypy --strict eden tests && \
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70 -q 2>&1 | tail -5
```
Expected: All green; `451 passed`; coverage ≥70%.

- [ ] **Step 4: If any link fixes were made, commit**

```bash
git add docs/
git commit -m "docs: fix relative cross-links between docs"
```

(Skip if step 2 reported no broken links.)

---

## Task 13: Push, dry-run rc tag, then production tag

**Files:** none (git operations only).

This task is split because the rc tag and production tag are gated by the user — we tag rc first, verify TestPyPI publish worked, then tag production.

- [ ] **Step 1: Push all commits to origin/main**

Run: `git push origin main`
Expected: pushes ~12 commits.

- [ ] **Step 2: Tag and push the release-candidate**

Run:
```bash
git tag v0.1.0-rc1 -m "v0.1.0 release candidate 1" && git push origin v0.1.0-rc1
```
Expected: pushes the tag. The `release.yml` workflow triggers; check `gh run watch` or the Actions tab.

**Note for the executor:** This step assumes PyPI Trusted Publishing is configured for `eden-agent` on TestPyPI with `dotbrains/eden`, workflow `release.yml`, environment `testpypi`. If not configured, the publish step fails — configure per `docs/development.md` and re-run the workflow via the GH UI. **Pause here and confirm the user wants to proceed before running steps 3-4.**

- [ ] **Step 3: After confirming TestPyPI upload succeeded, tag production**

Run:
```bash
git tag v0.1.0 -m "v0.1.0" && git push origin v0.1.0
```
Expected: pushes the tag; production publish workflow starts.

- [ ] **Step 4: Tag the phase-7 milestone**

Run:
```bash
git tag phase-7 -m "phase 7 complete" && git push origin phase-7
```
Expected: pushes the milestone tag, matching the convention from `phase-1` through `phase-6`.

---

## Self-review notes

**Spec coverage check** (every spec section maps to a task):

- §1 (public surface) — frozen surface; documented across Task 1.
- §2.2 (file map) — every file in the map appears in a task: docs files in Tasks 1–9; `tests/unit/test_docs_consistency.py` in Task 1; `README.md` and `pyproject.toml` in Task 10; `.github/workflows/release.yml` in Task 11.
- §2.3 (boundaries) — enforced by the per-doc structure briefs.
- §3.1 (docs file shape) — every doc body in Tasks 1–9 follows `# Title` + TL;DR + `---`.
- §3.2 (`docs/README.md` TOC) — Task 2 (with verification in Task 12).
- §3.3 (`python-api.md` structure) — Task 1 step 3 maps each item.
- §3.4 (ADRs) — Task 9.
- §3.5 (release.yml) — Task 11.
- §3.6 (consistency test) — Task 1 (alongside `python-api.md`).
- §3.7 (README rewrite) — Task 10.
- §3.8 (pyproject changes) — Task 10.
- §4 (error handling) — release-workflow failure modes documented in `docs/development.md` (Task 8).
- §6.1 (unit test) — Task 1.
- §6.2 (manual review checklist) — Task 12.
- §6.3 (rc dry-run) — Task 13.

**Test count math:**
- Phase 6 baseline: 450 passing.
- Phase 7 adds 1 test (`test_docs_python_api_covers_all_public_exports`).
- Final: **451 passing.**

**Commit count:** ~12 commits (one per major task) plus the rc/production tags.

**Artifact count:**
- Docs: 14 user-facing files + 3 ADRs + 1 TOC = 18 markdown files.
- CI: 1 new workflow file.
- Tests: 1 new test file with 1 test.
- Modified: `README.md`, `pyproject.toml`.

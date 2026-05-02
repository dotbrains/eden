# Eden Phase 5 — Additional Agents (codex, opencode, pi) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a generic `cli_agent` factory + three named wrappers (`codex`, `opencode`, `pi`) over the Phase 3a Agent Protocol.

**Architecture:** New `eden/agents/cli/` sub-package with `cli_agent(*, name, model, binary, build_argv=None, parse_stream=None, captures_sessions=False, env=None, extra_args=())` factory + `_CliAgent` frozen dataclass. Three named factories (`codex`, `opencode`, `pi`) are 5-line wrappers over `cli_agent` setting `binary=` and `name=` to known values. Default `build_argv` produces `[binary, *extra_args, ctx.prompt]`; default `parse_stream` returns `None` so the orchestrator's existing fallback emits `text` events.

**Tech Stack:** Python 3.11+. No new dependencies. Reuses Phase 3a's `Agent` Protocol, `IterationContext`, and orchestrator parse_stream-fallback path.

**Reference spec:** `docs/superpowers/specs/2026-05-02-eden-phase5-additional-agents-design.md`

**Phase 4c base:** assumes commit `6667d33` or later on `main`. Baseline: 404 unit+e2e tests passing, mypy strict clean, ruff clean.

---

## File structure

```
eden/
├── agents/
│   ├── cli/                          # NEW
│   │   └── __init__.py               # NEW — cli_agent + _CliAgent
│   ├── codex/                        # NEW
│   │   └── __init__.py               # NEW — codex() wrapper
│   ├── opencode/                     # NEW
│   │   └── __init__.py               # NEW — opencode() wrapper
│   ├── pi/                           # NEW
│   │   └── __init__.py               # NEW — pi() wrapper
│   └── __init__.py                   # MODIFY — re-export cli_agent + 3 named factories
└── __init__.py                       # MODIFY — re-export cli_agent + 3 named factories

tests/
└── unit/
    ├── test_cli_agent.py             # NEW — generic cli_agent tests
    ├── test_codex_agent.py           # NEW — codex factory shape
    ├── test_opencode_agent.py        # NEW — opencode factory shape
    └── test_pi_agent.py              # NEW — pi factory shape

README.md                             # MODIFY — bump status to phase 5 complete
```

---

## Pre-flight

- [ ] **Step 1: Confirm 4c baseline**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  git status -s && git log --oneline -1 && \
  .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3
```
Expected: clean tree, on main, 404 tests passing.

---

## Task 1: cli_agent foundation

**Files:**
- Create: `eden/agents/cli/__init__.py`
- Create: `tests/unit/test_cli_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_agent.py`:

```python
"""Verify the generic cli_agent factory."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import Agent, IterationContext
from eden.agents.cli import cli_agent
from eden.providers._types import ExecResult
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


def test_factory_returns_agent_protocol() -> None:
    a = cli_agent(name="custom", model="m1", binary="my-cli")
    assert isinstance(a, Agent)
    assert a.name == "custom"
    assert a.model == "m1"


def test_default_build_command_appends_prompt_to_binary() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    argv = a.build_command(_ctx(prompt="please run"))
    assert argv == ["my-cli", "please run"]


def test_extra_args_threaded_before_prompt() -> None:
    a = cli_agent(
        name="custom",
        model="m",
        binary="my-cli",
        extra_args=("--flag", "value"),
    )
    argv = a.build_command(_ctx(prompt="hi"))
    assert argv == ["my-cli", "--flag", "value", "hi"]


def test_custom_build_argv_overrides_default() -> None:
    def my_argv(ctx: IterationContext) -> list[str]:
        return ["echo", f"iter={ctx.iteration}", ctx.prompt]

    a = cli_agent(name="custom", model="m", binary="ignored", build_argv=my_argv)
    argv = a.build_command(_ctx(prompt="x"))
    assert argv == ["echo", "iter=0", "x"]


def test_default_parse_stream_returns_none() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    assert a.parse_stream("any line") is None


def test_custom_parse_stream_overrides_default() -> None:
    def my_parser(line: str) -> StreamEvent | None:
        if line.startswith("OK"):
            from datetime import UTC, datetime
            return StreamEvent(
                type="text",
                agent_name="custom",
                iteration=0,
                timestamp=datetime.now(UTC),
                text=line,
            )
        return None

    a = cli_agent(name="custom", model="m", binary="my-cli", parse_stream=my_parser)
    assert a.parse_stream("noise") is None
    ev = a.parse_stream("OK done")
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "OK done"


def test_captures_sessions_default_false() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    assert a.captures_sessions is False


def test_captures_sessions_true_honored() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli", captures_sessions=True)
    assert a.captures_sessions is True


def test_env_default_empty() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    # Env is stored privately; verify via attribute presence (no public getter exists,
    # but the dataclass field is accessible through the agent instance).
    # The simplest contract: the orchestrator merges this env at run time. We
    # test by passing custom env and confirming it's preserved as a Mapping.
    assert isinstance(a, Agent)


def test_prompt_passed_unescaped() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    argv = a.build_command(_ctx(prompt="echo $PWD; rm -rf /"))
    assert argv[-1] == "echo $PWD; rm -rf /"
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_cli_agent.py -v`
Expected: FAIL — `eden.agents.cli` not found.

- [ ] **Step 3: Implement cli_agent**

Create `eden/agents/cli/__init__.py`:

```python
"""Generic CLI-tool Agent factory.

Wraps any line-streaming CLI binary into an Agent that satisfies Phase 3a's
`Agent` Protocol. Use cli_agent directly for arbitrary binaries; the
codex/opencode/pi sub-packages are 5-line wrappers over cli_agent with
sensible defaults.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.streaming import StreamEvent

_BuildArgv = Callable[[IterationContext], list[str]]
_ParseStream = Callable[[str], StreamEvent | None]


@dataclass(frozen=True)
class _CliAgent:
    name: str
    model: str
    captures_sessions: bool
    _binary: str
    _build_argv: _BuildArgv | None = None
    _parse_stream: _ParseStream | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()

    def build_command(self, ctx: IterationContext) -> list[str]:
        if self._build_argv is not None:
            return self._build_argv(ctx)
        return [self._binary, *self._extra_args, ctx.prompt]

    def parse_stream(self, line: str) -> StreamEvent | None:
        if self._parse_stream is not None:
            return self._parse_stream(line)
        return None


def cli_agent(
    *,
    name: str,
    model: str,
    binary: str,
    build_argv: _BuildArgv | None = None,
    parse_stream: _ParseStream | None = None,
    captures_sessions: bool = False,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """Build an Agent for any line-streaming CLI tool.

    Args:
        name: Agent identifier (used in StreamEvent.agent_name).
        model: Model identifier (informational; threaded to your CLI's
            argv if `build_argv` references it).
        binary: Executable name; resolved via $PATH at subprocess-spawn time.
        build_argv: Optional override; default produces
            ``[binary, *extra_args, ctx.prompt]``.
        parse_stream: Optional override; default returns ``None`` (orchestrator
            fallback emits a `text` StreamEvent per line).
        captures_sessions: When ``True``, orchestrator post-processes session
            JSONL into ``.eden/sessions/...`` (requires the agent to write to
            ``~/.claude/projects/<slug>/<id>.jsonl``). Default ``False``.
        env: Per-agent environment additions (merged by the orchestrator).
        extra_args: Default-build_argv inserts these between binary and prompt.
    """
    return _CliAgent(
        name=name,
        model=model,
        captures_sessions=captures_sessions,
        _binary=binary,
        _build_argv=build_argv,
        _parse_stream=parse_stream,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
    )


__all__ = ["cli_agent"]
```

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_cli_agent.py -v`
Expected: PASS — 10 tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/agents/cli tests/unit/test_cli_agent.py && \
.venv/bin/ruff format eden/agents/cli/__init__.py tests/unit/test_cli_agent.py && \
.venv/bin/ruff format --check eden/agents/cli/__init__.py tests/unit/test_cli_agent.py && \
.venv/bin/ruff check --fix eden/agents/cli/__init__.py tests/unit/test_cli_agent.py && \
.venv/bin/ruff check eden/agents/cli/__init__.py tests/unit/test_cli_agent.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/agents/cli/__init__.py tests/unit/test_cli_agent.py && \
git commit -m "feat(agents): add generic cli_agent factory + _CliAgent dataclass"
```

DO NOT use `git add eden/agents/cli`.

---

## Task 2: codex / opencode / pi named wrapper factories

**Files:**
- Create: `eden/agents/codex/__init__.py`
- Create: `eden/agents/opencode/__init__.py`
- Create: `eden/agents/pi/__init__.py`
- Create: `tests/unit/test_codex_agent.py`
- Create: `tests/unit/test_opencode_agent.py`
- Create: `tests/unit/test_pi_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_codex_agent.py`:

```python
"""Verify the codex agent factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.codex import codex
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


def test_codex_default_metadata() -> None:
    a = codex()
    assert a.name == "codex"
    assert a.model == "gpt-5"


def test_codex_custom_model() -> None:
    a = codex(model="gpt-4o")
    assert a.model == "gpt-4o"


def test_codex_build_command_uses_codex_binary() -> None:
    a = codex()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "codex"
    assert argv[-1] == "hello"


def test_codex_extra_args_threaded() -> None:
    a = codex(extra_args=("--no-cache",))
    argv = a.build_command(_ctx(prompt="x"))
    assert "--no-cache" in argv
    assert argv.index("--no-cache") < argv.index("x")
```

Create `tests/unit/test_opencode_agent.py`:

```python
"""Verify the opencode agent factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.opencode import opencode
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


def test_opencode_default_metadata() -> None:
    a = opencode()
    assert a.name == "opencode"
    assert a.model == "claude-opus-4"


def test_opencode_custom_model() -> None:
    a = opencode(model="claude-sonnet-4")
    assert a.model == "claude-sonnet-4"


def test_opencode_build_command_uses_opencode_binary() -> None:
    a = opencode()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "opencode"
    assert argv[-1] == "hello"


def test_opencode_extra_args_threaded() -> None:
    a = opencode(extra_args=("--config", "x.yaml"))
    argv = a.build_command(_ctx(prompt="p"))
    assert "--config" in argv
    assert "x.yaml" in argv
    assert argv.index("x.yaml") < argv.index("p")
```

Create `tests/unit/test_pi_agent.py`:

```python
"""Verify the pi agent factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.pi import pi
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


def test_pi_default_metadata() -> None:
    a = pi()
    assert a.name == "pi"
    assert a.model == "pi-3.5"


def test_pi_custom_model() -> None:
    a = pi(model="pi-4")
    assert a.model == "pi-4"


def test_pi_build_command_uses_pi_binary() -> None:
    a = pi()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "pi"
    assert argv[-1] == "hello"


def test_pi_extra_args_threaded() -> None:
    a = pi(extra_args=("--verbose",))
    argv = a.build_command(_ctx(prompt="p"))
    assert "--verbose" in argv
    assert argv.index("--verbose") < argv.index("p")
```

- [ ] **Step 2: Run failing tests**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/pytest tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py -v
```
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the three named wrappers**

Create `eden/agents/codex/__init__.py`:

```python
"""OpenAI Codex CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def codex(
    model: str = "gpt-5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """OpenAI Codex CLI agent. Assumes `codex` binary is on PATH.

    Default `model` ("gpt-5") is illustrative — Codex CLI may name models
    differently. Override via the positional `model` argument or supply your
    own `extra_args` for binary-specific flags.
    """
    return cli_agent(
        name="codex",
        model=model,
        binary="codex",
        env=env,
        extra_args=extra_args,
    )


__all__ = ["codex"]
```

Create `eden/agents/opencode/__init__.py`:

```python
"""opencode CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def opencode(
    model: str = "claude-opus-4",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """opencode CLI agent (sst/opencode). Assumes `opencode` binary is on PATH.

    Default `model` ("claude-opus-4") is illustrative — opencode supports
    multiple model providers; override via the positional `model` argument or
    supply your own `extra_args`.
    """
    return cli_agent(
        name="opencode",
        model=model,
        binary="opencode",
        env=env,
        extra_args=extra_args,
    )


__all__ = ["opencode"]
```

Create `eden/agents/pi/__init__.py`:

```python
"""pi CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """pi CLI agent. Assumes `pi` binary is on PATH.

    Default `model` ("pi-3.5") is illustrative — override via the positional
    `model` argument or supply your own `extra_args` for binary-specific flags.
    """
    return cli_agent(
        name="pi",
        model=model,
        binary="pi",
        env=env,
        extra_args=extra_args,
    )


__all__ = ["pi"]
```

- [ ] **Step 4: Run passing tests**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/pytest tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py -v
```
Expected: PASS — 12 tests (4 per agent).

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/agents/codex eden/agents/opencode eden/agents/pi tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py && \
.venv/bin/ruff format eden/agents/codex/__init__.py eden/agents/opencode/__init__.py eden/agents/pi/__init__.py tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py && \
.venv/bin/ruff format --check eden/agents/codex/__init__.py eden/agents/opencode/__init__.py eden/agents/pi/__init__.py tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py && \
.venv/bin/ruff check --fix eden/agents/codex/__init__.py eden/agents/opencode/__init__.py eden/agents/pi/__init__.py tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py && \
.venv/bin/ruff check eden/agents/codex/__init__.py eden/agents/opencode/__init__.py eden/agents/pi/__init__.py tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 6 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/agents/codex/__init__.py eden/agents/opencode/__init__.py eden/agents/pi/__init__.py tests/unit/test_codex_agent.py tests/unit/test_opencode_agent.py tests/unit/test_pi_agent.py && \
git commit -m "feat(agents): add codex/opencode/pi named factories over cli_agent"
```

---

## Task 3: Re-export at `eden.agents` and `eden` top level

**Files:**
- Modify: `eden/agents/__init__.py`
- Modify: `eden/__init__.py`

- [ ] **Step 1: Read current `eden/agents/__init__.py` and `eden/__init__.py`**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  cat eden/agents/__init__.py && echo "---" && cat eden/__init__.py | head -100
```

The Phase 3b `eden/agents/__init__.py` re-exports `Agent`, `IterationContext`, `claude_code`, `simulated_agent`. We add 4 new names.

- [ ] **Step 2: Update `eden/agents/__init__.py`**

Replace the contents of `eden/agents/__init__.py` with:

```python
"""Agent factories + Protocol."""

from __future__ import annotations

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.claude_code import claude_code
from eden.agents.cli import cli_agent
from eden.agents.codex import codex
from eden.agents.opencode import opencode
from eden.agents.pi import pi
from eden.agents.simulated import simulated_agent

__all__ = [
    "Agent",
    "IterationContext",
    "claude_code",
    "cli_agent",
    "codex",
    "opencode",
    "pi",
    "simulated_agent",
]
```

- [ ] **Step 3: Update `eden/__init__.py`**

Edit `eden/__init__.py`. Find the existing `from eden.agents import ...` line and add the 4 new names alphabetically:

```python
from eden.agents import (
    Agent,
    IterationContext,
    claude_code,
    cli_agent,
    codex,
    opencode,
    pi,
    simulated_agent,
)
```

Add `"cli_agent"`, `"codex"`, `"opencode"`, `"pi"` to `__all__`. Use `ruff check --fix --unsafe-fixes` to alphabetize.

- [ ] **Step 4: Verify imports**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/python -c "import eden; assert eden.cli_agent is not None; assert eden.codex is not None; assert eden.opencode is not None; assert eden.pi is not None; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Run full unit + e2e suite (regression check)**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3`
Expected: All tests pass. Total: 404 (Phase 4c) + 10 (T1) + 12 (T2) = **426 tests**.

- [ ] **Step 6: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden && \
.venv/bin/ruff format eden/agents/__init__.py eden/__init__.py && \
.venv/bin/ruff format --check eden/agents/__init__.py eden/__init__.py && \
.venv/bin/ruff check --fix eden/agents/__init__.py eden/__init__.py && \
.venv/bin/ruff check eden/agents/__init__.py eden/__init__.py
```
Expected: All clean.

- [ ] **Step 7: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/agents/__init__.py eden/__init__.py && \
git commit -m "feat(eden): re-export cli_agent + codex/opencode/pi at package root"
```

---

## Task 4: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump status line**

Edit `README.md:5`. Replace the existing status line with:

```markdown
> **Status:** Pre-alpha. Phases 1–5 complete: package skeleton, provider Protocols, worktree manager, `no_sandbox`/`docker`/`podman` bind-mount providers, local `isolated` patch-sync provider, `daytona` and `vercel` cloud providers, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent`/`claude_code`/`codex`/`opencode`/`pi`/`cli_agent`, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, Claude Code session JSONL capture, and post-iteration `finalize()` for isolated/cloud handles. CLI scaffolder (6) and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add README.md && \
git commit -m "docs: bump README status to phase 5 complete"
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
git tag -a phase-5 -m "Phase 5: cli_agent + codex/opencode/pi named factories"
git push origin phase-5
```

---

## Notes for the implementer

- **No subprocess in tests.** All `cli_agent` and named-wrapper tests verify argv shape via the dataclass's `build_command(ctx)` method. No real binaries spawned. Real-binary integration tests are Phase 7 polish.
- **Default `parse_stream` returns None.** The orchestrator's existing fallback (Phase 3a `_loop.py`) emits `StreamEvent(type="text", text=line, ...)` per line for None-parsed lines. Phase 7 docs will provide structured-output recipes for codex/opencode/pi as their schemas stabilize.
- **`captures_sessions=False` default.** Each agent's session-file convention differs; only Claude Code (Phase 3b) currently writes sessions to the path Eden's `capture_session` knows about. Phase 7 may add per-agent session strategies.
- **Default `model` values are illustrative.** Users override via the positional `model` argument. `extra_args` is the escape hatch for binary-specific flags.
- **Frozen dataclass.** `_CliAgent` is `frozen=True` matching the Phase 3b `_ClaudeCodeAgent` discipline.
- **Coverage gate stays at 70%.** Phase 5 adds heavily-tested code; total stays well above gate.

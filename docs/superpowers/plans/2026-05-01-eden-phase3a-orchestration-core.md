# Eden Phase 3a — Orchestration Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the orchestration substrate that connects Phase 2's worktree + sandbox foundations to a top-level public `eden.run(...)` driving a deterministic `simulated_agent`.

**Architecture:** Eight new sub-namespaces (`eden.agents`, `eden.prompt`, `eden.lifecycle`, `eden.orchestrator`, `eden.env`, `eden.logging`, `eden.streaming`, `eden.abort`) + a shared `eden/_types.py`. Imperative threading model (no `asyncio`): main thread + per-iteration agent stdout pump + per-iteration idle watchdog + per-phase sandbox-hook `ThreadPoolExecutor`. Public API ships full surface; only the agent (Claude) and session capture are deferred to Phase 3b.

**Tech Stack:** Python 3.11+, `subprocess`, `threading`, `concurrent.futures.ThreadPoolExecutor`, `re`, `pytest`. No new pip dependencies. CI matrix unchanged: 3 OS × 3 Python versions.

**Reference spec:** `docs/superpowers/specs/2026-05-01-eden-phase3a-orchestration-design.md`

**Phase 2 base:** This plan assumes Phase 2 is committed: `eden/{providers,worktree,sandboxes}/` exist with `BranchStrategy`, `SandboxProvider`, `SandboxHandle`, `WorktreeHandle`, `create_worktree`, `stream_exec`, `no_sandbox.provider()`, `docker.provider(...)`, `create_sandbox(...)`. CI is green on the 9-job matrix.

---

## File structure produced by this plan

```
eden/
├── __init__.py                    # MODIFY — re-export new public surface
├── _types.py                      # NEW — RunResult, Iteration, Usage, Commit, Timeouts
├── errors.py                      # MODIFY — add ConfigError/HookError/EdenTimeoutError/Aborted hierarchies
├── abort/
│   ├── __init__.py                # NEW — AbortController, AbortSignal, Aborted re-exports
│   └── _signal.py                 # NEW — threading.Event-backed signal
├── streaming/
│   ├── __init__.py                # NEW — StreamEvent, TextDeltaBuffer re-exports
│   ├── _event.py                  # NEW — StreamEvent dataclass
│   └── _buffer.py                 # NEW — TextDeltaBuffer
├── env/
│   ├── __init__.py                # NEW — merge_env re-export
│   └── _merge.py                  # NEW — collision-checking layer merge
├── logging/
│   ├── __init__.py                # NEW — Logging dataclass + factory
│   ├── _config.py                 # NEW — Logging frozen dataclass
│   ├── _format.py                 # NEW — log line formatter
│   ├── _redact.py                 # NEW — secret redactor
│   └── _file.py                   # NEW — file-sink writer
├── prompt/
│   ├── __init__.py                # NEW — render_prompt public helper
│   ├── _source.py                 # NEW — PromptSource resolution + xor validation
│   ├── _render.py                 # NEW — {{KEY}} substitution
│   └── _shell.py                  # NEW — !`cmd` shell-block expansion
├── lifecycle/
│   ├── __init__.py                # NEW — Hook/Hooks/HostHooks/SandboxHooks/HookPhase
│   ├── _types.py                  # NEW — frozen dataclasses + HookPhase enum
│   └── _runner.py                 # NEW — run_host_hooks, run_sandbox_hooks
├── agents/
│   ├── __init__.py                # NEW — simulated_agent + Agent + IterationContext
│   ├── _protocol.py               # NEW — Agent Protocol
│   ├── _context.py                # NEW — IterationContext dataclass
│   └── simulated.py               # NEW — simulated_agent factory
└── orchestrator/
    ├── __init__.py                # NEW — run + create_worktree
    ├── _setup.py                  # NEW — validate(), resolve_strategy(), open_log()
    ├── _completion.py             # NEW — completion-signal substring matcher
    ├── _idle.py                   # NEW — IdleWatchdog
    ├── _runner.py                 # NEW — _AgentRunner: subprocess + stdout pump
    ├── _loop.py                   # NEW — _run_loop driver
    └── _result.py                 # NEW — RunResult assembly

tests/
├── unit/
│   ├── test_errors_phase3a.py             # NEW — new exception subclasses
│   ├── test_result_types.py               # NEW — RunResult/Iteration/Usage/Commit/Timeouts
│   ├── test_abort_signal.py               # NEW
│   ├── test_streaming.py                  # NEW — StreamEvent + TextDeltaBuffer
│   ├── test_env_merge.py                  # NEW
│   ├── test_logging_redact.py             # NEW
│   ├── test_logging_format.py             # NEW
│   ├── test_logging_file.py               # NEW
│   ├── test_prompt_source.py              # NEW
│   ├── test_prompt_render.py              # NEW
│   ├── test_prompt_shell.py               # NEW
│   ├── test_lifecycle_runner.py           # NEW
│   ├── test_simulated_agent.py            # NEW
│   ├── test_completion.py                 # NEW
│   ├── test_idle_watchdog.py              # NEW
│   ├── test_agent_runner.py               # NEW
│   ├── test_orchestrator_setup.py         # NEW
│   └── test_run_loop.py                   # NEW — orchestrator-internal loop tests
└── e2e/
    ├── __init__.py                        # NEW
    ├── conftest.py                        # NEW — same tmp_git_repo fixture, e2e marker
    └── test_run_smoke.py                  # NEW — full simulated_agent + no_sandbox run
```

**File responsibilities:**

- `eden/_types.py` — `RunResult`, `Iteration`, `Usage`, `Commit`, `Timeouts`. Frozen dataclasses only. Imports: `pathlib`, `dataclasses`, `eden.streaming._event` (for `StreamEvent` reference in docs only — no runtime import), Phase 2 types.
- `eden/errors.py` — keeps `EdenError` base; adds `ConfigError`, `InvalidOptions`, `PromptError`, `EnvMergeError`, `CwdError`, `HookError`, `HookFailed`, `HookTimeout`, `EdenTimeoutError` (also subclasses `builtins.TimeoutError`), `IdleTimeout`, `StepTimeout`, `Aborted`.
- `eden/abort/_signal.py` — `AbortSignal` (read-only check), `AbortController` (writer), `Aborted` shim re-export. Backed by `threading.Event`.
- `eden/streaming/_event.py` — `StreamEvent` frozen dataclass. Two types in 3a: `"text"`, `"idle_warning"`.
- `eden/streaming/_buffer.py` — `TextDeltaBuffer` accumulates partial chunks into newline-delimited lines.
- `eden/env/_merge.py` — `merge_env(*layers)` raises `EnvMergeError` on differing-value collisions.
- `eden/logging/_config.py` — `Logging` frozen dataclass + `Logging.file(...)` factory.
- `eden/logging/_redact.py` — pure-text scanner replacing `sk-ant-…`, `ghp_…`, `xoxb-…`, `xoxp-…` and known env-var values.
- `eden/logging/_format.py` — line formatter `<iso-utc> <level> [<iter>] <type>: <body>`.
- `eden/logging/_file.py` — `FileLogSink.open(path)` / `.write(StreamEvent, level, iter)` / `.close()`. Atomic append, redaction applied here.
- `eden/prompt/_source.py` — `PromptSource` resolution: xor validation of `prompt`/`prompt_file`; reads file lazily; reserved-key validation on `prompt_args`.
- `eden/prompt/_render.py` — `{{KEY}}` substitution + auto-injected built-ins (`SOURCE_BRANCH`, `TARGET_BRANCH`).
- `eden/prompt/_shell.py` — `` !`cmd` `` regex expansion via `handle.exec(cmd)`. Sequential.
- `eden/lifecycle/_types.py` — `Hook`, `Hooks`, `HostHooks`, `SandboxHooks`, `HookPhase` enum.
- `eden/lifecycle/_runner.py` — `run_host_hooks(phase, hooks, *, worktree_path, env, timeouts)` runs `subprocess.run` sequentially. `run_sandbox_hooks(phase, hooks, *, handle, env, timeouts)` uses `ThreadPoolExecutor`.
- `eden/agents/_protocol.py` — `Agent` Protocol. Minimal in 3a: `name`, `model`, `build_command`, `parse_stream`.
- `eden/agents/_context.py` — `IterationContext` frozen dataclass.
- `eden/agents/simulated.py` — `simulated_agent(...)` factory. Returns an `Agent` whose `build_command` produces a Python subprocess argv printing the configured output.
- `eden/orchestrator/_setup.py` — kwarg validation pipeline (top-to-bottom from spec §2.5), strategy resolution.
- `eden/orchestrator/_completion.py` — `match(line, signal)` against `str | list[str]`.
- `eden/orchestrator/_idle.py` — `IdleWatchdog` with `record_activity()`, `iter_warnings_until_timeout(...)`, owned `threading.Event`.
- `eden/orchestrator/_runner.py` — `_AgentRunner` context manager: spawns subprocess, drains stdout via thread+queue, integrates idle watchdog and abort signal. Yields lines via `iter_lines(...)`.
- `eden/orchestrator/_loop.py` — `_run_loop(...)`: drives setup → worktree → sandbox → log → for-loop iterations → teardown.
- `eden/orchestrator/_result.py` — assembles `RunResult` from collected state.
- `eden/orchestrator/__init__.py` — public `run(...)` and `create_worktree(...)`.
- `eden/__init__.py` — top-level re-exports per spec §2.1.

**Test responsibilities:**

- `tests/unit/test_*` — `unit` marker; subprocess calls that need real binaries use `sys.executable`; everything else is in-process. Run on all 9 CI jobs.
- `tests/e2e/test_run_smoke.py` — `e2e` marker; full simulated_agent + no_sandbox + merge_to_head with idle warnings. No docker (deferred to 3b). Run on all 9 CI jobs.

---

## Pre-flight: register the `e2e` pytest marker

- [ ] **Step 1: Add `e2e` marker to pyproject.toml**

Modify `pyproject.toml` `[tool.pytest.ini_options]` markers list — add `"e2e: end-to-end smoke tests for the orchestrator"` after the existing `smoke:` line:

```toml
markers = [
    "unit: fast unit tests with no external services",
    "integration: tests that touch real Docker/Podman/cloud services",
    "smoke: end-to-end smoke tests",
    "e2e: end-to-end orchestrator runs with simulated_agent (no external services)",
]
```

- [ ] **Step 2: Create the e2e tests package**

```bash
mkdir -p tests/e2e
: > tests/e2e/__init__.py
```

- [ ] **Step 3: Verify markers parse**

Run: `pytest --collect-only --strict-markers -q | head -5`
Expected: collection completes with no `PytestUnknownMarkWarning`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/e2e/__init__.py
git commit -m "chore: register e2e pytest marker for phase 3a"
```

---

## Task 1: Extended exception hierarchy

**Files:**
- Modify: `eden/errors.py`
- Create: `tests/unit/test_errors_phase3a.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_errors_phase3a.py`:

```python
"""Verify Phase 3a additions to the exception hierarchy."""

from __future__ import annotations

import builtins

import pytest

from eden.errors import (
    Aborted,
    ConfigError,
    CwdError,
    EdenError,
    EdenTimeoutError,
    EnvMergeError,
    HookError,
    HookFailed,
    HookTimeout,
    IdleTimeout,
    InvalidOptions,
    PromptError,
    StepTimeout,
)

pytestmark = pytest.mark.unit


def test_config_error_inherits_eden_error() -> None:
    assert issubclass(ConfigError, EdenError)


def test_invalid_options_carries_code_message_hint() -> None:
    err = InvalidOptions(
        code="config.invalid_options",
        message="must supply prompt or prompt_file",
        hint="provide one",
    )
    assert err.code == "config.invalid_options"
    assert err.message == "must supply prompt or prompt_file"
    assert err.hint == "provide one"
    assert "config.invalid_options" in str(err)


def test_invalid_options_inherits_config_error() -> None:
    assert issubclass(InvalidOptions, ConfigError)


def test_prompt_error_inherits_config_error() -> None:
    assert issubclass(PromptError, ConfigError)


def test_prompt_error_carries_cause() -> None:
    cause = ValueError("inner")
    err = PromptError(code="prompt.file_missing", message="x", cause=cause)
    assert err.cause is cause


def test_env_merge_error_inherits_config_error() -> None:
    assert issubclass(EnvMergeError, ConfigError)


def test_cwd_error_inherits_config_error() -> None:
    assert issubclass(CwdError, ConfigError)


def test_hook_error_inherits_eden_error() -> None:
    assert issubclass(HookError, EdenError)


def test_hook_failed_inherits_hook_error() -> None:
    assert issubclass(HookFailed, HookError)


def test_hook_timeout_inherits_hook_error() -> None:
    assert issubclass(HookTimeout, HookError)


def test_eden_timeout_error_subclasses_builtin_timeout_error() -> None:
    assert issubclass(EdenTimeoutError, EdenError)
    assert issubclass(EdenTimeoutError, builtins.TimeoutError)


def test_idle_timeout_inherits_eden_timeout_error() -> None:
    assert issubclass(IdleTimeout, EdenTimeoutError)


def test_step_timeout_inherits_eden_timeout_error() -> None:
    assert issubclass(StepTimeout, EdenTimeoutError)


def test_aborted_inherits_eden_error() -> None:
    assert issubclass(Aborted, EdenError)


def test_aborted_carries_reason() -> None:
    err = Aborted(reason="user-cancel")
    assert err.reason == "user-cancel"
    assert "user-cancel" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_errors_phase3a.py -v`
Expected: FAIL — ImportError: cannot import name 'ConfigError' from 'eden.errors'.

- [ ] **Step 3: Implement extended errors**

Replace contents of `eden/errors.py`:

```python
"""Base + Phase 3a runtime errors for the eden package."""

from __future__ import annotations

import builtins


class EdenError(Exception):
    """Base for every error raised from the eden package."""


def _format(code: str, message: str, hint: str | None) -> str:
    base = f"[{code}] {message}"
    return f"{base}\nhint: {hint}" if hint else base


class ConfigError(EdenError):
    """Configuration / kwarg / environment problem detected before any side effect."""


class InvalidOptions(ConfigError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class PromptError(ConfigError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class EnvMergeError(ConfigError):
    def __init__(
        self,
        *,
        code: str = "config.env_merge",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class CwdError(ConfigError):
    def __init__(
        self,
        *,
        code: str = "config.cwd",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class HookError(EdenError):
    """Base for host- and sandbox-hook failures."""


class HookFailed(HookError):
    def __init__(
        self,
        *,
        code: str = "hook.failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class HookTimeout(HookError):
    def __init__(
        self,
        *,
        code: str = "hook.timeout",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class EdenTimeoutError(EdenError, builtins.TimeoutError):
    """Time-budget exceeded. Subclasses builtins.TimeoutError so callers can
    catch either or both."""


class IdleTimeout(EdenTimeoutError):
    def __init__(
        self,
        *,
        code: str = "timeout.idle",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class StepTimeout(EdenTimeoutError):
    def __init__(
        self,
        *,
        code: str = "timeout.step",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class Aborted(EdenError):
    def __init__(self, *, reason: str = "abort-signal") -> None:
        self.reason = reason
        super().__init__(f"aborted: {reason}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_errors_phase3a.py -v`
Expected: PASS, all 14 tests.

- [ ] **Step 5: Run full pre-existing suite**

Run: `pytest tests/unit/test_errors.py -v`
Expected: PASS (Phase 2 errors untouched).

- [ ] **Step 6: Run mypy**

Run: `mypy eden/errors.py tests/unit/test_errors_phase3a.py`
Expected: Success — no issues.

- [ ] **Step 7: Commit**

```bash
git add eden/errors.py tests/unit/test_errors_phase3a.py
git commit -m "feat(errors): add phase 3a exception hierarchy"
```

---

## Task 2: Shared result dataclasses (`eden/_types.py`)

**Files:**
- Create: `eden/_types.py`
- Create: `tests/unit/test_result_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_result_types.py`:

```python
"""Verify shared result dataclasses (RunResult, Iteration, Usage, Commit, Timeouts)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from eden._types import Commit, Iteration, RunResult, Timeouts, Usage

pytestmark = pytest.mark.unit


def test_iteration_is_frozen() -> None:
    it = Iteration(index=0, completion_signal=None, session_id=None,
                   session_file_path=None, usage=None)
    with pytest.raises(FrozenInstanceError):
        it.index = 1  # type: ignore[misc]


def test_usage_is_frozen() -> None:
    u = Usage(input_tokens=1, cache_creation_input_tokens=2,
              cache_read_input_tokens=3, output_tokens=4)
    with pytest.raises(FrozenInstanceError):
        u.input_tokens = 99  # type: ignore[misc]


def test_commit_carries_sha() -> None:
    c = Commit(sha="abc123")
    assert c.sha == "abc123"


def test_timeouts_defaults() -> None:
    t = Timeouts()
    assert t.hook_step == 60.0
    assert t.iteration_step is None


def test_run_result_defaults_for_3a_deferred_fields() -> None:
    rr = RunResult(
        iterations=[],
        completion_signal=None,
        branch="HEAD",
        stdout="",
        commits=[],
        worktree_path=Path("/tmp/x"),
        preserved_worktree_path=None,
        merged_to_target_branch=None,
        cwd=Path("/tmp/x"),
        prompt="",
        env={},
        log_file_path=None,
        session_id=None,
        session_file_path=None,
        usage=None,
    )
    assert rr.commits == []
    assert rr.merged_to_target_branch is None
    assert rr.session_id is None
    assert rr.usage is None


def test_run_result_is_frozen() -> None:
    rr = RunResult(
        iterations=[], completion_signal=None, branch="b", stdout="",
        commits=[], worktree_path=Path("/x"), preserved_worktree_path=None,
        merged_to_target_branch=None, cwd=Path("/x"), prompt="", env={},
        log_file_path=None, session_id=None, session_file_path=None, usage=None,
    )
    with pytest.raises(FrozenInstanceError):
        rr.branch = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_result_types.py -v`
Expected: FAIL — ImportError on `eden._types`.

- [ ] **Step 3: Implement the dataclasses**

Create `eden/_types.py`:

```python
"""Shared frozen dataclasses for eden's public result surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Commit:
    sha: str


@dataclass(frozen=True)
class Iteration:
    index: int
    completion_signal: str | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None


@dataclass(frozen=True)
class Timeouts:
    hook_step: float = 60.0
    iteration_step: float | None = None


@dataclass(frozen=True)
class RunResult:
    iterations: list[Iteration]
    completion_signal: str | None
    branch: str
    stdout: str
    commits: list[Commit]
    worktree_path: Path
    preserved_worktree_path: Path | None
    merged_to_target_branch: str | None
    cwd: Path
    prompt: str
    env: dict[str, str]
    log_file_path: Path | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_result_types.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict check**

Run: `mypy eden/_types.py tests/unit/test_result_types.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/_types.py tests/unit/test_result_types.py
git commit -m "feat(types): add RunResult/Iteration/Usage/Commit/Timeouts dataclasses"
```

---

## Task 3: Abort signal (`eden/abort/`)

**Files:**
- Create: `eden/abort/__init__.py`
- Create: `eden/abort/_signal.py`
- Create: `tests/unit/test_abort_signal.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_abort_signal.py`:

```python
"""Verify AbortController + AbortSignal."""

from __future__ import annotations

import threading

import pytest

from eden.abort import AbortController, AbortSignal
from eden.errors import Aborted

pytestmark = pytest.mark.unit


def test_signal_is_initially_clear() -> None:
    ctrl = AbortController()
    assert ctrl.signal.is_aborted() is False


def test_abort_sets_signal() -> None:
    ctrl = AbortController()
    ctrl.abort(reason="user")
    assert ctrl.signal.is_aborted() is True
    assert ctrl.signal.reason == "user"


def test_abort_is_idempotent() -> None:
    ctrl = AbortController()
    ctrl.abort(reason="first")
    ctrl.abort(reason="second")
    assert ctrl.signal.reason == "first"


def test_signal_raise_if_aborted_raises() -> None:
    ctrl = AbortController()
    ctrl.abort(reason="x")
    with pytest.raises(Aborted) as excinfo:
        ctrl.signal.raise_if_aborted()
    assert excinfo.value.reason == "x"


def test_signal_raise_if_aborted_noop_when_not_aborted() -> None:
    ctrl = AbortController()
    ctrl.signal.raise_if_aborted()


def test_signal_wait_returns_when_aborted() -> None:
    ctrl = AbortController()

    def trigger() -> None:
        ctrl.abort(reason="bg")

    t = threading.Thread(target=trigger)
    t.start()
    triggered = ctrl.signal.wait(timeout=2.0)
    t.join()
    assert triggered is True


def test_signal_wait_returns_false_on_timeout() -> None:
    ctrl = AbortController()
    triggered = ctrl.signal.wait(timeout=0.05)
    assert triggered is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_abort_signal.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the signal**

Create `eden/abort/_signal.py`:

```python
"""AbortSignal — threading.Event-backed cooperative cancellation."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from eden.errors import Aborted


@dataclass
class AbortSignal:
    """Read-only-ish view: callers can check / wait / raise, but cannot trigger."""

    _event: threading.Event = field(default_factory=threading.Event)
    _reason: list[str | None] = field(default_factory=lambda: [None])

    def is_aborted(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        return self._reason[0]

    def raise_if_aborted(self) -> None:
        if self._event.is_set():
            raise Aborted(reason=self._reason[0] or "abort-signal")

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)


@dataclass
class AbortController:
    """Writer side of an AbortSignal."""

    signal: AbortSignal = field(default_factory=AbortSignal)

    def abort(self, *, reason: str = "abort-signal") -> None:
        if not self.signal._event.is_set():
            self.signal._reason[0] = reason
            self.signal._event.set()
```

- [ ] **Step 4: Implement the package init**

Create `eden/abort/__init__.py`:

```python
"""Cooperative cancellation primitives."""

from __future__ import annotations

from eden.abort._signal import AbortController, AbortSignal
from eden.errors import Aborted

__all__ = ["AbortController", "AbortSignal", "Aborted"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_abort_signal.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict check**

Run: `mypy eden/abort tests/unit/test_abort_signal.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/abort tests/unit/test_abort_signal.py
git commit -m "feat(abort): add AbortController + AbortSignal"
```

---

## Task 4: Streaming (`eden/streaming/`)

**Files:**
- Create: `eden/streaming/__init__.py`
- Create: `eden/streaming/_event.py`
- Create: `eden/streaming/_buffer.py`
- Create: `tests/unit/test_streaming.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_streaming.py`:

```python
"""Verify StreamEvent dataclass + TextDeltaBuffer."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eden.streaming import StreamEvent, TextDeltaBuffer

pytestmark = pytest.mark.unit


def test_stream_event_text_kind() -> None:
    ev = StreamEvent(
        type="text",
        agent_name="simulated",
        iteration=0,
        timestamp=datetime(2026, 5, 1, tzinfo=timezone.utc),
        text="hello",
    )
    assert ev.type == "text"
    assert ev.text == "hello"
    assert ev.minutes_idle is None


def test_stream_event_idle_warning_kind() -> None:
    ev = StreamEvent(
        type="idle_warning",
        agent_name="simulated",
        iteration=0,
        timestamp=datetime(2026, 5, 1, tzinfo=timezone.utc),
        minutes_idle=2,
    )
    assert ev.minutes_idle == 2
    assert ev.text is None


def test_buffer_emits_complete_lines_only() -> None:
    buf = TextDeltaBuffer()
    assert buf.feed("hello") == []
    assert buf.feed(" world\nsec") == ["hello world"]
    assert buf.feed("ond\n") == ["second"]


def test_buffer_handles_multiple_lines_in_one_chunk() -> None:
    buf = TextDeltaBuffer()
    assert buf.feed("a\nb\nc\n") == ["a", "b", "c"]


def test_buffer_flush_returns_residual() -> None:
    buf = TextDeltaBuffer()
    buf.feed("residual")
    assert buf.flush() == "residual"
    assert buf.flush() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_streaming.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement StreamEvent**

Create `eden/streaming/_event.py`:

```python
"""StreamEvent: discriminated-union event emitted from the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class StreamEvent:
    """Phase 3a kinds: 'text', 'idle_warning'. Phase 3b adds 'tool_call'."""

    type: Literal["text", "idle_warning"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None
    minutes_idle: int | None = None
```

- [ ] **Step 4: Implement TextDeltaBuffer**

Create `eden/streaming/_buffer.py`:

```python
"""Accumulate partial chunks into newline-delimited lines."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextDeltaBuffer:
    _residual: str = ""
    _emitted: int = field(default=0, init=False, repr=False)

    def feed(self, chunk: str) -> list[str]:
        if not chunk:
            return []
        combined = self._residual + chunk
        if "\n" not in combined:
            self._residual = combined
            return []
        lines = combined.split("\n")
        self._residual = lines.pop()
        return lines

    def flush(self) -> str:
        out = self._residual
        self._residual = ""
        return out
```

- [ ] **Step 5: Implement package init**

Create `eden/streaming/__init__.py`:

```python
"""Stream events emitted by the orchestrator."""

from __future__ import annotations

from eden.streaming._buffer import TextDeltaBuffer
from eden.streaming._event import StreamEvent

__all__ = ["StreamEvent", "TextDeltaBuffer"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/unit/test_streaming.py -v`
Expected: PASS.

- [ ] **Step 7: mypy strict**

Run: `mypy eden/streaming tests/unit/test_streaming.py`
Expected: Success.

- [ ] **Step 8: Commit**

```bash
git add eden/streaming tests/unit/test_streaming.py
git commit -m "feat(streaming): add StreamEvent + TextDeltaBuffer"
```

---

## Task 5: Env merge (`eden/env/`)

**Files:**
- Create: `eden/env/__init__.py`
- Create: `eden/env/_merge.py`
- Create: `tests/unit/test_env_merge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_env_merge.py`:

```python
"""Verify env layer merge with collision detection."""

from __future__ import annotations

import pytest

from eden.env import merge_env
from eden.errors import EnvMergeError

pytestmark = pytest.mark.unit


def test_disjoint_keys_union() -> None:
    out = merge_env({"A": "1"}, {"B": "2"})
    assert out == {"A": "1", "B": "2"}


def test_same_key_same_value_idempotent() -> None:
    out = merge_env({"A": "1"}, {"A": "1"})
    assert out == {"A": "1"}


def test_same_key_different_value_raises() -> None:
    with pytest.raises(EnvMergeError) as excinfo:
        merge_env({"A": "1"}, {"A": "2"})
    assert excinfo.value.code == "config.env_merge"
    assert "A" in excinfo.value.message


def test_three_layers_disjoint() -> None:
    out = merge_env({"A": "1"}, {"B": "2"}, {"C": "3"})
    assert out == {"A": "1", "B": "2", "C": "3"}


def test_three_layers_collision_lists_layer_index() -> None:
    with pytest.raises(EnvMergeError) as excinfo:
        merge_env({"A": "1"}, {}, {"A": "9"})
    assert "A" in excinfo.value.message


def test_empty_layers() -> None:
    assert merge_env() == {}
    assert merge_env({}) == {}
    assert merge_env({}, {}) == {}


def test_no_layer_mutation() -> None:
    a = {"X": "1"}
    b = {"Y": "2"}
    merge_env(a, b)
    assert a == {"X": "1"}
    assert b == {"Y": "2"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_env_merge.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement merge_env**

Create `eden/env/_merge.py`:

```python
"""Layered env merge with collision detection."""

from __future__ import annotations

from collections.abc import Mapping

from eden.errors import EnvMergeError


def merge_env(*layers: Mapping[str, str]) -> dict[str, str]:
    """Merge layers left-to-right; collisions on differing values raise EnvMergeError.

    Same-key/same-value collisions are idempotent (no error). Disjoint keys union.
    """
    out: dict[str, str] = {}
    for layer in layers:
        for key, value in layer.items():
            if key in out and out[key] != value:
                raise EnvMergeError(
                    message=f"env key {key!r} set to conflicting values "
                    f"({out[key]!r} vs {value!r})",
                    hint=f"rename one of the {key!r} settings or set them equal",
                )
            out[key] = value
    return out
```

- [ ] **Step 4: Implement package init**

Create `eden/env/__init__.py`:

```python
"""Internal env merge helper used by the orchestrator."""

from __future__ import annotations

from eden.env._merge import merge_env

__all__ = ["merge_env"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_env_merge.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict**

Run: `mypy eden/env tests/unit/test_env_merge.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/env tests/unit/test_env_merge.py
git commit -m "feat(env): add merge_env with collision detection"
```

---

## Task 6: Logging — redaction (`eden/logging/_redact.py`)

**Files:**
- Create: `eden/logging/__init__.py` (placeholder, expanded later in tasks 7–8)
- Create: `eden/logging/_redact.py`
- Create: `tests/unit/test_logging_redact.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_logging_redact.py`:

```python
"""Verify secret redactor."""

from __future__ import annotations

import pytest

from eden.logging._redact import redact

pytestmark = pytest.mark.unit


def test_anthropic_key_redacted() -> None:
    out = redact("API key: sk-ant-abc123XYZ-DEF", env_values=())
    assert "sk-ant" not in out
    assert "<redacted>" in out


def test_github_pat_redacted() -> None:
    out = redact("token=ghp_AbCdEf012345", env_values=())
    assert "ghp_" not in out
    assert "<redacted>" in out


def test_slack_bot_token_redacted() -> None:
    out = redact("xoxb-123-456-abc", env_values=())
    assert "xoxb-" not in out
    assert "<redacted>" in out


def test_slack_user_token_redacted() -> None:
    out = redact("xoxp-secret-stuff", env_values=())
    assert "xoxp-" not in out


def test_env_value_redacted() -> None:
    out = redact("password=mySecret123", env_values=("mySecret123",))
    assert "mySecret123" not in out
    assert "<redacted>" in out


def test_multiple_matches_one_line() -> None:
    out = redact("sk-ant-AAA and ghp_BBB on same line", env_values=())
    assert "sk-ant" not in out
    assert "ghp_" not in out
    assert out.count("<redacted>") == 2


def test_no_match_returns_input() -> None:
    out = redact("nothing sensitive here", env_values=())
    assert out == "nothing sensitive here"


def test_empty_env_value_skipped() -> None:
    out = redact("hello", env_values=("",))
    assert out == "hello"


def test_short_env_value_skipped() -> None:
    """Don't redact 1-2 char values to avoid mangling normal text."""
    out = redact("ab cd ef", env_values=("a", "ab"))
    assert out == "ab cd ef"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logging_redact.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement redactor**

Create `eden/logging/_redact.py`:

```python
"""Secret redactor for log lines."""

from __future__ import annotations

import re
from collections.abc import Iterable

_REDACTED = "<redacted>"

_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xoxb-[A-Za-z0-9\-]+"),
    re.compile(r"xoxp-[A-Za-z0-9\-]+"),
)


def redact(text: str, *, env_values: Iterable[str]) -> str:
    """Replace known secret prefixes and supplied env-var values with <redacted>.

    Env values shorter than 3 chars are skipped to avoid mangling normal text.
    """
    out = text
    for pattern in _PREFIX_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    for value in env_values:
        if len(value) < 3:
            continue
        out = out.replace(value, _REDACTED)
    return out
```

- [ ] **Step 4: Stub the package init**

Create `eden/logging/__init__.py`:

```python
"""Logging surface — file sink + redaction. (Public re-exports added in task 8.)"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_logging_redact.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict**

Run: `mypy eden/logging/_redact.py tests/unit/test_logging_redact.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/logging/__init__.py eden/logging/_redact.py tests/unit/test_logging_redact.py
git commit -m "feat(logging): add secret redactor"
```

---

## Task 7: Logging — line formatter (`eden/logging/_format.py`)

**Files:**
- Create: `eden/logging/_format.py`
- Create: `tests/unit/test_logging_format.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_logging_format.py`:

```python
"""Verify log line formatter."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eden.logging._format import format_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, 12, 34, 56, tzinfo=timezone.utc)


def test_format_text_event() -> None:
    ev = StreamEvent(type="text", agent_name="sim", iteration=0,
                     timestamp=_ts(), text="hello world")
    line = format_line(ev, level="info")
    assert line.startswith("2026-05-01T12:34:56Z info [0] text:")
    assert line.endswith("hello world")


def test_format_idle_warning_event() -> None:
    ev = StreamEvent(type="idle_warning", agent_name="sim", iteration=2,
                     timestamp=_ts(), minutes_idle=4)
    line = format_line(ev, level="warn")
    assert "warn [2] idle_warning:" in line
    assert "minutes_idle=4" in line


def test_format_strips_trailing_newline_in_text() -> None:
    ev = StreamEvent(type="text", agent_name="sim", iteration=0,
                     timestamp=_ts(), text="line\n")
    line = format_line(ev, level="info")
    assert line.endswith("line")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logging_format.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement formatter**

Create `eden/logging/_format.py`:

```python
"""Format StreamEvents into newline-delimited log lines."""

from __future__ import annotations

from typing import Literal

from eden.streaming import StreamEvent


def format_line(
    event: StreamEvent,
    *,
    level: Literal["debug", "info", "warn", "error"],
) -> str:
    iso = event.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = f"{iso} {level} [{event.iteration}] {event.type}:"
    if event.type == "text":
        body = (event.text or "").rstrip("\n")
        return f"{prefix} {body}"
    return f"{prefix} minutes_idle={event.minutes_idle}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_logging_format.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/logging/_format.py tests/unit/test_logging_format.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/logging/_format.py tests/unit/test_logging_format.py
git commit -m "feat(logging): add line formatter"
```

---

## Task 8: Logging — Logging dataclass + file sink

**Files:**
- Create: `eden/logging/_config.py`
- Create: `eden/logging/_file.py`
- Modify: `eden/logging/__init__.py`
- Create: `tests/unit/test_logging_file.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_logging_file.py`:

```python
"""Verify Logging dataclass, default-path generation, and FileLogSink."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from eden.logging import Logging
from eden.logging._file import FileLogSink, default_log_path
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_logging_file_factory(tmp_path: Path) -> None:
    cfg = Logging.file(tmp_path / "out.log")
    assert cfg.type == "file"
    assert cfg.path == tmp_path / "out.log"
    assert cfg.level == "info"


def test_logging_file_factory_with_level(tmp_path: Path) -> None:
    cfg = Logging.file(tmp_path / "out.log", level="debug")
    assert cfg.level == "debug"


def test_default_log_path_sanitizes_branch(tmp_path: Path) -> None:
    p = default_log_path(host_repo_path=tmp_path, branch="eden/feat/x", now=_ts())
    assert p.parent == tmp_path / ".eden" / "logs"
    assert p.name.startswith("eden-feat-x-")
    assert p.name.endswith(".log")


def test_default_log_path_truncates(tmp_path: Path) -> None:
    long_branch = "x" * 200
    p = default_log_path(host_repo_path=tmp_path, branch=long_branch, now=_ts())
    # filename: <sanitized 64 chars>-<utc>.log
    stem = p.stem
    sanitized = stem.rsplit("-", 1)[0]
    assert len(sanitized) <= 64


def test_file_sink_writes_redacted_text(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=("mySecret",))
    try:
        ev = StreamEvent(type="text", agent_name="sim", iteration=0,
                         timestamp=_ts(), text="password=mySecret here")
        sink.write(ev)
    finally:
        sink.close()
    body = log_path.read_text()
    assert "mySecret" not in body
    assert "<redacted>" in body


def test_file_sink_writes_idle_warning(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    try:
        ev = StreamEvent(type="idle_warning", agent_name="sim", iteration=1,
                         timestamp=_ts(), minutes_idle=3)
        sink.write(ev)
    finally:
        sink.close()
    body = log_path.read_text()
    assert "idle_warning:" in body
    assert "minutes_idle=3" in body


def test_file_sink_appends_newlines(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    try:
        for i in range(3):
            sink.write(StreamEvent(type="text", agent_name="sim", iteration=i,
                                   timestamp=_ts(), text=f"line{i}"))
    finally:
        sink.close()
    lines = log_path.read_text().splitlines()
    assert len(lines) == 3


def test_file_sink_creates_parent_dirs(tmp_path: Path) -> None:
    log_path = tmp_path / "deep" / "nest" / "out.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    sink.close()
    assert log_path.exists()


def test_file_sink_close_is_idempotent(tmp_path: Path) -> None:
    sink = FileLogSink.open(tmp_path / "x.log", level="info", env_values=())
    sink.close()
    sink.close()  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logging_file.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement Logging dataclass**

Create `eden/logging/_config.py`:

```python
"""Logging configuration dataclass + factory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Logging:
    type: Literal["file"]
    path: Path
    level: Literal["debug", "info", "warn", "error"] = "info"

    @staticmethod
    def file(
        path: str | Path,
        level: Literal["debug", "info", "warn", "error"] = "info",
    ) -> Logging:
        return Logging(type="file", path=Path(path), level=level)
```

- [ ] **Step 4: Implement file sink + default path**

Create `eden/logging/_file.py`:

```python
"""File-sink writer + default log-path generator."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Literal

from eden.logging._format import format_line
from eden.logging._redact import redact
from eden.streaming import StreamEvent

_BRANCH_SANITIZE = re.compile(r"[/\\\s]+")
_BRANCH_MAX = 64


def default_log_path(
    *,
    host_repo_path: Path,
    branch: str,
    now: datetime | None = None,
) -> Path:
    """Compute .eden/logs/<sanitized-branch>-<utc>.log under host_repo_path."""
    safe = _BRANCH_SANITIZE.sub("-", branch).strip("-")
    if not safe:
        safe = "run"
    if len(safe) > _BRANCH_MAX:
        safe = safe[:_BRANCH_MAX]
    moment = now or datetime.now(timezone.utc)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    return host_repo_path / ".eden" / "logs" / f"{safe}-{stamp}.log"


class FileLogSink:
    """Append-mode plain-text log sink. Redaction applied on every write."""

    def __init__(
        self,
        *,
        path: Path,
        level: Literal["debug", "info", "warn", "error"],
        env_values: tuple[str, ...],
        fp: IO[str],
    ) -> None:
        self.path = path
        self.level = level
        self._env_values = env_values
        self._fp: IO[str] | None = fp

    @staticmethod
    def open(
        path: Path,
        *,
        level: Literal["debug", "info", "warn", "error"],
        env_values: Iterable[str],
    ) -> FileLogSink:
        path.parent.mkdir(parents=True, exist_ok=True)
        fp = path.open("a", encoding="utf-8")
        return FileLogSink(
            path=path,
            level=level,
            env_values=tuple(env_values),
            fp=fp,
        )

    def write(self, event: StreamEvent) -> None:
        if self._fp is None:
            return
        line = format_line(event, level=self.level)
        line = redact(line, env_values=self._env_values)
        self._fp.write(line + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp is None:
            return
        try:
            self._fp.flush()
            self._fp.close()
        finally:
            self._fp = None
```

- [ ] **Step 5: Update package init**

Replace contents of `eden/logging/__init__.py`:

```python
"""Logging surface — Logging dataclass + file sink."""

from __future__ import annotations

from eden.logging._config import Logging

__all__ = ["Logging"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/unit/test_logging_file.py -v`
Expected: PASS.

- [ ] **Step 7: mypy strict**

Run: `mypy eden/logging tests/unit/test_logging_file.py`
Expected: Success.

- [ ] **Step 8: Commit**

```bash
git add eden/logging tests/unit/test_logging_file.py
git commit -m "feat(logging): add Logging dataclass + FileLogSink"
```

---

## Task 9: Prompt — source resolution (`eden/prompt/_source.py`)

**Files:**
- Create: `eden/prompt/__init__.py` (placeholder)
- Create: `eden/prompt/_source.py`
- Create: `tests/unit/test_prompt_source.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_prompt_source.py`:

```python
"""Verify PromptSource resolution: xor + file read + reserved-key validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import InvalidOptions, PromptError
from eden.prompt._source import resolve_source

pytestmark = pytest.mark.unit


def test_inline_prompt_returns_text() -> None:
    text = resolve_source(prompt="hello", prompt_file=None, prompt_args=None)
    assert text == "hello"


def test_file_prompt_reads_file(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("from file", encoding="utf-8")
    text = resolve_source(prompt=None, prompt_file=f, prompt_args=None)
    assert text == "from file"


def test_neither_supplied_raises_invalid_options() -> None:
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(prompt=None, prompt_file=None, prompt_args=None)
    assert excinfo.value.code == "config.invalid_options"


def test_both_supplied_raises_invalid_options(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(prompt="x", prompt_file=f, prompt_args=None)
    assert excinfo.value.code == "config.invalid_options"


def test_prompt_args_with_inline_raises_invalid_options() -> None:
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(prompt="x", prompt_file=None, prompt_args={"K": "v"})
    assert "prompt_args" in excinfo.value.message


def test_prompt_args_reserved_keys_rejected(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(
            prompt=None, prompt_file=f,
            prompt_args={"SOURCE_BRANCH": "x"},
        )
    assert "SOURCE_BRANCH" in excinfo.value.message


def test_missing_file_raises_prompt_error(tmp_path: Path) -> None:
    f = tmp_path / "missing.md"
    with pytest.raises(PromptError) as excinfo:
        resolve_source(prompt=None, prompt_file=f, prompt_args=None)
    assert excinfo.value.code == "prompt.file_missing"


def test_path_str_accepted(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("ok", encoding="utf-8")
    text = resolve_source(prompt=None, prompt_file=str(f), prompt_args=None)
    assert text == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_prompt_source.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement source resolution**

Create `eden/prompt/_source.py`:

```python
"""Prompt source resolution: xor validation + file read + reserved-key check."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from eden.errors import InvalidOptions, PromptError

_RESERVED_KEYS = frozenset({"SOURCE_BRANCH", "TARGET_BRANCH"})


def resolve_source(
    *,
    prompt: str | None,
    prompt_file: str | Path | None,
    prompt_args: Mapping[str, str] | None,
) -> str:
    if prompt is None and prompt_file is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message="must supply exactly one of prompt or prompt_file",
            hint="pass prompt=... for inline text or prompt_file=... for a file path",
        )
    if prompt is not None and prompt_file is not None:
        raise InvalidOptions(
            code="config.invalid_options",
            message="prompt and prompt_file are mutually exclusive",
            hint="pass exactly one",
        )
    if prompt is not None and prompt_args:
        raise InvalidOptions(
            code="config.invalid_options",
            message="prompt_args requires prompt_file (no substitution on inline text)",
            hint="move the prompt to a file or drop prompt_args",
        )
    if prompt_args:
        bad = sorted(set(prompt_args) & _RESERVED_KEYS)
        if bad:
            raise InvalidOptions(
                code="config.invalid_options",
                message=f"prompt_args may not set reserved keys: {bad}",
                hint="reserved keys are auto-injected: SOURCE_BRANCH, TARGET_BRANCH",
            )

    if prompt is not None:
        return prompt

    assert prompt_file is not None
    path = Path(prompt_file)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptError(
            code="prompt.file_missing",
            message=f"prompt_file not found: {path}",
            hint="check the path",
            cause=exc,
        ) from exc
    except OSError as exc:
        raise PromptError(
            code="prompt.file_unreadable",
            message=f"could not read prompt_file {path}: {exc}",
            cause=exc,
        ) from exc
```

- [ ] **Step 4: Stub the package init**

Create `eden/prompt/__init__.py`:

```python
"""Prompt rendering pipeline. (Public re-exports added in task 11.)"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_prompt_source.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict**

Run: `mypy eden/prompt/_source.py tests/unit/test_prompt_source.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/prompt/__init__.py eden/prompt/_source.py tests/unit/test_prompt_source.py
git commit -m "feat(prompt): add source resolution with xor + reserved-key checks"
```

---

## Task 10: Prompt — `{{KEY}}` rendering (`eden/prompt/_render.py`)

**Files:**
- Create: `eden/prompt/_render.py`
- Create: `tests/unit/test_prompt_render.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_prompt_render.py`:

```python
"""Verify {{KEY}} substitution + auto-injected built-ins."""

from __future__ import annotations

import pytest

from eden.errors import PromptError
from eden.prompt._render import render

pytestmark = pytest.mark.unit


def test_substitutes_user_key() -> None:
    out = render("Hi {{NAME}}!", args={"NAME": "Ada"},
                 source_branch="b", target_branch="main")
    assert out == "Hi Ada!"


def test_substitutes_source_branch() -> None:
    out = render("on {{SOURCE_BRANCH}}", args={},
                 source_branch="feat/x", target_branch="main")
    assert out == "on feat/x"


def test_substitutes_target_branch() -> None:
    out = render("from {{TARGET_BRANCH}}", args={},
                 source_branch="b", target_branch="main")
    assert out == "from main"


def test_multiple_substitutions() -> None:
    out = render("{{A}}-{{B}}-{{A}}", args={"A": "1", "B": "2"},
                 source_branch="x", target_branch="y")
    assert out == "1-2-1"


def test_unknown_key_raises_prompt_error() -> None:
    with pytest.raises(PromptError) as excinfo:
        render("hello {{MISSING}}", args={"NAME": "Ada"},
               source_branch="b", target_branch="main")
    assert excinfo.value.code == "prompt.unknown_key"
    assert "MISSING" in excinfo.value.message
    assert excinfo.value.hint is not None
    assert "NAME" in excinfo.value.hint
    assert "SOURCE_BRANCH" in excinfo.value.hint


def test_no_braces_returns_input() -> None:
    out = render("plain text", args={}, source_branch="b", target_branch="main")
    assert out == "plain text"


def test_single_brace_left_alone() -> None:
    out = render("a { b } c", args={}, source_branch="b", target_branch="main")
    assert out == "a { b } c"


def test_built_ins_cannot_be_overridden_by_args() -> None:
    """Args were already validated to not contain reserved keys (task 9), but
    render must defensively prefer built-ins anyway."""
    out = render("{{SOURCE_BRANCH}}", args={"SOURCE_BRANCH": "evil"},
                 source_branch="real", target_branch="main")
    assert out == "real"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_prompt_render.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement render**

Create `eden/prompt/_render.py`:

```python
"""{{KEY}} substitution with auto-injected built-ins."""

from __future__ import annotations

import re
from collections.abc import Mapping

from eden.errors import PromptError

_KEY_RE = re.compile(r"\{\{(?P<key>[A-Za-z_][A-Za-z0-9_]*)\}\}")


def render(
    text: str,
    *,
    args: Mapping[str, str],
    source_branch: str,
    target_branch: str,
) -> str:
    """Substitute {{KEY}} placeholders. Built-ins win over args."""
    built_ins = {"SOURCE_BRANCH": source_branch, "TARGET_BRANCH": target_branch}
    table: dict[str, str] = {**dict(args), **built_ins}

    def _sub(match: re.Match[str]) -> str:
        key = match.group("key")
        if key not in table:
            known = ", ".join(sorted(table)) or "(none)"
            raise PromptError(
                code="prompt.unknown_key",
                message=f"unknown placeholder {{{{{key}}}}} in prompt",
                hint=f"known keys: {known}",
            )
        return table[key]

    return _KEY_RE.sub(_sub, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_prompt_render.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/prompt/_render.py tests/unit/test_prompt_render.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/prompt/_render.py tests/unit/test_prompt_render.py
git commit -m "feat(prompt): add {{KEY}} renderer with built-ins"
```

---

## Task 11: Prompt — `` !`cmd` `` shell-block expansion + public `render_prompt`

**Files:**
- Create: `eden/prompt/_shell.py`
- Modify: `eden/prompt/__init__.py`
- Create: `tests/unit/test_prompt_shell.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_prompt_shell.py`:

```python
"""Verify !`cmd` shell-block expansion + public render_prompt."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.errors import PromptError
from eden.prompt import render_prompt
from eden.prompt._shell import expand_shell_blocks
from eden.providers._types import ExecResult


class _FakeHandle:
    worktree_path = Path("/workspace")

    def __init__(self, results: dict[str, ExecResult]) -> None:
        self._results = results
        self.calls: list[str] = []

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        self.calls.append(cmd)
        return self._results[cmd]

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


pytestmark = pytest.mark.unit


def test_no_blocks_returns_input() -> None:
    h = _FakeHandle({})
    out = expand_shell_blocks("plain text", handle=h)
    assert out == "plain text"
    assert h.calls == []


def test_single_block_substituted() -> None:
    h = _FakeHandle({"git status -s": ExecResult(stdout="?? a.py\n", stderr="", exit_code=0)})
    out = expand_shell_blocks("status: !`git status -s`", handle=h)
    assert out == "status: ?? a.py"


def test_multiple_blocks_run_sequentially() -> None:
    h = _FakeHandle({
        "echo a": ExecResult(stdout="A\n", stderr="", exit_code=0),
        "echo b": ExecResult(stdout="B\n", stderr="", exit_code=0),
    })
    out = expand_shell_blocks("!`echo a`-!`echo b`", handle=h)
    assert out == "A-B"
    assert h.calls == ["echo a", "echo b"]


def test_failure_raises_prompt_error() -> None:
    h = _FakeHandle({"bad": ExecResult(stdout="", stderr="boom", exit_code=1)})
    with pytest.raises(PromptError) as excinfo:
        expand_shell_blocks("!`bad`", handle=h)
    assert excinfo.value.code == "prompt.shell_block_failed"
    assert "bad" in excinfo.value.message


def test_block_strips_trailing_newline_only() -> None:
    h = _FakeHandle({"x": ExecResult(stdout="line1\nline2\n", stderr="", exit_code=0)})
    out = expand_shell_blocks("!`x`", handle=h)
    assert out == "line1\nline2"


def test_render_prompt_full_pipeline(tmp_path: Path) -> None:
    """Public render_prompt: substitution + shell expansion in order."""
    h = _FakeHandle({"date": ExecResult(stdout="2026-05-01\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="branch={{SOURCE_BRANCH}} date=!`date`",
        args={},
        source_branch="feat/x",
        target_branch="main",
        handle=h,
    )
    assert out == "branch=feat/x date=2026-05-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_prompt_shell.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement shell expansion**

Create `eden/prompt/_shell.py`:

```python
"""!`cmd` shell-block expansion via the sandbox handle."""

from __future__ import annotations

import re

from eden.errors import PromptError
from eden.providers._protocols import SandboxHandle

_BLOCK_RE = re.compile(r"!`(?P<cmd>[^`]+)`")


def expand_shell_blocks(text: str, *, handle: SandboxHandle) -> str:
    """Run each !`cmd` via handle.exec and substitute its stdout (one trailing \\n stripped).

    Blocks run sequentially. Non-zero exit → PromptError(code="prompt.shell_block_failed").
    """
    pos = 0
    out: list[str] = []
    for match in _BLOCK_RE.finditer(text):
        out.append(text[pos:match.start()])
        cmd = match.group("cmd").strip()
        result = handle.exec(cmd)
        if result.exit_code != 0:
            raise PromptError(
                code="prompt.shell_block_failed",
                message=f"prompt shell block {cmd!r} exited {result.exit_code}",
                hint=result.stderr.strip() or None,
            )
        body = result.stdout
        if body.endswith("\n"):
            body = body[:-1]
        out.append(body)
        pos = match.end()
    out.append(text[pos:])
    return "".join(out)
```

- [ ] **Step 4: Replace package init with full surface**

Replace contents of `eden/prompt/__init__.py`:

```python
"""Prompt rendering pipeline: source → {{KEY}} substitution → !`cmd` expansion."""

from __future__ import annotations

from collections.abc import Mapping

from eden.prompt._render import render
from eden.prompt._shell import expand_shell_blocks
from eden.prompt._source import resolve_source
from eden.providers._protocols import SandboxHandle


def render_prompt(
    *,
    text: str,
    args: Mapping[str, str],
    source_branch: str,
    target_branch: str,
    handle: SandboxHandle,
) -> str:
    """Render `text` by substituting {{KEY}} then expanding !`cmd` blocks via `handle`."""
    substituted = render(
        text,
        args=args,
        source_branch=source_branch,
        target_branch=target_branch,
    )
    return expand_shell_blocks(substituted, handle=handle)


__all__ = ["render_prompt", "resolve_source"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_prompt_shell.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict**

Run: `mypy eden/prompt tests/unit/test_prompt_shell.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/prompt/_shell.py eden/prompt/__init__.py tests/unit/test_prompt_shell.py
git commit -m "feat(prompt): add !\`cmd\` expansion + public render_prompt"
```

---

## Task 12: Lifecycle — types (`eden/lifecycle/_types.py`)

**Files:**
- Create: `eden/lifecycle/__init__.py`
- Create: `eden/lifecycle/_types.py`

- [ ] **Step 1: Implement lifecycle types**

Create `eden/lifecycle/_types.py`:

```python
"""Lifecycle hook dataclasses + HookPhase enum."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class Hook:
    cmd: str
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    timeout: float | None = None


@dataclass(frozen=True)
class HostHooks:
    on_worktree_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()


@dataclass(frozen=True)
class SandboxHooks:
    on_sandbox_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()


@dataclass(frozen=True)
class Hooks:
    host: HostHooks = field(default_factory=HostHooks)
    sandbox: SandboxHooks = field(default_factory=SandboxHooks)


class HookPhase(Enum):
    OnWorktreeReady = "on_worktree_ready"
    OnSandboxReady = "on_sandbox_ready"
    OnIterationStart = "on_iteration_start"
    OnIterationEnd = "on_iteration_end"
    OnClose = "on_close"
```

- [ ] **Step 2: Implement package init**

Create `eden/lifecycle/__init__.py`:

```python
"""Lifecycle hooks: host (sequential) + sandbox (parallel) per HookPhase."""

from __future__ import annotations

from eden.lifecycle._types import Hook, HookPhase, Hooks, HostHooks, SandboxHooks

__all__ = ["Hook", "HookPhase", "Hooks", "HostHooks", "SandboxHooks"]
```

- [ ] **Step 3: Verify imports**

Run: `python -c "from eden.lifecycle import Hook, Hooks, HostHooks, SandboxHooks, HookPhase; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: mypy strict**

Run: `mypy eden/lifecycle`
Expected: Success.

- [ ] **Step 5: Commit**

```bash
git add eden/lifecycle/__init__.py eden/lifecycle/_types.py
git commit -m "feat(lifecycle): add Hook/Hooks/HostHooks/SandboxHooks/HookPhase"
```

---

## Task 13: Lifecycle — runner (host sequential, sandbox parallel)

**Files:**
- Create: `eden/lifecycle/_runner.py`
- Create: `tests/unit/test_lifecycle_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_lifecycle_runner.py`:

```python
"""Verify host-sequential and sandbox-parallel hook runners."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from eden._types import Timeouts
from eden.errors import HookFailed, HookTimeout
from eden.lifecycle import Hook, HookPhase, HostHooks, SandboxHooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


@dataclass
class _FakeHandle:
    worktree_path: Path
    seen: list[str]
    fails_for: tuple[str, ...] = ()
    sleep_per_call: float = 0.0
    _lock: threading.Lock = threading.Lock()

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        if self.sleep_per_call:
            time.sleep(self.sleep_per_call)
        with self._lock:
            self.seen.append(cmd)
        if cmd in self.fails_for:
            return ExecResult(stdout="", stderr=f"err:{cmd}", exit_code=1)
        return ExecResult(stdout=f"ok:{cmd}\n", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def test_host_hooks_run_sequentially_in_order(tmp_path: Path) -> None:
    hooks = HostHooks(on_worktree_ready=(
        Hook(cmd=f'"{sys.executable}" -c "print(1)"'),
        Hook(cmd=f'"{sys.executable}" -c "print(2)"'),
    ))
    run_host_hooks(
        phase=HookPhase.OnWorktreeReady,
        hooks=hooks,
        worktree_path=tmp_path,
        env={},
        timeouts=Timeouts(),
    )


def test_host_hook_failure_raises_hook_failed(tmp_path: Path) -> None:
    hooks = HostHooks(on_worktree_ready=(
        Hook(cmd=f'"{sys.executable}" -c "import sys; sys.exit(7)"'),
    ))
    with pytest.raises(HookFailed) as excinfo:
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks,
            worktree_path=tmp_path,
            env={},
            timeouts=Timeouts(),
        )
    assert "exit 7" in excinfo.value.message or "7" in excinfo.value.message


def test_host_hook_timeout_raises_hook_timeout(tmp_path: Path) -> None:
    hooks = HostHooks(on_worktree_ready=(
        Hook(
            cmd=f'"{sys.executable}" -c "import time; time.sleep(60)"',
            timeout=0.5,
        ),
    ))
    with pytest.raises(HookTimeout):
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks,
            worktree_path=tmp_path,
            env={},
            timeouts=Timeouts(hook_step=0.5),
        )


def test_sandbox_hooks_run_parallel(tmp_path: Path) -> None:
    seen: list[str] = []
    handle = _FakeHandle(worktree_path=tmp_path, seen=seen, sleep_per_call=0.2)
    hooks = SandboxHooks(on_sandbox_ready=(
        Hook(cmd="A"), Hook(cmd="B"), Hook(cmd="C"), Hook(cmd="D"),
    ))
    start = time.monotonic()
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=hooks,
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
    elapsed = time.monotonic() - start
    assert sorted(seen) == ["A", "B", "C", "D"]
    # Sequential would be ~0.8s; parallel should be far less.
    assert elapsed < 0.7


def test_sandbox_hook_failures_aggregated(tmp_path: Path) -> None:
    seen: list[str] = []
    handle = _FakeHandle(
        worktree_path=tmp_path,
        seen=seen,
        fails_for=("X", "Y"),
    )
    hooks = SandboxHooks(on_sandbox_ready=(
        Hook(cmd="ok"), Hook(cmd="X"), Hook(cmd="Y"),
    ))
    with pytest.raises(HookFailed) as excinfo:
        run_sandbox_hooks(
            phase=HookPhase.OnSandboxReady,
            hooks=hooks,
            handle=handle,
            env={},
            timeouts=Timeouts(),
        )
    assert "X" in excinfo.value.message
    assert "Y" in excinfo.value.message


def test_empty_hooks_noop(tmp_path: Path) -> None:
    run_host_hooks(
        phase=HookPhase.OnWorktreeReady,
        hooks=HostHooks(),
        worktree_path=tmp_path,
        env={},
        timeouts=Timeouts(),
    )
    handle = _FakeHandle(worktree_path=tmp_path, seen=[])
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=SandboxHooks(),
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_lifecycle_runner.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement lifecycle runner**

Create `eden/lifecycle/_runner.py`:

```python
"""Run host hooks (sequential) and sandbox hooks (parallel) for a phase."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eden._types import Timeouts
from eden.errors import HookFailed, HookTimeout
from eden.lifecycle._types import Hook, HookPhase, HostHooks, SandboxHooks
from eden.providers._protocols import SandboxHandle


def _phase_attr(phase: HookPhase) -> str:
    return phase.value


def run_host_hooks(
    *,
    phase: HookPhase,
    hooks: HostHooks,
    worktree_path: Path,
    env: Mapping[str, str],
    timeouts: Timeouts,
) -> None:
    attr = _phase_attr(phase)
    hook_list: tuple[Hook, ...] = getattr(hooks, attr, ())
    for hook in hook_list:
        deadline = hook.timeout if hook.timeout is not None else timeouts.hook_step
        merged: dict[str, str] = dict(os.environ)
        merged.update(env)
        if hook.env:
            merged.update(hook.env)
        try:
            proc = subprocess.run(
                hook.cmd,
                shell=True,
                cwd=str(hook.cwd) if hook.cwd is not None else str(worktree_path),
                env=merged,
                capture_output=True,
                text=True,
                timeout=deadline,
            )
        except subprocess.TimeoutExpired as exc:
            raise HookTimeout(
                message=f"host hook {hook.cmd!r} timed out after {deadline}s",
                hint="raise Hook.timeout or Timeouts.hook_step",
                cause=exc,
            ) from exc
        if proc.returncode != 0:
            raise HookFailed(
                message=(
                    f"host hook {hook.cmd!r} failed (exit {proc.returncode})\n"
                    f"{proc.stderr}"
                ),
            )


def run_sandbox_hooks(
    *,
    phase: HookPhase,
    hooks: SandboxHooks,
    handle: SandboxHandle,
    env: Mapping[str, str],
    timeouts: Timeouts,
) -> None:
    attr = _phase_attr(phase)
    hook_list: tuple[Hook, ...] = getattr(hooks, attr, ())
    if not hook_list:
        return

    def _run_one(hook: Hook) -> tuple[Hook, str | None]:
        merged: dict[str, str] = dict(env)
        if hook.env:
            merged.update(hook.env)
        deadline = hook.timeout if hook.timeout is not None else timeouts.hook_step
        try:
            result = handle.exec(
                hook.cmd,
                cwd=hook.cwd,
                env=merged,
                timeout=deadline,
            )
        except Exception as exc:  # ExecTimeout etc.
            return hook, f"{type(exc).__name__}: {exc}"
        if result.exit_code != 0:
            return hook, f"exit {result.exit_code}: {result.stderr.strip()}"
        return hook, None

    with ThreadPoolExecutor(max_workers=max(1, len(hook_list))) as pool:
        results = list(pool.map(_run_one, hook_list))

    failures = [(h, msg) for (h, msg) in results if msg is not None]
    if failures:
        lines = "\n".join(f"  - {h.cmd}: {msg}" for h, msg in failures)
        raise HookFailed(
            message=f"{len(failures)} sandbox hook(s) failed for phase {phase.value}:\n{lines}",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_lifecycle_runner.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/lifecycle tests/unit/test_lifecycle_runner.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/lifecycle/_runner.py tests/unit/test_lifecycle_runner.py
git commit -m "feat(lifecycle): add host (sequential) + sandbox (parallel) hook runners"
```

---

## Task 14: Agents — Protocol + IterationContext

**Files:**
- Create: `eden/agents/__init__.py` (placeholder)
- Create: `eden/agents/_protocol.py`
- Create: `eden/agents/_context.py`

- [ ] **Step 1: Implement IterationContext**

Create `eden/agents/_context.py`:

```python
"""IterationContext passed to Agent.build_command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eden.providers._protocols import SandboxHandle


@dataclass(frozen=True)
class IterationContext:
    iteration: int
    prompt: str
    sandbox_handle: SandboxHandle
    worktree_path: Path
    branch: str
    name: str | None
```

- [ ] **Step 2: Implement Agent Protocol**

Create `eden/agents/_protocol.py`:

```python
"""Agent Protocol — minimal in 3a (build_command + parse_stream)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from eden.agents._context import IterationContext
from eden.streaming import StreamEvent


@runtime_checkable
class Agent(Protocol):
    name: str
    model: str

    def build_command(self, ctx: IterationContext) -> list[str]: ...

    def parse_stream(self, line: str) -> StreamEvent | None: ...
```

- [ ] **Step 3: Stub the package init**

Create `eden/agents/__init__.py`:

```python
"""Agent factories. (simulated_agent re-exported in task 15.)"""

from __future__ import annotations

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent

__all__ = ["Agent", "IterationContext"]
```

- [ ] **Step 4: Verify imports**

Run: `python -c "from eden.agents import Agent, IterationContext; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/agents`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/agents
git commit -m "feat(agents): add Agent Protocol + IterationContext"
```

---

## Task 15: Agents — simulated_agent factory

**Files:**
- Create: `eden/agents/simulated.py`
- Modify: `eden/agents/__init__.py`
- Create: `tests/unit/test_simulated_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_simulated_agent.py`:

```python
"""Verify simulated_agent factory."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext, simulated_agent
from eden.providers._types import ExecResult


class _StubHandle:
    worktree_path = Path("/workspace")
    def exec(
        self, cmd: str, *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)
    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


pytestmark = pytest.mark.unit


def _ctx(iteration: int = 0, prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=iteration,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/tmp/x"),
        branch="HEAD",
        name=None,
    )


def test_default_metadata() -> None:
    a = simulated_agent()
    assert a.name == "simulated"
    assert a.model == "deterministic-1"


def test_custom_name_and_model() -> None:
    a = simulated_agent(name="fixture", model="v9")
    assert a.name == "fixture"
    assert a.model == "v9"


def test_build_command_argv_runs_and_emits_output() -> None:
    a = simulated_agent(output="hello\n<promise>COMPLETE</promise>\n")
    argv = a.build_command(_ctx())
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "hello" in proc.stdout
    assert "<promise>COMPLETE</promise>" in proc.stdout


def test_output_callable_per_iteration() -> None:
    def producer(ctx: IterationContext) -> str:
        return f"iter={ctx.iteration} prompt={ctx.prompt}\n"
    a = simulated_agent(output=producer)
    argv = a.build_command(_ctx(iteration=2, prompt="hi"))
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    assert "iter=2" in proc.stdout
    assert "prompt=hi" in proc.stdout


def test_output_list_emits_lines_in_order() -> None:
    a = simulated_agent(output=["line-A", "line-B", "<promise>COMPLETE</promise>"])
    argv = a.build_command(_ctx())
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    out_lines = [line for line in proc.stdout.splitlines() if line]
    assert out_lines == ["line-A", "line-B", "<promise>COMPLETE</promise>"]


def test_fail_with_raises_on_build_command() -> None:
    a = simulated_agent(fail_with=RuntimeError("nope"))
    with pytest.raises(RuntimeError, match="nope"):
        a.build_command(_ctx())


def test_parse_stream_returns_none_so_orchestrator_wraps_text() -> None:
    a = simulated_agent()
    assert a.parse_stream("any line") is None


def test_delay_per_line_drives_idle_paths() -> None:
    """delay_per_line ⇒ argv that prints with sleep between lines.

    We just check the argv carries a delay marker; the actual sleep is exercised
    in the orchestrator's idle-watchdog tests.
    """
    a = simulated_agent(output=["a", "b"], delay_per_line=0.05)
    argv = a.build_command(_ctx())
    joined = " ".join(argv)
    assert "0.05" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_simulated_agent.py -v`
Expected: FAIL — `simulated_agent` not exported.

- [ ] **Step 3: Implement simulated_agent**

Create `eden/agents/simulated.py`:

```python
"""Deterministic simulated_agent — drives orchestrator code paths in tests."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.streaming import StreamEvent


@dataclass
class _SimulatedAgent:
    name: str
    model: str
    _output: str | list[str] | Callable[[IterationContext], str]
    _delay_per_line: float
    _fail_with: Exception | None

    def build_command(self, ctx: IterationContext) -> list[str]:
        if self._fail_with is not None:
            raise self._fail_with
        if isinstance(self._output, str):
            text = self._output
        elif callable(self._output):
            text = self._output(ctx)
        else:
            text = "\n".join(self._output) + "\n"
        # Embed text and delay into a tiny Python program. JSON keeps quoting
        # safe across platforms.
        script = (
            "import sys, time, json\n"
            f"text = json.loads({json.dumps(json.dumps(text))})\n"
            f"delay = {self._delay_per_line!r}\n"
            "for line in text.split('\\n'):\n"
            "    if line == '' and not text.endswith('\\n'):\n"
            "        continue\n"
            "    sys.stdout.write(line + '\\n')\n"
            "    sys.stdout.flush()\n"
            "    if delay:\n"
            "        time.sleep(delay)\n"
        )
        return [sys.executable, "-u", "-c", script]

    def parse_stream(self, line: str) -> StreamEvent | None:
        return None


def simulated_agent(
    name: str = "simulated",
    model: str = "deterministic-1",
    *,
    output: str | list[str] | Callable[[IterationContext], str] = "<promise>COMPLETE</promise>\n",
    delay_per_line: float = 0.0,
    fail_with: Exception | None = None,
) -> Agent:
    """Build a deterministic Agent for orchestrator tests."""
    return _SimulatedAgent(
        name=name,
        model=model,
        _output=output,
        _delay_per_line=delay_per_line,
        _fail_with=fail_with,
    )
```

- [ ] **Step 4: Re-export simulated_agent**

Replace contents of `eden/agents/__init__.py`:

```python
"""Agent factories + Protocol."""

from __future__ import annotations

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.simulated import simulated_agent

__all__ = ["Agent", "IterationContext", "simulated_agent"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_simulated_agent.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict**

Run: `mypy eden/agents tests/unit/test_simulated_agent.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/agents/simulated.py eden/agents/__init__.py tests/unit/test_simulated_agent.py
git commit -m "feat(agents): add simulated_agent factory"
```

---

## Task 16: Orchestrator — completion-signal matcher

**Files:**
- Create: `eden/orchestrator/__init__.py` (placeholder)
- Create: `eden/orchestrator/_completion.py`
- Create: `tests/unit/test_completion.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_completion.py`:

```python
"""Verify completion-signal substring matcher."""

from __future__ import annotations

import pytest

from eden.orchestrator._completion import match

pytestmark = pytest.mark.unit


def test_string_signal_match_returns_signal() -> None:
    assert match("done <promise>COMPLETE</promise>", "<promise>COMPLETE</promise>") \
        == "<promise>COMPLETE</promise>"


def test_string_signal_no_match_returns_none() -> None:
    assert match("just some text", "<promise>COMPLETE</promise>") is None


def test_list_signal_first_match_wins() -> None:
    assert match("FOO line", ["FOO", "BAR"]) == "FOO"
    assert match("BAR line", ["FOO", "BAR"]) == "BAR"


def test_list_signal_no_match() -> None:
    assert match("nothing", ["FOO", "BAR"]) is None


def test_empty_list_returns_none() -> None:
    assert match("anything", []) is None


def test_empty_string_in_list_skipped() -> None:
    assert match("anything", ["", "X"]) is None


def test_substring_not_word_boundary() -> None:
    """Substring match — 'DONE' inside 'DONEX' counts."""
    assert match("DONEX", "DONE") == "DONE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_completion.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement matcher**

Create `eden/orchestrator/_completion.py`:

```python
"""Completion-signal substring matcher."""

from __future__ import annotations


def match(line: str, signal: str | list[str]) -> str | None:
    """Return the first matching signal substring, or None."""
    if isinstance(signal, str):
        return signal if signal in line else None
    for needle in signal:
        if needle and needle in line:
            return needle
    return None
```

- [ ] **Step 4: Stub package init**

Create `eden/orchestrator/__init__.py`:

```python
"""Orchestrator: run() + create_worktree(). (Public surface added in task 21.)"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_completion.py -v`
Expected: PASS.

- [ ] **Step 6: mypy strict**

Run: `mypy eden/orchestrator tests/unit/test_completion.py`
Expected: Success.

- [ ] **Step 7: Commit**

```bash
git add eden/orchestrator/__init__.py eden/orchestrator/_completion.py tests/unit/test_completion.py
git commit -m "feat(orchestrator): add completion-signal substring matcher"
```

---

## Task 17: Orchestrator — idle watchdog

**Files:**
- Create: `eden/orchestrator/_idle.py`
- Create: `tests/unit/test_idle_watchdog.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_idle_watchdog.py`:

```python
"""Verify IdleWatchdog timing behaviour."""

from __future__ import annotations

import time

import pytest

from eden.errors import IdleTimeout
from eden.orchestrator._idle import IdleWatchdog

pytestmark = pytest.mark.unit


def test_no_warning_when_activity_keeps_resetting() -> None:
    wd = IdleWatchdog(idle_timeout=0.5, idle_warning_interval=0.1)
    wd.start()
    try:
        for _ in range(8):
            time.sleep(0.05)
            wd.record_activity()
        # No warning should have fired in this 0.4s window because we reset
        # every 0.05s.
        assert wd.poll_warning() is None
    finally:
        wd.stop()


def test_warning_fires_after_interval() -> None:
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=0.15)
    wd.start()
    try:
        time.sleep(0.4)
        # Two intervals elapsed — at least one warning should be queued.
        warnings: list[int] = []
        while True:
            w = wd.poll_warning()
            if w is None:
                break
            warnings.append(w)
        assert warnings  # at least one warning
        # minutes_idle is rounded — 0 is acceptable for sub-minute warnings.
        assert all(isinstance(m, int) for m in warnings)
    finally:
        wd.stop()


def test_timeout_raises_idle_timeout() -> None:
    wd = IdleWatchdog(idle_timeout=0.2, idle_warning_interval=None)
    wd.start()
    try:
        time.sleep(0.4)
        with pytest.raises(IdleTimeout):
            wd.check_timeout()
    finally:
        wd.stop()


def test_no_warning_interval_disables_warnings() -> None:
    wd = IdleWatchdog(idle_timeout=2.0, idle_warning_interval=None)
    wd.start()
    try:
        time.sleep(0.3)
        assert wd.poll_warning() is None
    finally:
        wd.stop()


def test_stop_is_idempotent() -> None:
    wd = IdleWatchdog(idle_timeout=1.0, idle_warning_interval=None)
    wd.start()
    wd.stop()
    wd.stop()  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_idle_watchdog.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement IdleWatchdog**

Create `eden/orchestrator/_idle.py`:

```python
"""Idle watchdog — tracks last-activity, surfaces warnings + timeout from the main thread."""

from __future__ import annotations

import threading
import time
from queue import Empty, Queue

from eden.errors import IdleTimeout


class IdleWatchdog:
    """Polled watchdog. Caller calls record_activity() per stdout line.
    poll_warning() pops queued warnings; check_timeout() raises if the deadline
    has elapsed without activity."""

    def __init__(
        self,
        *,
        idle_timeout: float,
        idle_warning_interval: float | None,
    ) -> None:
        self._idle_timeout = idle_timeout
        self._warn_interval = idle_warning_interval
        self._last_activity = time.monotonic()
        self._activity_lock = threading.Lock()
        self._warnings: Queue[int] = Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._warn_interval is None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def record_activity(self) -> None:
        with self._activity_lock:
            self._last_activity = time.monotonic()

    def poll_warning(self) -> int | None:
        try:
            return self._warnings.get_nowait()
        except Empty:
            return None

    def check_timeout(self) -> None:
        with self._activity_lock:
            elapsed = time.monotonic() - self._last_activity
        if elapsed >= self._idle_timeout:
            raise IdleTimeout(
                message=(
                    f"agent produced no stdout for {elapsed:.1f}s "
                    f"(idle_timeout={self._idle_timeout}s)"
                ),
                hint="raise idle_timeout or check the agent's output",
            )

    def _loop(self) -> None:
        assert self._warn_interval is not None
        last_warn = time.monotonic()
        while not self._stop.is_set():
            self._stop.wait(timeout=self._warn_interval / 2)
            if self._stop.is_set():
                return
            now = time.monotonic()
            with self._activity_lock:
                idle_for = now - self._last_activity
            if idle_for >= self._warn_interval and (now - last_warn) >= self._warn_interval:
                self._warnings.put(int(idle_for // 60))
                last_warn = now
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_idle_watchdog.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/orchestrator/_idle.py tests/unit/test_idle_watchdog.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/orchestrator/_idle.py tests/unit/test_idle_watchdog.py
git commit -m "feat(orchestrator): add IdleWatchdog (warnings + timeout)"
```

---

## Task 18: Orchestrator — agent runner (subprocess + stdout pump)

**Files:**
- Create: `eden/orchestrator/_runner.py`
- Create: `tests/unit/test_agent_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agent_runner.py`:

```python
"""Verify _AgentRunner: subprocess spawn, stdout pump, idle integration, abort."""

from __future__ import annotations

import sys
import threading
import time

import pytest

from eden.abort import AbortController
from eden.errors import Aborted, IdleTimeout
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._runner import _AgentRunner

pytestmark = pytest.mark.unit


def test_runner_streams_lines_in_order() -> None:
    argv = [sys.executable, "-u", "-c",
            "import sys\nfor i in range(3):\n    sys.stdout.write(f'line{i}\\n')\n"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            warnings: list[int] = []
            lines = list(runner.iter_lines(
                signal=ctrl.signal,
                on_warning=warnings.append,
            ))
        assert lines == ["line0", "line1", "line2"]
    finally:
        wd.stop()


def test_runner_terminate_stops_subprocess() -> None:
    argv = [sys.executable, "-u", "-c",
            "import time, sys\nwhile True:\n    sys.stdout.write('tick\\n')\n    sys.stdout.flush()\n    time.sleep(0.05)\n"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            it = runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None)
            next(it)
            runner.terminate()
            # Drain remaining lines until generator exits.
            for _ in it:
                pass
    finally:
        wd.stop()


def test_runner_idle_timeout_raises() -> None:
    argv = [sys.executable, "-u", "-c",
            "import time\ntime.sleep(2)\n"]
    wd = IdleWatchdog(idle_timeout=0.2, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            with pytest.raises(IdleTimeout):
                for _ in runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None):
                    pass
    finally:
        wd.stop()


def test_runner_abort_signal_raises() -> None:
    argv = [sys.executable, "-u", "-c",
            "import time, sys\nwhile True:\n    sys.stdout.write('x\\n')\n    sys.stdout.flush()\n    time.sleep(0.05)\n"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            it = runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None)
            next(it)

            def trigger() -> None:
                time.sleep(0.05)
                ctrl.abort(reason="test")

            threading.Thread(target=trigger).start()

            with pytest.raises(Aborted):
                for _ in it:
                    pass
    finally:
        wd.stop()


def test_runner_emits_warnings_via_callback() -> None:
    argv = [sys.executable, "-u", "-c",
            "import time\ntime.sleep(1)\n"]
    wd = IdleWatchdog(idle_timeout=2.0, idle_warning_interval=0.15)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            warnings: list[int] = []
            for _ in runner.iter_lines(signal=ctrl.signal, on_warning=warnings.append):
                pass
        assert warnings  # at least one warning fired
    finally:
        wd.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_agent_runner.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement _AgentRunner**

Create `eden/orchestrator/_runner.py`:

```python
"""Agent process runner: spawn, stream stdout, integrate idle + abort."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable, Generator, Mapping
from queue import Empty, Queue
from typing import IO, Any

from eden.abort import AbortSignal
from eden.orchestrator._idle import IdleWatchdog

_SENTINEL: Any = object()
_GRACE_SECONDS = 5.0


def _drain(stream: IO[str], queue: Queue[Any]) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        queue.put(_SENTINEL)


class _AgentRunner:
    def __init__(
        self,
        *,
        argv: list[str],
        env: Mapping[str, str],
        watchdog: IdleWatchdog,
    ) -> None:
        self._argv = list(argv)
        self._env = dict(env)
        self._watchdog = watchdog
        self._proc: subprocess.Popen[str] | None = None
        self._stdout_q: Queue[Any] = Queue()
        self._stderr_chunks: list[str] = []

    def __enter__(self) -> _AgentRunner:
        merged = dict(os.environ)
        merged.update(self._env)
        self._proc = subprocess.Popen(
            self._argv,
            env=merged,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self._proc.stdout is not None
        assert self._proc.stderr is not None
        threading.Thread(
            target=_drain, args=(self._proc.stdout, self._stdout_q), daemon=True
        ).start()
        # stderr is captured silently (logged at iteration end if non-empty).
        threading.Thread(
            target=lambda: self._stderr_chunks.extend(self._proc.stderr or ()),
            daemon=True,
        ).start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.terminate()

    def iter_lines(
        self,
        *,
        signal: AbortSignal,
        on_warning: Callable[[int], None],
    ) -> Generator[str, None, None]:
        assert self._proc is not None
        while True:
            signal.raise_if_aborted()
            warning = self._watchdog.poll_warning()
            if warning is not None:
                on_warning(warning)
            try:
                item = self._stdout_q.get(timeout=0.1)
            except Empty:
                self._watchdog.check_timeout()
                continue
            if item is _SENTINEL:
                return
            self._watchdog.record_activity()
            yield item.rstrip("\n")

    def terminate(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self._proc = None
            return
        proc.terminate()
        try:
            proc.wait(timeout=_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        self._proc = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_agent_runner.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/orchestrator/_runner.py tests/unit/test_agent_runner.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/orchestrator/_runner.py tests/unit/test_agent_runner.py
git commit -m "feat(orchestrator): add _AgentRunner (subprocess + idle + abort)"
```

---

## Task 19: Orchestrator — setup / validation pipeline

**Files:**
- Create: `eden/orchestrator/_setup.py`
- Create: `tests/unit/test_orchestrator_setup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_orchestrator_setup.py`:

```python
"""Verify orchestrator setup pipeline: validation, strategy resolution, target branch."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.errors import CwdError, EnvMergeError, InvalidOptions
from eden.orchestrator._setup import (
    SetupResult,
    resolve_branch_strategy,
    resolve_setup,
    resolve_target_branch,
)
from eden.providers._types import BranchStrategy
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider

pytestmark = pytest.mark.unit


def test_resolve_setup_inline_prompt_no_args(tmp_git_repo: Path) -> None:
    result = resolve_setup(
        prompt="hello",
        prompt_file=None,
        prompt_args=None,
        cwd=tmp_git_repo,
        env=None,
        provider_env={},
        sandbox_kind="none",
    )
    assert isinstance(result, SetupResult)
    assert result.prompt_text == "hello"
    assert result.cwd == tmp_git_repo
    assert result.merged_env == {}


def test_resolve_setup_xor_violation_raises() -> None:
    with pytest.raises(InvalidOptions):
        resolve_setup(
            prompt=None, prompt_file=None, prompt_args=None,
            cwd=None, env=None, provider_env={}, sandbox_kind="none",
        )


def test_resolve_setup_env_collision_raises(tmp_git_repo: Path) -> None:
    with pytest.raises(EnvMergeError):
        resolve_setup(
            prompt="x",
            prompt_file=None,
            prompt_args=None,
            cwd=tmp_git_repo,
            env={"K": "1"},
            provider_env={"K": "2"},
            sandbox_kind="none",
        )


def test_resolve_setup_cwd_must_exist(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(CwdError):
        resolve_setup(
            prompt="x", prompt_file=None, prompt_args=None,
            cwd=missing, env=None, provider_env={}, sandbox_kind="none",
        )


def test_resolve_setup_cwd_must_be_git_repo(tmp_path: Path) -> None:
    with pytest.raises(CwdError):
        resolve_setup(
            prompt="x", prompt_file=None, prompt_args=None,
            cwd=tmp_path, env=None, provider_env={}, sandbox_kind="none",
        )


def test_resolve_branch_strategy_default_for_none_kind() -> None:
    s = resolve_branch_strategy(branch_strategy=None, sandbox_kind="none")
    assert s.tag == "head"


def test_resolve_branch_strategy_default_for_bind_mount() -> None:
    s = resolve_branch_strategy(branch_strategy=None, sandbox_kind="bind_mount")
    assert s.tag == "merge_to_head"


def test_resolve_branch_strategy_explicit_passes_through() -> None:
    s = resolve_branch_strategy(
        branch_strategy=BranchStrategy.named("feat/x"),
        sandbox_kind="bind_mount",
    )
    assert s.tag == "named"
    assert s.branch == "feat/x"


def test_resolve_branch_strategy_unsupported_raises() -> None:
    p = no_sandbox_provider()
    s = BranchStrategy.head()
    assert p.supports_strategy(s)


def test_resolve_target_branch_returns_active_branch(tmp_git_repo: Path) -> None:
    out = resolve_target_branch(host_repo_path=tmp_git_repo)
    assert out == "main"


def test_resolve_target_branch_detached_head(tmp_git_repo: Path) -> None:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_git_repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", sha], cwd=tmp_git_repo,
                   capture_output=True, check=True)
    out = resolve_target_branch(host_repo_path=tmp_git_repo)
    assert out == "HEAD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_orchestrator_setup.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement setup**

Create `eden/orchestrator/_setup.py`:

```python
"""Validation + strategy resolution for orchestrator.run()."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from eden.env import merge_env
from eden.errors import CwdError, InvalidOptions
from eden.prompt._source import resolve_source
from eden.providers._types import BranchStrategy

_KIND_DEFAULT_STRATEGY: dict[str, BranchStrategy] = {
    "none": BranchStrategy.head(),
    "bind_mount": BranchStrategy.merge_to_head(),
    "isolated": BranchStrategy.merge_to_head(),
}


@dataclass(frozen=True)
class SetupResult:
    prompt_text: str
    cwd: Path
    merged_env: dict[str, str]


def resolve_setup(
    *,
    prompt: str | None,
    prompt_file: str | Path | None,
    prompt_args: Mapping[str, str] | None,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    provider_env: Mapping[str, str],
    sandbox_kind: Literal["none", "bind_mount", "isolated"],
) -> SetupResult:
    text = resolve_source(prompt=prompt, prompt_file=prompt_file, prompt_args=prompt_args)
    merged = merge_env(provider_env, env or {})
    resolved_cwd = _resolve_cwd(cwd)
    return SetupResult(prompt_text=text, cwd=resolved_cwd, merged_env=merged)


def _resolve_cwd(cwd: Path | None) -> Path:
    target = cwd if cwd is not None else Path.cwd()
    if not target.exists():
        raise CwdError(message=f"cwd does not exist: {target}")
    if not target.is_dir():
        raise CwdError(message=f"cwd is not a directory: {target}")
    git_dir = target / ".git"
    if not git_dir.exists():
        raise CwdError(
            message=f"cwd is not a git repository: {target}",
            hint="run `git init` or pass a different cwd",
        )
    return target


def resolve_branch_strategy(
    *,
    branch_strategy: BranchStrategy | None,
    sandbox_kind: Literal["none", "bind_mount", "isolated"],
) -> BranchStrategy:
    if branch_strategy is not None:
        return branch_strategy
    return _KIND_DEFAULT_STRATEGY[sandbox_kind]


def resolve_target_branch(*, host_repo_path: Path) -> str:
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=str(host_repo_path),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "HEAD"
    return proc.stdout.strip() or "HEAD"
```

Note: `resolve_setup` doesn't validate strategy support; that happens in `_loop` via the existing `UnsupportedStrategy` mechanism Phase 2 already provides through `create_sandbox` path. The orchestrator wires it explicitly in Task 20.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_orchestrator_setup.py -v`
Expected: PASS.

- [ ] **Step 5: mypy strict**

Run: `mypy eden/orchestrator/_setup.py tests/unit/test_orchestrator_setup.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/orchestrator/_setup.py tests/unit/test_orchestrator_setup.py
git commit -m "feat(orchestrator): add setup pipeline (validation + strategy resolution)"
```

---

## Task 20: Orchestrator — main loop (`_loop._run_loop`)

**Files:**
- Create: `eden/orchestrator/_result.py`
- Create: `eden/orchestrator/_loop.py`
- Create: `tests/unit/test_run_loop.py`

- [ ] **Step 1: Implement RunResult assembler (no test — pure data)**

Create `eden/orchestrator/_result.py`:

```python
"""Assemble RunResult from orchestrator state."""

from __future__ import annotations

from pathlib import Path

from eden._types import Iteration, RunResult


def assemble(
    *,
    iterations: list[Iteration],
    completion_signal: str | None,
    branch: str,
    stdout: str,
    worktree_path: Path,
    preserved_worktree_path: Path | None,
    cwd: Path,
    prompt: str,
    env: dict[str, str],
    log_file_path: Path | None,
) -> RunResult:
    return RunResult(
        iterations=iterations,
        completion_signal=completion_signal,
        branch=branch,
        stdout=stdout,
        commits=[],
        worktree_path=worktree_path,
        preserved_worktree_path=preserved_worktree_path,
        merged_to_target_branch=None,
        cwd=cwd,
        prompt=prompt,
        env=env,
        log_file_path=log_file_path,
        session_id=None,
        session_file_path=None,
        usage=None,
    )
```

- [ ] **Step 2: Implement _run_loop**

Create `eden/orchestrator/_loop.py`:

```python
"""Orchestrator iteration loop driver."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from eden._types import Iteration, RunResult, Timeouts
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.errors import Aborted, IdleTimeout
from eden.lifecycle import Hooks, HookPhase
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.logging._config import Logging
from eden.logging._file import FileLogSink, default_log_path
from eden.orchestrator._completion import match
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._result import assemble
from eden.orchestrator._runner import _AgentRunner
from eden.orchestrator._setup import (
    SetupResult,
    resolve_branch_strategy,
    resolve_target_branch,
)
from eden.prompt import render_prompt
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.errors import UnsupportedStrategy
from eden.streaming import StreamEvent
from eden.worktree._create import create_worktree


def _iteration_step_timeout(t: Timeouts) -> float | None:
    return t.iteration_step


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run_loop(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    setup: SetupResult,
    branch_strategy: BranchStrategy | None,
    max_iterations: int,
    completion_signal: str | list[str],
    idle_timeout: float,
    idle_warning_interval: float | None,
    name: str | None,
    hooks: Hooks,
    timeouts: Timeouts,
    on_event: Callable[[StreamEvent], None] | None,
    logging_cfg: Logging | None,
    signal: AbortSignal,
    prompt_args: Mapping[str, str] | None,
) -> RunResult:
    strategy = resolve_branch_strategy(
        branch_strategy=branch_strategy,
        sandbox_kind=sandbox.kind,
    )
    if not sandbox.supports_strategy(strategy):
        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

    target_branch = resolve_target_branch(host_repo_path=setup.cwd)

    wt = create_worktree(host_repo_path=setup.cwd, strategy=strategy, name_hint=name)
    sink: FileLogSink | None = None
    handle = None
    iterations: list[Iteration] = []
    stdout_chunks: list[str] = []
    completion_hit: str | None = None
    rendered_prompt = ""
    log_path: Path | None = None
    preserved: Path | None = None

    try:
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady, hooks=hooks.host,
            worktree_path=wt.worktree_path, env=setup.merged_env, timeouts=timeouts,
        )

        signal.raise_if_aborted()

        handle = sandbox.create(CreateOptions(
            branch=wt.branch,
            worktree_path=wt.worktree_path,
            host_repo_path=wt.host_repo_path,
            env=setup.merged_env,
            mounts=(),
            name_hint=name,
        ))
        run_sandbox_hooks(
            phase=HookPhase.OnSandboxReady, hooks=hooks.sandbox,
            handle=handle, env=setup.merged_env, timeouts=timeouts,
        )

        log_cfg = logging_cfg or Logging.file(default_log_path(
            host_repo_path=setup.cwd, branch=wt.branch,
        ))
        log_path = log_cfg.path
        sink = FileLogSink.open(
            log_cfg.path,
            level=log_cfg.level,
            env_values=tuple(setup.merged_env.values()),
        )

        for i in range(max_iterations):
            signal.raise_if_aborted()
            run_host_hooks(
                phase=HookPhase.OnIterationStart, hooks=hooks.host,
                worktree_path=wt.worktree_path, env=setup.merged_env, timeouts=timeouts,
            )
            run_sandbox_hooks(
                phase=HookPhase.OnIterationStart, hooks=hooks.sandbox,
                handle=handle, env=setup.merged_env, timeouts=timeouts,
            )

            rendered_prompt = render_prompt(
                text=setup.prompt_text,
                args=prompt_args or {},
                source_branch=wt.branch,
                target_branch=target_branch,
                handle=handle,
            )

            argv = agent.build_command(IterationContext(
                iteration=i,
                prompt=rendered_prompt,
                sandbox_handle=handle,
                worktree_path=wt.worktree_path,
                branch=wt.branch,
                name=name,
            ))

            wd = IdleWatchdog(
                idle_timeout=idle_timeout,
                idle_warning_interval=idle_warning_interval,
            )
            wd.start()
            try:
                iter_completion: str | None = None
                with _AgentRunner(argv=argv, env=setup.merged_env, watchdog=wd) as runner:
                    def _emit_warning(minutes: int) -> None:
                        ev = StreamEvent(
                            type="idle_warning", agent_name=agent.name,
                            iteration=i, timestamp=_utcnow(), minutes_idle=minutes,
                        )
                        if sink is not None:
                            sink.write(ev)
                        if on_event is not None:
                            on_event(ev)

                    for line in runner.iter_lines(signal=signal, on_warning=_emit_warning):
                        stdout_chunks.append(line + "\n")
                        ev = agent.parse_stream(line) or StreamEvent(
                            type="text", agent_name=agent.name,
                            iteration=i, timestamp=_utcnow(), text=line,
                        )
                        if sink is not None:
                            sink.write(ev)
                        if on_event is not None:
                            on_event(ev)
                        hit = match(line, completion_signal)
                        if hit is not None:
                            iter_completion = hit
                            runner.terminate()
                            break
            finally:
                wd.stop()

            run_sandbox_hooks(
                phase=HookPhase.OnIterationEnd, hooks=hooks.sandbox,
                handle=handle, env=setup.merged_env, timeouts=timeouts,
            )
            run_host_hooks(
                phase=HookPhase.OnIterationEnd, hooks=hooks.host,
                worktree_path=wt.worktree_path, env=setup.merged_env, timeouts=timeouts,
            )

            iterations.append(Iteration(
                index=i, completion_signal=iter_completion,
                session_id=None, session_file_path=None, usage=None,
            ))
            if iter_completion is not None:
                completion_hit = iter_completion
                break

    finally:
        if handle is not None:
            try:
                run_sandbox_hooks(
                    phase=HookPhase.OnClose, hooks=hooks.sandbox,
                    handle=handle, env=setup.merged_env, timeouts=timeouts,
                )
            except Exception:
                pass
        try:
            run_host_hooks(
                phase=HookPhase.OnClose, hooks=hooks.host,
                worktree_path=wt.worktree_path, env=setup.merged_env, timeouts=timeouts,
            )
        except Exception:
            pass
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        if sink is not None:
            sink.close()
        close_result = wt.close()
        if close_result.action == "preserved":
            preserved = wt.worktree_path

    return assemble(
        iterations=iterations,
        completion_signal=completion_hit,
        branch=wt.branch,
        stdout="".join(stdout_chunks),
        worktree_path=wt.worktree_path,
        preserved_worktree_path=preserved,
        cwd=setup.cwd,
        prompt=rendered_prompt,
        env=setup.merged_env,
        log_file_path=log_path,
    )


__all__ = ["_run_loop"]
```

- [ ] **Step 3: Write the failing test**

Create `tests/unit/test_run_loop.py`:

```python
"""Verify _run_loop happy paths + completion + abort + idle."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from eden._types import Timeouts
from eden.abort import AbortController
from eden.agents import simulated_agent
from eden.errors import Aborted, IdleTimeout
from eden.lifecycle import Hooks
from eden.logging import Logging
from eden.orchestrator._loop import _run_loop
from eden.orchestrator._setup import resolve_setup
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _setup(tmp_git_repo: Path):
    return resolve_setup(
        prompt="please complete",
        prompt_file=None,
        prompt_args=None,
        cwd=tmp_git_repo,
        env=None,
        provider_env={},
        sandbox_kind="none",
    )


def test_run_loop_completion_ends_loop(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output="working\n<promise>COMPLETE</promise>\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    result = _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=5,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        idle_warning_interval=None,
        name=None,
        hooks=Hooks(),
        timeouts=Timeouts(),
        on_event=None,
        logging_cfg=Logging.file(tmp_git_repo / ".eden" / "logs" / "x.log"),
        signal=ctrl.signal,
        prompt_args=None,
    )
    assert len(result.iterations) == 1
    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert "working" in result.stdout
    assert result.log_file_path == tmp_git_repo / ".eden" / "logs" / "x.log"


def test_run_loop_max_iterations_exhausted_without_signal(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output="just text\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    result = _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=2,
        completion_signal="MARKER",
        idle_timeout=10.0,
        idle_warning_interval=None,
        name=None,
        hooks=Hooks(),
        timeouts=Timeouts(),
        on_event=None,
        logging_cfg=None,
        signal=ctrl.signal,
        prompt_args=None,
    )
    assert len(result.iterations) == 2
    assert result.completion_signal is None


def test_run_loop_aborts_when_signal_set(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output=["a"] * 50, delay_per_line=0.05)
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()

    def trigger() -> None:
        time.sleep(0.1)
        ctrl.abort(reason="test")

    threading.Thread(target=trigger).start()
    with pytest.raises(Aborted):
        _run_loop(
            agent=agent,
            sandbox=no_sandbox_provider(),
            setup=setup,
            branch_strategy=None,
            max_iterations=1,
            completion_signal="NEVER",
            idle_timeout=10.0,
            idle_warning_interval=None,
            name=None,
            hooks=Hooks(),
            timeouts=Timeouts(),
            on_event=None,
            logging_cfg=None,
            signal=ctrl.signal,
            prompt_args=None,
        )


def test_run_loop_idle_timeout(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output=["a"] * 30, delay_per_line=2.0)
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    with pytest.raises(IdleTimeout):
        _run_loop(
            agent=agent,
            sandbox=no_sandbox_provider(),
            setup=setup,
            branch_strategy=None,
            max_iterations=1,
            completion_signal="NEVER",
            idle_timeout=0.3,
            idle_warning_interval=None,
            name=None,
            hooks=Hooks(),
            timeouts=Timeouts(),
            on_event=None,
            logging_cfg=None,
            signal=ctrl.signal,
            prompt_args=None,
        )


def test_run_loop_emits_text_events_via_callback(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output="alpha\n<promise>COMPLETE</promise>\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    events: list[StreamEvent] = []
    _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        idle_warning_interval=None,
        name=None,
        hooks=Hooks(),
        timeouts=Timeouts(),
        on_event=events.append,
        logging_cfg=None,
        signal=ctrl.signal,
        prompt_args=None,
    )
    text_events = [e for e in events if e.type == "text"]
    assert any(e.text == "alpha" for e in text_events)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_run_loop.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: mypy strict**

Run: `mypy eden/orchestrator tests/unit/test_run_loop.py`
Expected: Success.

- [ ] **Step 6: Commit**

```bash
git add eden/orchestrator/_loop.py eden/orchestrator/_result.py tests/unit/test_run_loop.py
git commit -m "feat(orchestrator): add _run_loop driver + RunResult assembler"
```

---

## Task 21: Public `run()` and `create_worktree()` + top-level exports

**Files:**
- Modify: `eden/orchestrator/__init__.py`
- Modify: `eden/__init__.py`

- [ ] **Step 1: Implement public orchestrator surface**

Replace contents of `eden/orchestrator/__init__.py`:

```python
"""Public orchestrator surface: run() + create_worktree()."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.abort._signal import AbortController
from eden.agents._protocol import Agent
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._loop import _run_loop
from eden.orchestrator._setup import resolve_setup
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy
from eden.streaming import StreamEvent
from eden.worktree._create import WorktreeHandle, create_worktree as _carve_worktree


def _seconds(value: float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return _seconds(value)


def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,
    signal: AbortSignal | None = None,
) -> RunResult:
    """Run an agent against a sandbox in a managed worktree, returning RunResult."""
    cwd_path = Path(cwd) if cwd is not None else None
    setup = resolve_setup(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        cwd=cwd_path,
        env=env,
        provider_env={},
        sandbox_kind=sandbox.kind,
    )
    abort = signal if signal is not None else AbortController().signal
    return _run_loop(
        agent=agent,
        sandbox=sandbox,
        setup=setup,
        branch_strategy=branch_strategy,
        max_iterations=max_iterations,
        completion_signal=completion_signal,
        idle_timeout=_seconds(idle_timeout),
        idle_warning_interval=_maybe_seconds(idle_warning_interval),
        name=name,
        hooks=hooks if hooks is not None else Hooks(),
        timeouts=timeouts if timeouts is not None else Timeouts(),
        on_event=on_event,
        logging_cfg=logging,
        signal=abort,
        prompt_args=prompt_args,
    )


def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
) -> WorktreeHandle:
    """Carve a worktree using Phase 2's create_worktree, with sugar for branch/strategy.

    Returns a WorktreeHandle (context manager) with `.branch`, `.worktree_path`, `.close()`.
    """
    if branch is not None and branch_strategy is not None:
        raise ValueError("branch and branch_strategy are mutually exclusive")
    if branch is not None:
        strategy = BranchStrategy.named(branch)
    elif branch_strategy is not None:
        strategy = branch_strategy
    else:
        strategy = BranchStrategy.merge_to_head()
    return _carve_worktree(
        host_repo_path=Path.cwd(),
        strategy=strategy,
        name_hint=name,
    )


__all__ = ["create_worktree", "run"]
```

- [ ] **Step 2: Update top-level eden package exports**

Replace contents of `eden/__init__.py`:

```python
"""Eden — Python orchestrator for AI coding agents in sandboxed worktrees."""

from __future__ import annotations

from eden._types import Commit, Iteration, RunResult, Timeouts, Usage
from eden._version import __version__
from eden.abort import AbortController, AbortSignal, Aborted
from eden.agents import Agent, IterationContext, simulated_agent
from eden.errors import (
    ConfigError,
    CwdError,
    EdenError,
    EdenTimeoutError,
    EnvMergeError,
    HookError,
    HookFailed,
    HookTimeout,
    IdleTimeout,
    InvalidOptions,
    PromptError,
    StepTimeout,
)
from eden.lifecycle import Hook, HookPhase, Hooks, HostHooks, SandboxHooks
from eden.logging import Logging
from eden.orchestrator import create_worktree, run
from eden.providers._types import BranchStrategy, Mount
from eden.streaming import StreamEvent

__all__ = [
    "__version__",
    # entrypoints
    "run",
    "create_worktree",
    # agent
    "Agent",
    "IterationContext",
    "simulated_agent",
    # provider re-exports
    "BranchStrategy",
    "Mount",
    # lifecycle
    "Hook",
    "HookPhase",
    "Hooks",
    "HostHooks",
    "SandboxHooks",
    # config / data
    "Logging",
    "Timeouts",
    "RunResult",
    "Iteration",
    "Usage",
    "Commit",
    "StreamEvent",
    # cancellation
    "AbortController",
    "AbortSignal",
    "Aborted",
    # errors
    "EdenError",
    "ConfigError",
    "InvalidOptions",
    "PromptError",
    "EnvMergeError",
    "CwdError",
    "HookError",
    "HookFailed",
    "HookTimeout",
    "EdenTimeoutError",
    "IdleTimeout",
    "StepTimeout",
]
```

- [ ] **Step 3: Verify imports**

Run:

```bash
python -c "import eden; print(sorted([n for n in eden.__all__ if not n.startswith('_')]))"
```

Expected: prints a sorted list including `Agent`, `BranchStrategy`, `EdenError`, `Hook`, `Hooks`, `Logging`, `RunResult`, `StreamEvent`, `Timeouts`, `run`, `simulated_agent`, etc.

- [ ] **Step 4: mypy strict on full package**

Run: `mypy eden`
Expected: Success.

- [ ] **Step 5: Run full unit suite**

Run: `pytest tests/unit -v --no-cov`
Expected: All previously-passing unit tests still pass + new run-loop tests pass.

- [ ] **Step 6: Commit**

```bash
git add eden/__init__.py eden/orchestrator/__init__.py
git commit -m "feat(orchestrator): add public run() + create_worktree(); wire top-level exports"
```

---

## Task 22: Smoke E2E test (`tests/e2e/test_run_smoke.py`)

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_run_smoke.py`

- [ ] **Step 1: Implement e2e conftest**

Create `tests/e2e/conftest.py`:

```python
"""E2E test fixtures."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def e2e_git_repo(tmp_path: Path) -> Iterator[Path]:
    """Initialize a tmp git repo on `main`, yield path, restore CWD on exit."""
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "e2e@example.com"],
                   cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "E2E"],
                   cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
    prev = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev)
```

- [ ] **Step 2: Write the e2e smoke test**

Create `tests/e2e/test_run_smoke.py`:

```python
"""Smoke E2E: simulated_agent + no_sandbox + merge_to_head + idle warnings."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden

pytestmark = pytest.mark.e2e


def test_simulated_agent_full_run(e2e_git_repo: Path) -> None:
    events: list[eden.StreamEvent] = []
    result = eden.run(
        agent=eden.simulated_agent(
            output="working on it\n<promise>COMPLETE</promise>\n",
            delay_per_line=0.05,
        ),
        sandbox=__import__(
            "eden.sandboxes.no_sandbox", fromlist=["provider"],
        ).provider(),
        prompt="branch={{SOURCE_BRANCH}} target={{TARGET_BRANCH}}",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        idle_warning_interval=0.05,  # fire warnings during run
        on_event=events.append,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert len(result.iterations) == 1
    assert result.iterations[0].completion_signal == "<promise>COMPLETE</promise>"
    assert "working on it" in result.stdout
    # rendered prompt has substituted SOURCE_BRANCH and TARGET_BRANCH
    assert "branch=" in result.prompt
    assert "target=main" in result.prompt
    assert "{{SOURCE_BRANCH}}" not in result.prompt
    # log file written and discoverable
    assert result.log_file_path is not None
    assert result.log_file_path.exists()
    body = result.log_file_path.read_text()
    assert "working on it" in body
    # at least one idle_warning event fired through on_event
    assert any(ev.type == "idle_warning" for ev in events)
    # text events for the agent's output
    text_events = [ev for ev in events if ev.type == "text"]
    assert any(ev.text == "working on it" for ev in text_events)


def test_max_iterations_no_completion(e2e_git_repo: Path) -> None:
    result = eden.run(
        agent=eden.simulated_agent(output="just text\n"),
        sandbox=__import__("eden.sandboxes.no_sandbox", fromlist=["provider"]).provider(),
        prompt="x",
        max_iterations=3,
        completion_signal="NEVER_HIT",
        idle_timeout=10.0,
    )
    assert len(result.iterations) == 3
    assert result.completion_signal is None
    assert all(it.completion_signal is None for it in result.iterations)
```

- [ ] **Step 3: Run e2e tests**

Run: `pytest tests/e2e -v -m e2e`
Expected: PASS (2 tests).

- [ ] **Step 4: Run full suite (unit + e2e + integration excluded)**

Run: `pytest -v -m "unit or e2e" --no-cov`
Expected: All tests pass on every OS (3 OS × 3 Py = 9 jobs).

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_run_smoke.py
git commit -m "test(e2e): add simulated_agent smoke run for phase 3a"
```

---

## Task 23: CI wire-up + coverage gate

**Files:**
- Modify: `.github/workflows/*.yml` (only if e2e marker isn't already covered by the existing unit invocation)

- [ ] **Step 1: Inspect current CI**

Run: `ls .github/workflows && cat .github/workflows/*.yml | grep -nE 'pytest|markers'`
Expected output: identify how `unit`, `integration`, `smoke` markers are currently invoked.

- [ ] **Step 2: Add `e2e` marker to the unit-test job**

Find the workflow step that runs `pytest -m unit ...` and modify it to include `e2e` (most repos will have this in `.github/workflows/ci.yml`):

Change the pytest invocation in the unit-test job from `-m unit` to `-m "unit or e2e"`:

```yaml
      - name: Run unit + e2e tests
        run: pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```

If the project uses a separate test command, mirror the change wherever the unit marker appears. Do not touch the integration job (it stays Linux-only and runs `-m integration`).

- [ ] **Step 3: Verify coverage gate locally**

Run: `pytest -m "unit or e2e" --cov=eden --cov-report=term-missing --cov-fail-under=70`
Expected: PASS, coverage ≥ 70%.

If coverage is < 70%, add focused tests until passing. Do not delete tests to mask gaps.

- [ ] **Step 4: Run mypy + ruff on the full tree**

Run:
```bash
mypy eden tests
ruff format --check eden tests
ruff check --no-cache eden tests
```
Expected: All three Success.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows
git commit -m "ci: include e2e tests in the unit job"
```

---

## Task 24: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump status line**

Modify `README.md:5` (the `> **Status:** ...` blockquote) to read:

```markdown
> **Status:** Pre-alpha. Phases 1–3a complete: package skeleton, provider Protocols, worktree manager, `no_sandbox` and `docker` MVP providers, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent`, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, and file logging. Claude Code agent (3b), additional providers (4), other agents (5), CLI scaffolder (6), and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: bump README status to phase 3a complete"
```

---

## Final verification (after every task is committed)

- [ ] **Step 1: Full local CI parity check**

Run:

```bash
ruff format --check eden tests
ruff check --no-cache eden tests
mypy eden tests
pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```

Expected: Every command Success / PASS.

- [ ] **Step 2: Run pushed CI**

```bash
git push origin main
```

Then check CI from the GitHub UI — all 9 matrix jobs (Linux/macOS/Windows × py3.11/3.12/3.13) green for both unit+e2e and (Linux-only) integration jobs.

- [ ] **Step 3: Tag the phase**

Wait for CI green before tagging.

```bash
git tag -a phase-3a -m "Phase 3a: orchestration core complete (simulated agent)"
git push origin phase-3a
```

---

## Notes for the implementer

- **Threading model:** every subprocess uses the same Phase 2 `stream_exec`-style pattern: `subprocess.Popen(text=True, bufsize=1)` + a daemon thread draining stdout into a `Queue` with a sentinel. Don't introduce `asyncio` anywhere.
- **mypy `--strict` on Windows:** keep `sys.platform == "win32"` checks **inline** (not via an intermediate constant) so mypy narrows correctly. This bit Phase 2 — see commit `cd7750c` for context.
- **Cross-platform paths in argv:** when paths flow into a Linux container or a Linux-only docker argv, use `.as_posix()` on the sandbox-side path. This bit Phase 2 — see commit `d9aae08`.
- **Idempotency:** every `close()` / `stop()` / `release()` method must be safely callable twice. Phase 2 set this pattern.
- **Frozen dataclasses for all public types.** Tests assert frozenness on a couple — it's the contract.
- **Hook ordering at every phase:** host runs first (sequential), then sandbox (parallel). Documented in spec §3.8 and tested in `test_lifecycle_runner.py`.
- **`Aborted` propagation through teardown:** `_run_loop`'s `try/finally` swallows hook errors during teardown so the original abort/exception reaches the caller. This is intentional — a teardown failure during an abort is information, not a cause to mask the abort.
- **No new pip dependencies.** Everything is stdlib + Phase 2 deps.
- **Coverage ≥ 70%** on `eden/`. The unit suite alone should clear this; e2e adds margin.

# Eden Phase 3b — Claude Code Agent + Session JSONL Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a Claude-Code-backed `Agent` factory (`claude_code(...)`) that drops into Phase 3a's `eden.run(...)` and captures each iteration's session JSONL on disk, populating the `session_id` / `session_file_path` / `usage` fields that Phase 3a left as `None`.

**Architecture:** Two new sub-packages — `eden.agents.claude_code` (factory + argv builder + stream parser) and `eden.session` (slug derivation + path rewriting + JSONL copy). Extends `StreamEvent` with two new kinds (`"tool_call"`, `"usage"`). Wires session capture into `_run_loop` between agent EOF and the iteration record append.

**Tech Stack:** Python 3.11+, stdlib only (`subprocess`, `json`, `pathlib`, `re`). Re-uses Phase 3a's `_AgentRunner`, `IdleWatchdog`, `FileLogSink`. No new pip dependencies. CI matrix unchanged: 3 OS × 3 Python versions.

**Reference spec:** `docs/superpowers/specs/2026-05-01-eden-phase3b-claude-code-design.md`

**Phase 3a base:** This plan assumes Phase 3a is committed (`ecf5646`): `Agent` Protocol, `IterationContext`, `simulated_agent`, `_AgentRunner`, `StreamEvent`, `Iteration`, `RunResult`, `Usage`, `eden.run()` all present. `Iteration.session_id`, `Iteration.session_file_path`, `Iteration.usage`, `RunResult.session_id`, `RunResult.session_file_path`, `RunResult.usage` are declared but always `None`.

---

## File structure produced by this plan

```
eden/
├── streaming/_event.py                     # MODIFY — extend Literal + new optional fields
├── errors.py                               # MODIFY — add SessionCaptureFailed
├── session/                                # NEW package
│   ├── __init__.py                         # NEW — capture_session() + __all__
│   ├── _slug.py                            # NEW — claude_projects_slug
│   ├── _encode.py                          # NEW — rewrite_paths
│   └── _store.py                           # NEW — write_session_copy
├── agents/
│   ├── __init__.py                         # MODIFY — re-export claude_code
│   └── claude_code/                        # NEW package
│       ├── __init__.py                     # NEW — claude_code() + __all__
│       ├── _argv.py                        # NEW — build_argv
│       ├── _stream.py                      # NEW — parse_line
│       └── _agent.py                       # NEW — _ClaudeCodeAgent dataclass
├── orchestrator/
│   ├── _result.py                          # MODIFY — assemble() takes session_id/session_file_path/usage
│   └── _loop.py                            # MODIFY — populate session fields + docker mount injection
└── __init__.py                             # MODIFY — re-export claude_code + SessionCaptureFailed

tests/
├── _fake_claude/                           # NEW — test infrastructure
│   ├── __init__.py                         # NEW — shim helper
│   └── _transcript.py                      # NEW — typed builder
├── unit/
│   ├── test_streaming_extensions.py        # NEW
│   ├── test_errors_phase3b.py              # NEW
│   ├── test_session_slug.py                # NEW
│   ├── test_session_rewrite.py             # NEW
│   ├── test_session_store.py               # NEW
│   ├── test_claude_code_argv.py            # NEW
│   ├── test_claude_code_stream.py          # NEW
│   └── test_claude_code_agent.py           # NEW
└── e2e/
    └── test_claude_code_smoke.py           # NEW

README.md                                   # MODIFY — bump status to phase 3b complete
```

**File responsibilities:**

- `eden/streaming/_event.py` — adds `"tool_call"` and `"usage"` to the `type` literal; adds optional fields `tool_name`, `tool_input`, `usage`, `session_id`; extends `__post_init__` validation.
- `eden/errors.py` — adds `SessionCaptureFailed(EdenError)` with default `code="session.capture_failed"`.
- `eden/session/_slug.py` — pure helper deriving Claude Code's projects-dir slug from a cwd path.
- `eden/session/_encode.py` — pure helper rewriting absolute-path string-prefixes inside a JSON line.
- `eden/session/_store.py` — `write_session_copy(src, dest, ...)` reads + rewrites + writes line-by-line.
- `eden/session/__init__.py` — public `capture_session(...)` orchestrates slug → src lookup → mkdir → copy.
- `eden/agents/claude_code/_argv.py` — `build_argv(...)` constructs the `claude --print --output-format stream-json --verbose ...` argv.
- `eden/agents/claude_code/_stream.py` — `parse_line(...)` decodes one stream-json line and returns a `StreamEvent | None`.
- `eden/agents/claude_code/_agent.py` — `_ClaudeCodeAgent` frozen dataclass implementing the `Agent` Protocol structurally + a `captures_sessions: bool` field.
- `eden/agents/claude_code/__init__.py` — public `claude_code(...)` factory.
- `eden/agents/__init__.py` — re-exports `claude_code` alongside existing `Agent`/`IterationContext`/`simulated_agent`.
- `eden/orchestrator/_result.py` — `assemble()` gains three keyword-only parameters that flow into `RunResult(...)`.
- `eden/orchestrator/_loop.py` — populates per-iteration `iter_session_id`/`iter_usage`/`iter_session_file`; injects `~/.claude/projects/` mount when `agent.captures_sessions=True`; passes session/usage values into `Iteration` + `assemble()`.
- `eden/__init__.py` — re-exports `claude_code` and `SessionCaptureFailed`.
- `tests/_fake_claude/__init__.py` — `install_fake_claude(tmp_path, transcript, monkeypatch)` writes a Python script named `claude` and overrides `$PATH` + `$HOME`.
- `tests/_fake_claude/_transcript.py` — `Transcript` builder for stream-json fixtures.

---

## Pre-flight: confirm Phase 3a baseline

- [ ] **Step 1: Confirm working tree is clean and on main**

Run:
```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  git status -s && git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expected: empty status, branch `main`, commit `ae5e2b2 docs: add phase 3b ...` (or later).

- [ ] **Step 2: Confirm phase 3a tests pass**

Run:
```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3
```
Expected: `241 passed` (Phase 3a baseline). If lower, stop and investigate.

No commit at this step — sanity check only.

---

## Task 1: Extend StreamEvent with `tool_call` and `usage` kinds

**Files:**
- Modify: `eden/streaming/_event.py`
- Create: `tests/unit/test_streaming_extensions.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_streaming_extensions.py`:

```python
"""Verify Phase 3b extensions to StreamEvent."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eden._types import Usage
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, tzinfo=UTC)


def _u() -> Usage:
    return Usage(
        input_tokens=10,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        output_tokens=20,
    )


def test_tool_call_event_round_trip() -> None:
    ev = StreamEvent(
        type="tool_call",
        agent_name="claude-code",
        iteration=0,
        timestamp=_ts(),
        tool_name="Read",
        tool_input={"path": "/x"},
    )
    assert ev.tool_name == "Read"
    assert ev.tool_input == {"path": "/x"}
    assert ev.text is None


def test_tool_call_requires_tool_name() -> None:
    with pytest.raises(ValueError, match="tool_name"):
        StreamEvent(
            type="tool_call",
            agent_name="claude-code",
            iteration=0,
            timestamp=_ts(),
            tool_input={"path": "/x"},
        )


def test_usage_event_round_trip() -> None:
    ev = StreamEvent(
        type="usage",
        agent_name="claude-code",
        iteration=0,
        timestamp=_ts(),
        usage=_u(),
        session_id="abc-123",
    )
    assert ev.usage == _u()
    assert ev.session_id == "abc-123"


def test_usage_requires_usage_field() -> None:
    with pytest.raises(ValueError, match="usage"):
        StreamEvent(
            type="usage",
            agent_name="claude-code",
            iteration=0,
            timestamp=_ts(),
            session_id="abc-123",
        )


def test_text_event_still_works_after_extension() -> None:
    ev = StreamEvent(
        type="text",
        agent_name="claude-code",
        iteration=0,
        timestamp=_ts(),
        text="hello",
    )
    assert ev.tool_name is None
    assert ev.tool_input is None
    assert ev.usage is None
    assert ev.session_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_streaming_extensions.py -v`
Expected: FAIL on `tool_call` / `usage` kind not accepted by the `Literal`.

- [ ] **Step 3: Implement extension**

Replace contents of `eden/streaming/_event.py` with:

```python
"""StreamEvent: discriminated-union event emitted from the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from eden._types import Usage


@dataclass(frozen=True)
class StreamEvent:
    """Discriminated-union event from the orchestrator.

    Phase 3a kinds: ``"text"`` (carries ``text``) and ``"idle_warning"`` (carries
    ``minutes_idle``). Phase 3b adds ``"tool_call"`` (carries ``tool_name`` and
    ``tool_input``) and ``"usage"`` (carries ``usage`` and ``session_id``).
    """

    type: Literal["text", "idle_warning", "tool_call", "usage"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None
    minutes_idle: int | None = None
    tool_name: str | None = None
    tool_input: dict[str, object] | None = None
    usage: Usage | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.type == "text" and self.text is None:
            raise ValueError('StreamEvent type="text" requires text to be non-None')
        if self.type == "idle_warning" and self.minutes_idle is None:
            raise ValueError(
                'StreamEvent type="idle_warning" requires minutes_idle to be non-None'
            )
        if self.type == "tool_call" and self.tool_name is None:
            raise ValueError('StreamEvent type="tool_call" requires tool_name to be non-None')
        if self.type == "usage" and self.usage is None:
            raise ValueError('StreamEvent type="usage" requires usage to be non-None')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_streaming_extensions.py -v`
Expected: PASS — 5 tests.

- [ ] **Step 5: Run pre-existing streaming + run-loop tests**

Run: `.venv/bin/pytest tests/unit/test_streaming.py tests/unit/test_run_loop.py -v`
Expected: PASS (no regression on Phase 3a behavior).

- [ ] **Step 6: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/streaming tests/unit/test_streaming_extensions.py && \
.venv/bin/ruff format eden/streaming/_event.py tests/unit/test_streaming_extensions.py && \
.venv/bin/ruff format --check eden/streaming/_event.py tests/unit/test_streaming_extensions.py && \
.venv/bin/ruff check --fix eden/streaming/_event.py tests/unit/test_streaming_extensions.py && \
.venv/bin/ruff check eden/streaming/_event.py tests/unit/test_streaming_extensions.py
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add eden/streaming/_event.py tests/unit/test_streaming_extensions.py
git commit -m "feat(streaming): extend StreamEvent with tool_call + usage kinds"
```

---

## Task 2: Add SessionCaptureFailed error class

**Files:**
- Modify: `eden/errors.py`
- Create: `tests/unit/test_errors_phase3b.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_errors_phase3b.py`:

```python
"""Verify Phase 3b additions to the exception hierarchy."""

from __future__ import annotations

import pytest

from eden.errors import EdenError, SessionCaptureFailed

pytestmark = pytest.mark.unit


def test_session_capture_failed_inherits_eden_error() -> None:
    assert issubclass(SessionCaptureFailed, EdenError)


def test_session_capture_failed_default_code() -> None:
    err = SessionCaptureFailed(message="not found")
    assert err.code == "session.capture_failed"
    assert err.message == "not found"
    assert err.hint is None
    assert err.cause is None
    assert "[session.capture_failed]" in str(err)


def test_session_capture_failed_carries_cause() -> None:
    cause = FileNotFoundError("missing")
    err = SessionCaptureFailed(message="x", cause=cause)
    assert err.cause is cause
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_errors_phase3b.py -v`
Expected: FAIL — `SessionCaptureFailed` not importable.

- [ ] **Step 3: Add SessionCaptureFailed at the end of `eden/errors.py`**

Append (do not replace existing content) to `eden/errors.py`:

```python


class SessionCaptureFailed(EdenError):
    """Raised when capture_session() can't locate, read, or write the JSONL.

    Always a soft failure — the orchestrator catches it and surfaces a warning
    event without aborting the run.
    """

    def __init__(
        self,
        *,
        code: str = "session.capture_failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_errors_phase3b.py -v`
Expected: PASS — 3 tests.

- [ ] **Step 5: Pre-existing errors tests still pass**

Run: `.venv/bin/pytest tests/unit/test_errors.py tests/unit/test_errors_phase3a.py -v`
Expected: PASS (no regression).

- [ ] **Step 6: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/errors.py tests/unit/test_errors_phase3b.py && \
.venv/bin/ruff format eden/errors.py tests/unit/test_errors_phase3b.py && \
.venv/bin/ruff format --check eden/errors.py tests/unit/test_errors_phase3b.py && \
.venv/bin/ruff check --fix eden/errors.py tests/unit/test_errors_phase3b.py && \
.venv/bin/ruff check eden/errors.py tests/unit/test_errors_phase3b.py
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add eden/errors.py tests/unit/test_errors_phase3b.py
git commit -m "feat(errors): add SessionCaptureFailed for phase 3b"
```

---

## Task 3: Session slug derivation

**Files:**
- Create: `eden/session/__init__.py` (placeholder; expanded in Task 6)
- Create: `eden/session/_slug.py`
- Create: `tests/unit/test_session_slug.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_session_slug.py`:

```python
"""Verify Claude Code's projects-dir slug derivation."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from eden.session._slug import claude_projects_slug

pytestmark = pytest.mark.unit


def test_simple_posix_path() -> None:
    assert claude_projects_slug(PurePosixPath("/Users/x/work/eden")) == "-Users-x-work-eden"


def test_workspace_root() -> None:
    assert claude_projects_slug(PurePosixPath("/workspace")) == "-workspace"


def test_relative_path_resolved_through_absolute() -> None:
    """Relative paths get absolutized before slugging.

    The function accepts any path-like; users typically pass an absolute Path
    already (because the orchestrator does), but a sandbox cwd that's relative
    must still produce a deterministic slug.
    """
    p = PurePosixPath("/Users/x/work/eden/sub")
    assert claude_projects_slug(p) == "-Users-x-work-eden-sub"


def test_windows_backslashes_collapse() -> None:
    """A Windows-style path with backslashes maps each separator to dash."""
    assert (
        claude_projects_slug(PureWindowsPath(r"C:\Users\x\work\eden"))
        == "C--Users-x-work-eden"
    )


def test_trailing_slash_ignored() -> None:
    assert claude_projects_slug(PurePosixPath("/Users/x/work/eden/")) == "-Users-x-work-eden"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_session_slug.py -v`
Expected: FAIL — `eden.session._slug` not found.

- [ ] **Step 3: Implement slug derivation**

Create `eden/session/_slug.py`:

```python
"""Derive Claude Code's ~/.claude/projects/<slug>/ directory name from a cwd path."""

from __future__ import annotations

from pathlib import PurePath


def claude_projects_slug(cwd: PurePath) -> str:
    """Return the Claude Code projects-dir slug for ``cwd``.

    Algorithm: take the path's string form, replace every '/' and '\\' with
    '-', collapse adjacent dashes to a single dash, and strip trailing dashes.

    Cross-platform: forward and back slashes both collapse to '-'.
    """
    raw = str(cwd)
    slug = raw.replace("/", "-").replace("\\", "-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.rstrip("-")
```

- [ ] **Step 4: Stub the package init**

Create `eden/session/__init__.py`:

```python
"""Session JSONL capture. (Public re-exports added in task 6.)"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_session_slug.py -v`
Expected: PASS — 5 tests.

- [ ] **Step 6: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/session tests/unit/test_session_slug.py && \
.venv/bin/ruff format eden/session/_slug.py eden/session/__init__.py tests/unit/test_session_slug.py && \
.venv/bin/ruff format --check eden/session/_slug.py eden/session/__init__.py tests/unit/test_session_slug.py && \
.venv/bin/ruff check --fix eden/session/_slug.py eden/session/__init__.py tests/unit/test_session_slug.py && \
.venv/bin/ruff check eden/session/_slug.py eden/session/__init__.py tests/unit/test_session_slug.py
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add eden/session/_slug.py eden/session/__init__.py tests/unit/test_session_slug.py
git commit -m "feat(session): add claude_projects_slug derivation"
```

---

## Task 4: JSON path-prefix rewriter

**Files:**
- Create: `eden/session/_encode.py`
- Create: `tests/unit/test_session_rewrite.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_session_rewrite.py`:

```python
"""Verify rewrite_paths walks JSON and replaces sandbox-prefix string starts."""

from __future__ import annotations

import json

import pytest

from eden.session._encode import rewrite_paths

pytestmark = pytest.mark.unit


def _r(line: str) -> str:
    return rewrite_paths(line, sandbox_prefix="/workspace", host_prefix="/host/repo")


def test_top_level_string_replaced() -> None:
    out = _r(json.dumps({"cwd": "/workspace"}))
    assert json.loads(out) == {"cwd": "/host/repo"}


def test_nested_string_replaced() -> None:
    obj = {"tool_input": {"file_path": "/workspace/src/x.py"}}
    out = _r(json.dumps(obj))
    assert json.loads(out) == {"tool_input": {"file_path": "/host/repo/src/x.py"}}


def test_array_of_strings_replaced() -> None:
    obj = {"paths": ["/workspace/a", "/elsewhere/b", "/workspace/c"]}
    out = _r(json.dumps(obj))
    assert json.loads(out) == {"paths": ["/host/repo/a", "/elsewhere/b", "/host/repo/c"]}


def test_substring_in_middle_not_replaced() -> None:
    """A path matching the prefix in the middle of a string is NOT replaced.

    rewrite_paths uses startswith, not contains.
    """
    obj = {"text": "see /workspace/x for details"}
    out = _r(json.dumps(obj))
    # The "see " prefix means startswith fails; line passes through unchanged.
    assert json.loads(out) == {"text": "see /workspace/x for details"}


def test_non_string_values_pass_through() -> None:
    obj = {"a": 1, "b": True, "c": None, "d": [1, 2, 3], "e": "/workspace/x"}
    out = _r(json.dumps(obj))
    assert json.loads(out) == {"a": 1, "b": True, "c": None, "d": [1, 2, 3], "e": "/host/repo/x"}


def test_invalid_json_returns_unchanged() -> None:
    assert _r("not json {") == "not json {"


def test_no_match_returns_equivalent_json() -> None:
    line = json.dumps({"k": "v"})
    out = _r(line)
    assert json.loads(out) == json.loads(line)


def test_exact_prefix_match_replaced() -> None:
    """A path equal to the sandbox prefix (no trailing slash) is also replaced."""
    out = _r(json.dumps({"cwd": "/workspace"}))
    assert json.loads(out) == {"cwd": "/host/repo"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_session_rewrite.py -v`
Expected: FAIL — `eden.session._encode` not found.

- [ ] **Step 3: Implement rewrite_paths**

Create `eden/session/_encode.py`:

```python
"""Rewrite absolute path prefixes inside a JSON line."""

from __future__ import annotations

import json
from typing import Any


def rewrite_paths(line: str, *, sandbox_prefix: str, host_prefix: str) -> str:
    """Parse ``line`` as JSON, recursively walk every string value, replace any
    occurrence of ``sandbox_prefix`` at the START of the string with
    ``host_prefix``, re-encode.

    If ``line`` doesn't parse as JSON, return it unchanged.
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return line
    rewritten = _walk(obj, sandbox_prefix=sandbox_prefix, host_prefix=host_prefix)
    return json.dumps(rewritten, ensure_ascii=False)


def _walk(obj: Any, *, sandbox_prefix: str, host_prefix: str) -> Any:
    if isinstance(obj, str):
        if obj.startswith(sandbox_prefix):
            return host_prefix + obj[len(sandbox_prefix) :]
        return obj
    if isinstance(obj, list):
        return [_walk(item, sandbox_prefix=sandbox_prefix, host_prefix=host_prefix) for item in obj]
    if isinstance(obj, dict):
        return {
            k: _walk(v, sandbox_prefix=sandbox_prefix, host_prefix=host_prefix)
            for k, v in obj.items()
        }
    return obj
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_session_rewrite.py -v`
Expected: PASS — 8 tests.

- [ ] **Step 5: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/session/_encode.py tests/unit/test_session_rewrite.py && \
.venv/bin/ruff format eden/session/_encode.py tests/unit/test_session_rewrite.py && \
.venv/bin/ruff format --check eden/session/_encode.py tests/unit/test_session_rewrite.py && \
.venv/bin/ruff check --fix eden/session/_encode.py tests/unit/test_session_rewrite.py && \
.venv/bin/ruff check eden/session/_encode.py tests/unit/test_session_rewrite.py
```
Expected: All clean.

- [ ] **Step 6: Commit**

```bash
git add eden/session/_encode.py tests/unit/test_session_rewrite.py
git commit -m "feat(session): add rewrite_paths JSON walker"
```

---

## Task 5: Session store + public capture_session helper

**Files:**
- Create: `eden/session/_store.py`
- Modify: `eden/session/__init__.py`
- Create: `tests/unit/test_session_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_session_store.py`:

```python
"""Verify capture_session: locate ~/.claude/projects/<slug>/<id>.jsonl, copy + rewrite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eden.errors import SessionCaptureFailed
from eden.session import capture_session

pytestmark = pytest.mark.unit


def _write_source(home: Path, slug: str, session_id: str, lines: list[dict]) -> Path:
    src_dir = home / ".claude" / "projects" / slug
    src_dir.mkdir(parents=True, exist_ok=True)
    src = src_dir / f"{session_id}.jsonl"
    src.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return src


def test_happy_path_no_sandbox(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    # In no_sandbox, sandbox_cwd == host_repo_path. No path rewriting needed,
    # but capture_session should still copy the file.
    src = _write_source(
        home, slug=str(repo).replace("/", "-").replace("\\", "-").lstrip("-"),
        session_id="abc-123",
        lines=[{"cwd": str(repo)}, {"text": "hello"}],
    )
    # We cannot rely on the slug helper in this test (it's tested elsewhere);
    # write under the slug derived from str(repo).
    dest = capture_session(
        session_id="abc-123",
        sandbox_cwd=repo,
        host_repo_path=repo,
        branch="HEAD",
        iteration=0,
        home=home,
    )
    assert dest.exists()
    assert dest.parent == repo / ".eden" / "sessions" / "HEAD"
    assert dest.name == "iter-0-abc-123.jsonl"
    body_lines = dest.read_text(encoding="utf-8").strip().split("\n")
    assert json.loads(body_lines[0]) == {"cwd": str(repo)}
    assert json.loads(body_lines[1]) == {"text": "hello"}
    assert src.exists()  # source not deleted


def test_path_rewriting_for_sandboxed_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "host_repo"
    repo.mkdir()
    sandbox_cwd = Path("/workspace")
    # Slug for /workspace
    src = _write_source(
        home, slug="-workspace", session_id="def-456",
        lines=[
            {"cwd": "/workspace"},
            {"tool_input": {"file_path": "/workspace/src/x.py"}},
        ],
    )
    dest = capture_session(
        session_id="def-456",
        sandbox_cwd=sandbox_cwd,
        host_repo_path=repo,
        branch="feat/x",
        iteration=2,
        home=home,
    )
    body_lines = dest.read_text(encoding="utf-8").strip().split("\n")
    assert json.loads(body_lines[0]) == {"cwd": str(repo)}
    assert json.loads(body_lines[1]) == {"tool_input": {"file_path": str(repo) + "/src/x.py"}}
    # Branch sanitization: "feat/x" -> "feat-x"
    assert dest.parent == repo / ".eden" / "sessions" / "feat-x"
    assert src.exists()


def test_missing_source_raises(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(SessionCaptureFailed) as excinfo:
        capture_session(
            session_id="missing",
            sandbox_cwd=repo,
            host_repo_path=repo,
            branch="HEAD",
            iteration=0,
            home=home,
        )
    assert excinfo.value.code == "session.capture_failed"
    assert "missing" in excinfo.value.message


def test_dest_dir_created(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_source(
        home, slug=str(repo).replace("/", "-").replace("\\", "-").lstrip("-"),
        session_id="z",
        lines=[{}],
    )
    # .eden/sessions/HEAD does not exist yet
    dest = capture_session(
        session_id="z",
        sandbox_cwd=repo,
        host_repo_path=repo,
        branch="HEAD",
        iteration=9,
        home=home,
    )
    assert dest.parent.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_session_store.py -v`
Expected: FAIL — `capture_session` not exported.

- [ ] **Step 3: Implement write_session_copy**

Create `eden/session/_store.py`:

```python
"""Read a Claude Code session JSONL and write a path-rewritten copy."""

from __future__ import annotations

from pathlib import Path

from eden.session._encode import rewrite_paths


def write_session_copy(
    *,
    src: Path,
    dest: Path,
    sandbox_prefix: str,
    host_prefix: str,
) -> None:
    """Read ``src`` line by line, run ``rewrite_paths`` on each line, write to ``dest``.

    ``dest``'s parent directory is created if missing. Empty lines are
    preserved verbatim. Lines that don't parse as JSON pass through unchanged.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8") as fp_in, dest.open("w", encoding="utf-8") as fp_out:
        for raw in fp_in:
            line = raw.rstrip("\n")
            if not line:
                fp_out.write(raw)
                continue
            rewritten = rewrite_paths(
                line,
                sandbox_prefix=sandbox_prefix,
                host_prefix=host_prefix,
            )
            fp_out.write(rewritten + "\n")
```

- [ ] **Step 4: Implement capture_session in `eden/session/__init__.py`**

Replace contents of `eden/session/__init__.py`:

```python
"""Session JSONL capture: locate Claude Code's transcript, copy + rewrite paths."""

from __future__ import annotations

import re
from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.session._slug import claude_projects_slug
from eden.session._store import write_session_copy

# Mirrors eden.logging._file._BRANCH_SANITIZE for consistency.
_BRANCH_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")
_BRANCH_MAX = 64


def _sanitize_branch(branch: str) -> str:
    safe = _BRANCH_SANITIZE.sub("-", branch).strip("-")
    if not safe:
        safe = "run"
    if len(safe) > _BRANCH_MAX:
        safe = safe[:_BRANCH_MAX]
    return safe


def capture_session(
    *,
    session_id: str,
    sandbox_cwd: Path,
    host_repo_path: Path,
    branch: str,
    iteration: int,
    home: Path | None = None,
) -> Path:
    """Locate ``~/.claude/projects/<slug>/<session_id>.jsonl`` and copy it to
    ``<host_repo_path>/.eden/sessions/<sanitized-branch>/iter-<iteration>-<session_id>.jsonl``,
    rewriting absolute paths from ``str(sandbox_cwd)`` -> ``str(host_repo_path)``.

    Returns the destination path. Raises ``SessionCaptureFailed`` on any failure.
    """
    home_path = home if home is not None else Path.home()
    slug = claude_projects_slug(sandbox_cwd)
    src = home_path / ".claude" / "projects" / slug / f"{session_id}.jsonl"
    if not src.is_file():
        raise SessionCaptureFailed(
            message=f"Claude Code session JSONL not found at {src}",
            hint="check that Claude Code wrote a session file for the slug",
        )
    safe_branch = _sanitize_branch(branch)
    dest = (
        host_repo_path
        / ".eden"
        / "sessions"
        / safe_branch
        / f"iter-{iteration}-{session_id}.jsonl"
    )
    try:
        write_session_copy(
            src=src,
            dest=dest,
            sandbox_prefix=str(sandbox_cwd),
            host_prefix=str(host_repo_path),
        )
    except OSError as exc:
        raise SessionCaptureFailed(
            message=f"failed to write session copy to {dest}: {exc}",
            cause=exc,
        ) from exc
    return dest


__all__ = ["capture_session"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_session_store.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 6: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/session tests/unit/test_session_store.py && \
.venv/bin/ruff format eden/session/_store.py eden/session/__init__.py tests/unit/test_session_store.py && \
.venv/bin/ruff format --check eden/session/_store.py eden/session/__init__.py tests/unit/test_session_store.py && \
.venv/bin/ruff check --fix eden/session/_store.py eden/session/__init__.py tests/unit/test_session_store.py && \
.venv/bin/ruff check eden/session/_store.py eden/session/__init__.py tests/unit/test_session_store.py
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add eden/session/_store.py eden/session/__init__.py tests/unit/test_session_store.py
git commit -m "feat(session): add capture_session + write_session_copy"
```

---

## Task 6: Claude Code argv builder

**Files:**
- Create: `eden/agents/claude_code/__init__.py` (placeholder; expanded in Task 9)
- Create: `eden/agents/claude_code/_argv.py`
- Create: `tests/unit/test_claude_code_argv.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_claude_code_argv.py`:

```python
"""Verify the Claude Code argv builder."""

from __future__ import annotations

import pytest

from eden.agents.claude_code._argv import build_argv

pytestmark = pytest.mark.unit


def test_minimal_argv() -> None:
    argv = build_argv(model="claude-opus-4-7", effort=None, prompt="hi", extra_args=())
    assert argv == [
        "claude",
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        "claude-opus-4-7",
        "--",
        "hi",
    ]


def test_effort_threaded() -> None:
    argv = build_argv(model="m", effort="high", prompt="p", extra_args=())
    assert "--thinking-effort" in argv
    idx = argv.index("--thinking-effort")
    assert argv[idx + 1] == "high"


def test_extra_args_appended_before_double_dash() -> None:
    argv = build_argv(
        model="m", effort=None, prompt="p",
        extra_args=("--allowed-tools", "Read,Write"),
    )
    # extras come before the prompt-separator
    assert argv[-3:] == ["--allowed-tools", "Read,Write", "--", "p"] or argv[-2:] == ["--", "p"]
    # The exact constraint we verify:
    dd = argv.index("--")
    assert argv[dd + 1] == "p"
    assert "Read,Write" in argv
    assert argv.index("Read,Write") < dd


def test_prompt_with_metacharacters_passed_unescaped() -> None:
    """The prompt is a positional argv element; subprocess does no shell parsing."""
    argv = build_argv(model="m", effort=None, prompt="echo $PWD; rm -rf /", extra_args=())
    assert argv[-1] == "echo $PWD; rm -rf /"


def test_default_argv_does_not_include_thinking_effort() -> None:
    argv = build_argv(model="m", effort=None, prompt="p", extra_args=())
    assert "--thinking-effort" not in argv
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_claude_code_argv.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement build_argv**

Create `eden/agents/claude_code/_argv.py`:

```python
"""argv builder for `claude --print --output-format stream-json --verbose ...`."""

from __future__ import annotations

from typing import Literal

_BASE: tuple[str, ...] = (
    "claude",
    "--print",
    "--output-format",
    "stream-json",
    "--verbose",
)


def build_argv(
    *,
    model: str,
    effort: Literal["low", "medium", "high"] | None,
    prompt: str,
    extra_args: tuple[str, ...],
) -> list[str]:
    """Return the argv vector for a single Claude Code invocation.

    The prompt is appended as a positional argument after `--` so the shell
    does no parsing of its content.
    """
    argv: list[str] = [*_BASE, "--model", model]
    if effort is not None:
        argv.extend(["--thinking-effort", effort])
    argv.extend(extra_args)
    argv.extend(["--", prompt])
    return argv
```

- [ ] **Step 4: Stub the package init**

Create `eden/agents/claude_code/__init__.py`:

```python
"""Claude Code agent package. (Public claude_code() factory added in task 8.)"""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_claude_code_argv.py -v`
Expected: PASS — 5 tests.

- [ ] **Step 6: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/agents/claude_code tests/unit/test_claude_code_argv.py && \
.venv/bin/ruff format eden/agents/claude_code/_argv.py eden/agents/claude_code/__init__.py tests/unit/test_claude_code_argv.py && \
.venv/bin/ruff format --check eden/agents/claude_code/_argv.py eden/agents/claude_code/__init__.py tests/unit/test_claude_code_argv.py && \
.venv/bin/ruff check --fix eden/agents/claude_code/_argv.py eden/agents/claude_code/__init__.py tests/unit/test_claude_code_argv.py && \
.venv/bin/ruff check eden/agents/claude_code/_argv.py eden/agents/claude_code/__init__.py tests/unit/test_claude_code_argv.py
```
Expected: All clean.

- [ ] **Step 7: Commit**

```bash
git add eden/agents/claude_code/_argv.py eden/agents/claude_code/__init__.py tests/unit/test_claude_code_argv.py
git commit -m "feat(claude_code): add argv builder"
```

---

## Task 7: Claude Code stream-json parser

**Files:**
- Create: `eden/agents/claude_code/_stream.py`
- Create: `tests/unit/test_claude_code_stream.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_claude_code_stream.py`:

```python
"""Verify parse_line maps stream-json shapes to StreamEvent kinds."""

from __future__ import annotations

import json

import pytest

from eden.agents.claude_code._stream import parse_line

pytestmark = pytest.mark.unit


def _parse(obj: dict) -> object:
    return parse_line(json.dumps(obj), agent_name="claude-code", iteration=0)


def test_system_init_returns_none() -> None:
    assert _parse({"type": "system", "subtype": "init"}) is None


def test_assistant_text_block_returns_text_event() -> None:
    ev = _parse({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "hello world"}]},
    })
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hello world"


def test_assistant_tool_use_block_returns_tool_call() -> None:
    ev = _parse({
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Read", "input": {"path": "/x"}},
            ],
        },
    })
    assert ev is not None
    assert ev.type == "tool_call"
    assert ev.tool_name == "Read"
    assert ev.tool_input == {"path": "/x"}


def test_assistant_thinking_block_returns_none() -> None:
    assert _parse({
        "type": "assistant",
        "message": {"content": [{"type": "thinking", "thinking": "..."}]},
    }) is None


def test_user_tool_result_returns_none() -> None:
    assert _parse({
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": "..."}]},
    }) is None


def test_result_returns_usage_event() -> None:
    ev = _parse({
        "type": "result",
        "session_id": "abc-123",
        "usage": {
            "input_tokens": 10,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens": 20,
        },
    })
    assert ev is not None
    assert ev.type == "usage"
    assert ev.session_id == "abc-123"
    assert ev.usage is not None
    assert ev.usage.input_tokens == 10
    assert ev.usage.output_tokens == 20


def test_malformed_json_returns_none() -> None:
    assert parse_line("not json {", agent_name="claude-code", iteration=0) is None


def test_assistant_multi_block_returns_first_text_only() -> None:
    """When an assistant message has multiple content blocks, we surface the
    first text block (subsequent blocks would arrive as future stream-json
    lines from Claude Code in practice)."""
    ev = _parse({
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "first"},
                {"type": "text", "text": "second"},
            ],
        },
    })
    assert ev is not None
    assert ev.text == "first"


def test_unknown_top_level_type_returns_none() -> None:
    assert _parse({"type": "future_kind"}) is None


def test_result_without_usage_returns_none() -> None:
    """A result line missing the usage field is treated as unparseable
    (Claude Code always includes usage; if missing, drop the line)."""
    assert _parse({"type": "result", "session_id": "x"}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_claude_code_stream.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement parse_line**

Create `eden/agents/claude_code/_stream.py`:

```python
"""Parse one stream-json line emitted by `claude --output-format stream-json --verbose`."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from eden._types import Usage
from eden.streaming import StreamEvent


def parse_line(line: str, *, agent_name: str, iteration: int) -> StreamEvent | None:
    """Decode one stream-json line and return a StreamEvent.

    Returns:
        - StreamEvent(type="text", ...) for assistant text blocks (first one wins).
        - StreamEvent(type="tool_call", ...) for assistant tool_use blocks.
        - StreamEvent(type="usage", ...) for the final result line (must carry usage).
        - None for system / user / thinking / unknown / malformed lines.
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    kind = obj.get("type")
    now = datetime.now(UTC)
    if kind == "assistant":
        return _parse_assistant(obj, agent_name=agent_name, iteration=iteration, now=now)
    if kind == "result":
        return _parse_result(obj, agent_name=agent_name, iteration=iteration, now=now)
    return None


def _parse_assistant(
    obj: dict[str, Any],
    *,
    agent_name: str,
    iteration: int,
    now: datetime,
) -> StreamEvent | None:
    message = obj.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str):
                return StreamEvent(
                    type="text",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=now,
                    text=text,
                )
        elif block_type == "tool_use":
            name = block.get("name")
            tool_input = block.get("input")
            if isinstance(name, str) and isinstance(tool_input, dict):
                return StreamEvent(
                    type="tool_call",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=now,
                    tool_name=name,
                    tool_input=tool_input,
                )
    return None


def _parse_result(
    obj: dict[str, Any],
    *,
    agent_name: str,
    iteration: int,
    now: datetime,
) -> StreamEvent | None:
    session_id = obj.get("session_id")
    raw_usage = obj.get("usage")
    if not isinstance(session_id, str) or not isinstance(raw_usage, dict):
        return None
    try:
        usage = Usage(
            input_tokens=int(raw_usage.get("input_tokens", 0)),
            cache_creation_input_tokens=int(raw_usage.get("cache_creation_input_tokens", 0)),
            cache_read_input_tokens=int(raw_usage.get("cache_read_input_tokens", 0)),
            output_tokens=int(raw_usage.get("output_tokens", 0)),
        )
    except (TypeError, ValueError):
        return None
    return StreamEvent(
        type="usage",
        agent_name=agent_name,
        iteration=iteration,
        timestamp=now,
        usage=usage,
        session_id=session_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_claude_code_stream.py -v`
Expected: PASS — 10 tests.

- [ ] **Step 5: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/agents/claude_code tests/unit/test_claude_code_stream.py && \
.venv/bin/ruff format eden/agents/claude_code/_stream.py tests/unit/test_claude_code_stream.py && \
.venv/bin/ruff format --check eden/agents/claude_code/_stream.py tests/unit/test_claude_code_stream.py && \
.venv/bin/ruff check --fix eden/agents/claude_code/_stream.py tests/unit/test_claude_code_stream.py && \
.venv/bin/ruff check eden/agents/claude_code/_stream.py tests/unit/test_claude_code_stream.py
```
Expected: All clean.

- [ ] **Step 6: Commit**

```bash
git add eden/agents/claude_code/_stream.py tests/unit/test_claude_code_stream.py
git commit -m "feat(claude_code): add stream-json line parser"
```

---

## Task 8: `_ClaudeCodeAgent` dataclass + public `claude_code()` factory

**Files:**
- Create: `eden/agents/claude_code/_agent.py`
- Modify: `eden/agents/claude_code/__init__.py`
- Modify: `eden/agents/__init__.py`
- Create: `tests/unit/test_claude_code_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_claude_code_agent.py`:

```python
"""Verify the claude_code() factory produces an Agent that satisfies the Protocol."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import Agent, IterationContext, claude_code
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


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


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


def test_default_metadata() -> None:
    a = claude_code(model="claude-opus-4-7")
    assert a.name == "claude-code"
    assert a.model == "claude-opus-4-7"
    assert isinstance(a, Agent)


def test_custom_name() -> None:
    a = claude_code(model="m", name="my-agent")
    assert a.name == "my-agent"


def test_captures_sessions_default_true() -> None:
    a = claude_code(model="m")
    assert a.captures_sessions is True


def test_captures_sessions_false_overrides() -> None:
    a = claude_code(model="m", capture_sessions=False)
    assert a.captures_sessions is False


def test_build_command_returns_argv_with_prompt() -> None:
    a = claude_code(model="m")
    argv = a.build_command(_ctx(prompt="hi"))
    assert argv[0] == "claude"
    assert "stream-json" in argv
    assert argv[-1] == "hi"
    assert argv[-2] == "--"


def test_build_command_with_effort_includes_thinking_effort() -> None:
    a = claude_code(model="m", effort="high")
    argv = a.build_command(_ctx())
    assert "--thinking-effort" in argv


def test_parse_stream_returns_text_for_assistant_block() -> None:
    a = claude_code(model="m")
    line = json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "hi"}]},
    })
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hi"
    assert ev.agent_name == "claude-code"


def test_parse_stream_returns_none_for_system() -> None:
    a = claude_code(model="m")
    assert a.parse_stream(json.dumps({"type": "system", "subtype": "init"})) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_claude_code_agent.py -v`
Expected: FAIL — `claude_code` not exported.

- [ ] **Step 3: Implement `_ClaudeCodeAgent`**

Create `eden/agents/claude_code/_agent.py`:

```python
"""_ClaudeCodeAgent dataclass — implements the Agent Protocol structurally."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from eden.agents._context import IterationContext
from eden.agents.claude_code._argv import build_argv
from eden.agents.claude_code._stream import parse_line
from eden.streaming import StreamEvent


@dataclass(frozen=True)
class _ClaudeCodeAgent:
    name: str
    model: str
    captures_sessions: bool
    _effort: Literal["low", "medium", "high"] | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()

    def build_command(self, ctx: IterationContext) -> list[str]:
        return build_argv(
            model=self.model,
            effort=self._effort,
            prompt=ctx.prompt,
            extra_args=self._extra_args,
        )

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)
```

Note: `parse_stream` passes `iteration=0` to `parse_line`. The Agent Protocol's `parse_stream(line)` signature does not carry the iteration index, so the parser cannot know the real value. The orchestrator (Task 10) corrects this by wrapping every non-None parsed event with `dataclasses.replace(parsed, iteration=i, agent_name=agent.name)` before emitting — so callers consuming `on_event` and lines written to the log sink always see the correct iteration. The parser's emitted `iteration` field is informational only; the orchestrator overwrites it.

- [ ] **Step 4: Implement the public factory**

Replace contents of `eden/agents/claude_code/__init__.py`:

```python
"""Public factory for the Claude Code-backed Agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from eden.agents._protocol import Agent
from eden.agents.claude_code._agent import _ClaudeCodeAgent


def claude_code(
    model: str,
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """Build a Claude Code-backed Agent.

    Args:
        model: Claude model id (threaded into ``--model``).
        name: Agent identifier (default ``"claude-code"``).
        effort: Optional ``--thinking-effort`` level.
        env: Per-agent environment additions (merged by the orchestrator).
        capture_sessions: When ``True``, the orchestrator post-processes each
            iteration's session JSONL into ``.eden/sessions/...``.
        extra_args: Escape hatch for unsurfaced Claude CLI flags. Inserted
            before the ``--`` prompt separator.
    """
    return _ClaudeCodeAgent(
        name=name,
        model=model,
        captures_sessions=capture_sessions,
        _effort=effort,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
    )


__all__ = ["claude_code"]
```

- [ ] **Step 5: Re-export from `eden/agents/__init__.py`**

Replace contents of `eden/agents/__init__.py`:

```python
"""Agent factories + Protocol."""

from __future__ import annotations

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.claude_code import claude_code
from eden.agents.simulated import simulated_agent

__all__ = ["Agent", "IterationContext", "claude_code", "simulated_agent"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_claude_code_agent.py -v`
Expected: PASS — 8 tests.

- [ ] **Step 7: Pre-existing simulated_agent tests still pass**

Run: `.venv/bin/pytest tests/unit/test_simulated_agent.py -v`
Expected: PASS (8 tests).

- [ ] **Step 8: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/agents tests/unit/test_claude_code_agent.py && \
.venv/bin/ruff format eden/agents/claude_code/_agent.py eden/agents/claude_code/__init__.py eden/agents/__init__.py tests/unit/test_claude_code_agent.py && \
.venv/bin/ruff format --check eden/agents/claude_code/_agent.py eden/agents/claude_code/__init__.py eden/agents/__init__.py tests/unit/test_claude_code_agent.py && \
.venv/bin/ruff check --fix eden/agents/claude_code/_agent.py eden/agents/claude_code/__init__.py eden/agents/__init__.py tests/unit/test_claude_code_agent.py && \
.venv/bin/ruff check eden/agents/claude_code/_agent.py eden/agents/claude_code/__init__.py eden/agents/__init__.py tests/unit/test_claude_code_agent.py
```
Expected: All clean.

- [ ] **Step 9: Commit**

```bash
git add eden/agents/claude_code/_agent.py eden/agents/claude_code/__init__.py eden/agents/__init__.py tests/unit/test_claude_code_agent.py
git commit -m "feat(claude_code): add _ClaudeCodeAgent + public claude_code() factory"
```

---

## Task 9: Extend `assemble()` to accept session/usage fields

**Files:**
- Modify: `eden/orchestrator/_result.py`

(No new test file — `assemble()` is internal; it's exercised via `_run_loop` tests in Task 10.)

- [ ] **Step 1: Replace contents of `eden/orchestrator/_result.py`**

```python
"""Assemble RunResult from orchestrator state."""

from __future__ import annotations

from pathlib import Path

from eden._types import Iteration, RunResult, Usage


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
    session_id: str | None,
    session_file_path: Path | None,
    usage: Usage | None,
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
        session_id=session_id,
        session_file_path=session_file_path,
        usage=usage,
    )
```

The `assemble()` signature now requires `session_id`, `session_file_path`, `usage`. Task 10 updates the lone caller in `_loop.py`.

- [ ] **Step 2: Verify the existing run-loop tests still pass after the signature change**

Run: `.venv/bin/pytest tests/unit/test_run_loop.py -v`
Expected: FAIL — `_loop.py`'s call to `assemble(...)` is missing the three new kwargs. This is intentional: Task 10 fixes it.

- [ ] **Step 3: Commit (broken state — Task 10 follows immediately)**

```bash
git add eden/orchestrator/_result.py
git commit -m "feat(orchestrator): extend assemble() with session/usage args"
```

This commit deliberately leaves `_run_loop` calling `assemble(...)` with insufficient kwargs. The next task fixes the call site and adds the new behavior. Atomicity is preserved by Task 10 landing immediately after.

---

## Task 10: Wire session capture into `_run_loop`

**Files:**
- Modify: `eden/orchestrator/_loop.py`
- Modify: `tests/unit/test_run_loop.py` (extend with capture-aware test)

- [ ] **Step 1: Replace contents of `eden/orchestrator/_loop.py`**

```python
"""Orchestrator iteration loop driver."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from eden._types import Iteration, RunResult, Timeouts, Usage
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.errors import SessionCaptureFailed
from eden.lifecycle import HookPhase, Hooks
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
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes.errors import UnsupportedStrategy
from eden.session import capture_session
from eden.streaming import StreamEvent
from eden.worktree._create import create_worktree


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _claude_projects_mount() -> tuple[Mount, ...]:
    """Inject ~/.claude/projects/ → /root/.claude/projects/ when the agent
    needs session capture inside a containerized sandbox.

    no_sandbox ignores the mount; docker honors it. If ~/.claude/projects/
    doesn't exist on the host yet, return () — Claude Code will create it
    on first use, but Eden cannot mount a non-existent path.
    """
    host_dir = Path.home() / ".claude" / "projects"
    if not host_dir.exists():
        return ()
    return (Mount(host=host_dir, sandbox=Path("/root/.claude/projects")),)


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

    captures = bool(getattr(agent, "captures_sessions", False))
    extra_mounts: tuple[Mount, ...] = _claude_projects_mount() if captures else ()

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
            mounts=extra_mounts,
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
            iter_session_id: str | None = None
            iter_usage: Usage | None = None
            iter_session_file: Path | None = None

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
                    def _emit_warning(minutes: int, _i: int = i) -> None:
                        ev = StreamEvent(
                            type="idle_warning", agent_name=agent.name,
                            iteration=_i, timestamp=_utcnow(), minutes_idle=minutes,
                        )
                        if sink is not None:
                            sink.write(ev)
                        if on_event is not None:
                            on_event(ev)

                    for line in runner.iter_lines(signal=signal, on_warning=_emit_warning):
                        stdout_chunks.append(line + "\n")
                        parsed = agent.parse_stream(line)
                        if parsed is not None:
                            # Parser doesn't know the real iteration; rewrap.
                            ev = replace(parsed, iteration=i, agent_name=agent.name)
                        else:
                            ev = StreamEvent(
                                type="text", agent_name=agent.name,
                                iteration=i, timestamp=_utcnow(), text=line,
                            )
                        if ev.type == "usage":
                            iter_session_id = ev.session_id
                            iter_usage = ev.usage
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

            if iter_session_id is not None and captures:
                try:
                    iter_session_file = capture_session(
                        session_id=iter_session_id,
                        sandbox_cwd=handle.worktree_path,
                        host_repo_path=setup.cwd,
                        branch=wt.branch,
                        iteration=i,
                    )
                except SessionCaptureFailed as exc:
                    if sink is not None:
                        sink.write(StreamEvent(
                            type="text", agent_name=agent.name, iteration=i,
                            timestamp=_utcnow(),
                            text=f"[eden] session capture failed: {exc}",
                        ))

            run_sandbox_hooks(
                phase=HookPhase.OnIterationEnd, hooks=hooks.sandbox,
                handle=handle, env=setup.merged_env, timeouts=timeouts,
            )
            run_host_hooks(
                phase=HookPhase.OnIterationEnd, hooks=hooks.host,
                worktree_path=wt.worktree_path, env=setup.merged_env, timeouts=timeouts,
            )

            iterations.append(Iteration(
                index=i,
                completion_signal=iter_completion,
                session_id=iter_session_id,
                session_file_path=iter_session_file,
                usage=iter_usage,
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

    last = iterations[-1] if iterations else None
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
        session_id=last.session_id if last else None,
        session_file_path=last.session_file_path if last else None,
        usage=last.usage if last else None,
    )


__all__ = ["_run_loop"]
```

- [ ] **Step 2: Run pre-existing run-loop tests**

Run: `.venv/bin/pytest tests/unit/test_run_loop.py -v`
Expected: PASS — all 5 existing tests (no behavior change for `simulated_agent` callers).

- [ ] **Step 3: Add a capture-aware test**

Append to `tests/unit/test_run_loop.py`:

```python


def test_run_loop_simulated_agent_does_not_capture(tmp_git_repo: Path) -> None:
    """simulated_agent has no captures_sessions attr → capture skipped → result.session_id is None."""
    agent = simulated_agent(output="hello\n<promise>COMPLETE</promise>\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    result = _run_loop(
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
        on_event=None,
        logging_cfg=None,
        signal=ctrl.signal,
        prompt_args=None,
    )
    assert result.session_id is None
    assert result.session_file_path is None
    assert result.usage is None
    assert result.iterations[0].session_id is None
    assert result.iterations[0].session_file_path is None
    assert result.iterations[0].usage is None
```

- [ ] **Step 4: Run the extended test file**

Run: `.venv/bin/pytest tests/unit/test_run_loop.py -v`
Expected: PASS — 6 tests.

- [ ] **Step 5: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden/orchestrator tests/unit/test_run_loop.py && \
.venv/bin/ruff format eden/orchestrator/_loop.py tests/unit/test_run_loop.py && \
.venv/bin/ruff format --check eden/orchestrator/_loop.py tests/unit/test_run_loop.py && \
.venv/bin/ruff check --fix eden/orchestrator/_loop.py tests/unit/test_run_loop.py && \
.venv/bin/ruff check eden/orchestrator/_loop.py tests/unit/test_run_loop.py
```
Expected: All clean.

- [ ] **Step 6: Commit**

```bash
git add eden/orchestrator/_loop.py tests/unit/test_run_loop.py
git commit -m "feat(orchestrator): wire session capture + populate session/usage fields"
```

---

## Task 11: Top-level public re-exports

**Files:**
- Modify: `eden/__init__.py`

- [ ] **Step 1: Add `claude_code` and `SessionCaptureFailed` to top-level exports**

Edit `eden/__init__.py`:

1. Add to the `from eden.agents import ...` line: include `claude_code`. Final form:
   ```python
   from eden.agents import Agent, IterationContext, claude_code, simulated_agent
   ```
2. Add `SessionCaptureFailed` to the `from eden.errors import (...)` block (alphabetical position between `PromptError` and `StepTimeout`):
   ```python
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
       SessionCaptureFailed,
       StepTimeout,
   )
   ```
3. Add `"claude_code"` and `"SessionCaptureFailed"` to `__all__`. The exact list (alphabetical, ruff-sorted in 3a) becomes:
   ```python
   __all__ = [
       "Aborted",
       "AbortController",
       "AbortSignal",
       "Agent",
       "BranchStrategy",
       "ConfigError",
       "CwdError",
       "Commit",
       "EdenError",
       "EdenTimeoutError",
       "EnvMergeError",
       "Hook",
       "HookError",
       "HookFailed",
       "HookPhase",
       "HookTimeout",
       "Hooks",
       "HostHooks",
       "IdleTimeout",
       "InvalidOptions",
       "Iteration",
       "IterationContext",
       "Logging",
       "Mount",
       "PromptError",
       "RunResult",
       "SandboxHooks",
       "SessionCaptureFailed",
       "StepTimeout",
       "StreamEvent",
       "Timeouts",
       "Usage",
       "__version__",
       "claude_code",
       "create_worktree",
       "run",
       "simulated_agent",
   ]
   ```

(Let ruff RUF022 sort if it disagrees on order — the unsafe-fix is the same one Phase 3a accepted.)

- [ ] **Step 2: Verify imports**

Run:
```bash
.venv/bin/python -c "import eden; assert eden.claude_code is not None; assert eden.SessionCaptureFailed is not None; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Run full unit suite (regression check)**

Run: `.venv/bin/pytest -m "unit or e2e" --no-cov -q`
Expected: All tests pass; total count = 241 (3a baseline) + 41 (this plan's new tests through Task 10) = ~282.

- [ ] **Step 4: mypy + ruff**

Run:
```bash
.venv/bin/mypy eden && \
.venv/bin/ruff format eden/__init__.py && \
.venv/bin/ruff format --check eden/__init__.py && \
.venv/bin/ruff check --fix eden/__init__.py && \
.venv/bin/ruff check eden/__init__.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
git add eden/__init__.py
git commit -m "feat(orchestrator): re-export claude_code + SessionCaptureFailed at package root"
```

---

## Task 12: Fake-claude shim for e2e tests

**Files:**
- Create: `tests/_fake_claude/__init__.py`
- Create: `tests/_fake_claude/_transcript.py`

(No standalone tests; the shim is exercised by Task 13's e2e test.)

- [ ] **Step 1: Implement Transcript builder**

Create `tests/_fake_claude/_transcript.py`:

```python
"""Builder for stream-json transcripts used by the fake claude shim."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Transcript:
    _lines: list[dict] = field(default_factory=list)

    def system_init(self) -> "Transcript":
        self._lines.append({"type": "system", "subtype": "init"})
        return self

    def text(self, text: str) -> "Transcript":
        self._lines.append({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": text}]},
        })
        return self

    def tool(self, name: str, tool_input: dict) -> "Transcript":
        self._lines.append({
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": name, "input": tool_input},
                ],
            },
        })
        return self

    def result(
        self,
        *,
        session_id: str,
        input_tokens: int = 10,
        output_tokens: int = 20,
    ) -> "Transcript":
        self._lines.append({
            "type": "result",
            "session_id": session_id,
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": output_tokens,
            },
        })
        return self

    def stream_json_lines(self) -> list[str]:
        return [json.dumps(line) for line in self._lines]

    def session_jsonl_body(self, *, sandbox_cwd: str) -> str:
        """The contents Claude Code writes to ~/.claude/projects/<slug>/<id>.jsonl.

        For the shim, we mirror only the bits Eden's rewriter cares about: a
        cwd line plus a tool_input line containing a sandbox-prefixed path.
        """
        body = [
            {"cwd": sandbox_cwd},
            {"tool_input": {"file_path": f"{sandbox_cwd}/src/x.py"}},
        ]
        return "\n".join(json.dumps(b) for b in body) + "\n"
```

- [ ] **Step 2: Implement the shim installer**

Create `tests/_fake_claude/__init__.py`:

```python
"""Install a fake `claude` executable for e2e tests."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from tests._fake_claude._transcript import Transcript


def install_fake_claude(
    *,
    tmp_dir: Path,
    transcript: Transcript,
    session_id: str,
    sandbox_cwd: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Write a Python script named `claude` to ``tmp_dir`` and prepend its
    parent directory to PATH. Override $HOME (and USERPROFILE on Windows) to
    a fresh tmp tree.

    Side effects:
        - Writes the executable to <tmp_dir>/bin/claude (no extension).
        - Writes a session JSONL to <tmp_dir>/home/.claude/projects/<slug>/<id>.jsonl.
        - Sets $PATH to put <tmp_dir>/bin first.
        - Sets $HOME (and USERPROFILE) to <tmp_dir>/home.

    Returns the home dir Path so callers can introspect the captured file.
    """
    bin_dir = tmp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_dir / "home"
    home_dir.mkdir(parents=True, exist_ok=True)

    # Pre-write the Claude session JSONL the shim will reference.
    slug = sandbox_cwd.replace("/", "-").replace("\\", "-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.rstrip("-")
    session_dir = home_dir / ".claude" / "projects" / slug
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"{session_id}.jsonl"
    session_file.write_text(
        transcript.session_jsonl_body(sandbox_cwd=sandbox_cwd),
        encoding="utf-8",
    )

    # Stream-json lines emitted by the shim, in order.
    lines = transcript.stream_json_lines()
    script_path = bin_dir / "claude"
    script_path.write_text(
        "\n".join([
            f"#!{sys.executable}",
            "import sys, time",
            "lines = " + repr(lines),
            "for line in lines:",
            "    sys.stdout.write(line + '\\n')",
            "    sys.stdout.flush()",
            "    time.sleep(0.01)",
        ]) + "\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))

    return home_dir


__all__ = ["Transcript", "install_fake_claude"]
```

Note for Windows: the shebang line and `chmod +x` don't matter on Windows; what matters is that `claude` is found via PATH. On Windows, Python won't run a file named `claude` directly without an extension. For 3b, the e2e test that uses this shim is gated to Linux + macOS by checking `sys.platform != "win32"`, with a `@pytest.mark.skipif` on the test (Windows users still get the unit suite; the e2e is platform-restricted because the shim mechanism can't satisfy Windows's PATHEXT model without more plumbing).

- [ ] **Step 3: Verify the shim imports clean**

Run: `.venv/bin/python -c "from tests._fake_claude import install_fake_claude, Transcript; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: mypy + ruff**

Run:
```bash
.venv/bin/mypy tests/_fake_claude && \
.venv/bin/ruff format tests/_fake_claude/__init__.py tests/_fake_claude/_transcript.py && \
.venv/bin/ruff format --check tests/_fake_claude/__init__.py tests/_fake_claude/_transcript.py && \
.venv/bin/ruff check --fix tests/_fake_claude/__init__.py tests/_fake_claude/_transcript.py && \
.venv/bin/ruff check tests/_fake_claude/__init__.py tests/_fake_claude/_transcript.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
git add tests/_fake_claude/__init__.py tests/_fake_claude/_transcript.py
git commit -m "test: add fake-claude shim for phase 3b e2e tests"
```

---

## Task 13: Claude Code e2e smoke test

**Files:**
- Create: `tests/e2e/test_claude_code_smoke.py`

- [ ] **Step 1: Write the e2e test**

Create `tests/e2e/test_claude_code_smoke.py`:

```python
"""Smoke E2E: claude_code agent + no_sandbox + session capture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import eden
from tests._fake_claude import Transcript, install_fake_claude

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-claude shim relies on POSIX-style executable PATH lookup",
)
def test_claude_code_full_run(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = (
        Transcript()
        .system_init()
        .text("working on it")
        .tool("Read", {"path": "/workspace/src/x.py"})
        .text("<promise>COMPLETE</promise>")
        .result(session_id="test-session-abc", input_tokens=12, output_tokens=34)
    )
    home = install_fake_claude(
        tmp_dir=tmp_path / "fake_claude",
        transcript=transcript,
        session_id="test-session-abc",
        sandbox_cwd=str(e2e_git_repo),  # no_sandbox: sandbox_cwd == host_repo_path
        monkeypatch=monkeypatch,
    )

    events: list[eden.StreamEvent] = []
    result = eden.run(
        agent=eden.claude_code(model="test-model"),
        sandbox=__import__(
            "eden.sandboxes.no_sandbox", fromlist=["provider"],
        ).provider(),
        prompt="please complete the task",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        on_event=events.append,
    )

    # Completion fired
    assert result.completion_signal == "<promise>COMPLETE</promise>"

    # Session metadata populated from the result line
    assert result.session_id == "test-session-abc"
    assert result.usage is not None
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 34
    assert result.iterations[0].session_id == "test-session-abc"
    assert result.iterations[0].usage is not None

    # Session file copied + path-rewritten
    assert result.session_file_path is not None
    assert result.session_file_path.exists()
    assert result.session_file_path.parent == e2e_git_repo / ".eden" / "sessions" / "main"
    assert result.session_file_path.name == "iter-0-test-session-abc.jsonl"
    body_lines = [
        json.loads(line)
        for line in result.session_file_path.read_text(encoding="utf-8").strip().split("\n")
    ]
    # The shim wrote {"cwd": "<sandbox_cwd>"} and {"tool_input": {"file_path": "<sandbox_cwd>/src/x.py"}};
    # in no_sandbox sandbox_cwd == host_repo_path so paths match the repo path either way.
    assert body_lines[0] == {"cwd": str(e2e_git_repo)}

    # tool_call event landed
    tool_calls = [e for e in events if e.type == "tool_call"]
    assert len(tool_calls) >= 1
    assert tool_calls[0].tool_name == "Read"

    # usage event landed (final)
    usage_events = [e for e in events if e.type == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0].session_id == "test-session-abc"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-claude shim relies on POSIX-style executable PATH lookup",
)
def test_claude_code_capture_sessions_false(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = (
        Transcript()
        .text("ok")
        .text("<promise>COMPLETE</promise>")
        .result(session_id="no-capture-id", input_tokens=1, output_tokens=2)
    )
    install_fake_claude(
        tmp_dir=tmp_path / "fake_claude",
        transcript=transcript,
        session_id="no-capture-id",
        sandbox_cwd=str(e2e_git_repo),
        monkeypatch=monkeypatch,
    )

    result = eden.run(
        agent=eden.claude_code(model="test-model", capture_sessions=False),
        sandbox=__import__(
            "eden.sandboxes.no_sandbox", fromlist=["provider"],
        ).provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
    )

    assert result.session_id == "no-capture-id"   # populated from stream
    assert result.session_file_path is None        # but no file written
    assert result.usage is not None                 # usage still populated
    # No .eden/sessions/ directory created at all
    assert not (e2e_git_repo / ".eden" / "sessions").exists()
```

- [ ] **Step 2: Run the e2e test**

Run: `.venv/bin/pytest tests/e2e/test_claude_code_smoke.py -v`
Expected: PASS — 2 tests on macOS/Linux, both skipped on Windows.

- [ ] **Step 3: Run combined unit + e2e (regression check)**

Run: `.venv/bin/pytest -m "unit or e2e" --no-cov -q`
Expected: All tests pass.

- [ ] **Step 4: mypy + ruff**

Run:
```bash
.venv/bin/mypy tests/e2e/test_claude_code_smoke.py && \
.venv/bin/ruff format tests/e2e/test_claude_code_smoke.py && \
.venv/bin/ruff format --check tests/e2e/test_claude_code_smoke.py && \
.venv/bin/ruff check --fix tests/e2e/test_claude_code_smoke.py && \
.venv/bin/ruff check tests/e2e/test_claude_code_smoke.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_claude_code_smoke.py
git commit -m "test(e2e): add claude_code smoke run via fake-claude shim"
```

---

## Task 14: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the status blockquote**

Edit `README.md:5`. Replace the existing `> **Status:** ...` line with:

```markdown
> **Status:** Pre-alpha. Phases 1–3b complete: package skeleton, provider Protocols, worktree manager, `no_sandbox` and `docker` MVP providers, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent` and `claude_code` agents, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, and Claude Code session JSONL capture. Additional providers (4), other agents (5), CLI scaffolder (6), and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: bump README status to phase 3b complete"
```

---

## Final verification (after every task is committed)

- [ ] **Step 1: Full local CI parity check**

Run:

```bash
.venv/bin/ruff format --check eden tests
.venv/bin/ruff check --no-cache eden tests
.venv/bin/mypy --strict eden tests
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```

Expected: every command Success / PASS. Coverage stays ≥ 70%.

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

Then check GitHub CI — all 9 matrix jobs (Linux/macOS/Windows × py3.11/3.12/3.13) green for both unit+e2e (Windows skips the e2e claude_code tests via `@pytest.mark.skipif`). The integration job stays Linux-only.

- [ ] **Step 3: Tag the phase**

Wait for CI green before tagging.

```bash
git tag -a phase-3b -m "Phase 3b: Claude Code agent + session JSONL capture"
git push origin phase-3b
```

---

## Notes for the implementer

- **No new threads.** Session capture runs synchronously between agent EOF and the `iterations.append(...)` call. The Phase 3a stdout-pump + idle-watchdog threading model is unchanged.
- **`captures_sessions` is an attribute, not a Protocol method.** The orchestrator reads it via `getattr(agent, "captures_sessions", False)`. Older agents (`simulated_agent`) lack the attribute → `False` → no capture. Don't extend the `Agent` Protocol in 3b — that's a 3c+ concern.
- **Soft failure on capture errors.** `SessionCaptureFailed` is caught inside the iteration loop; the run continues. The agent's stdout, log file, and prior events are unaffected.
- **String-prefix path rewrite.** `rewrite_paths` uses `startswith`, not contains. Mid-string occurrences (e.g., `"see /workspace/x for details"`) pass through unchanged. This is intentional and tested.
- **Slug derivation.** `claude_projects_slug` is the single point of truth for Claude Code's filesystem layout. If Claude Code ever changes its slug rule, only this function needs an update.
- **Docker mount injection.** The `_claude_projects_mount()` helper injects `~/.claude/projects/` into the sandbox mounts when the agent advertises `captures_sessions=True`. `no_sandbox` ignores it; `docker` honors it. Container `$HOME` is hardcoded to `/root/` per spec §3.9 — Phase 4 can refine.
- **Prompt is positional after `--`.** No shell parsing applies to prompt content (verified by `test_prompt_with_metacharacters_passed_unescaped`).
- **`parse_line` returns first text/tool block only.** Multi-block assistant messages drop subsequent blocks. In practice Claude Code emits one block per stream-json line, so this is rarely material; if it becomes a problem in 3c+, the parser can yield a list instead.
- **mypy `--strict`** must stay green across the whole tree — the `from __future__ import annotations` discipline carries through every new file.
- **Coverage gate:** stays at 70%. The Phase 3a baseline was 95.18%; Phase 3b adds ~600 LoC of source heavily tested, so total coverage should stay ≥ 90%.
- **Frequent commits.** Every task lands one or two commits. The Task 9 → Task 10 split intentionally leaves a momentarily-broken state between commits because `assemble()`'s signature changes ahead of its caller; both must be reviewed together but commit-atomicity is preserved by landing them in immediate succession.

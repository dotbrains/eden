# Eden Phase 3b — Claude Code Agent + Session JSONL Capture

**Status:** Approved design. Implementation to follow via `superpowers:writing-plans`.

**Predecessor:** Phase 3a (orchestration core). Tag: `phase-3a` (when CI green; commit `ecf5646`).

**Goal:** Add a real Claude-Code-backed `Agent` factory (`claude_code(...)`) that drops into Phase 3a's `eden.run(...)` pipeline, plus session-JSONL capture so each iteration's transcript is preserved on disk and surfaced via `Iteration.session_id` / `session_file_path` / `usage` (currently always `None` in 3a).

**Out of scope (deferred to later phases):**
- `resume_session` re-entry of prior conversations (3c+)
- `interactive(...)` TTY mode + Rich-rendered stdout sink (Phase 6)
- Other agents: `codex`, `opencode`, `pi` (Phase 5)

---

## 1. Public surface added

```python
from typing import Literal
from collections.abc import Mapping

def claude_code(
    model: str,
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """Build a Claude-Code-backed Agent."""
```

Re-exported from `eden.__init__` as `claude_code`. Joins `simulated_agent` in `eden.agents.__all__`.

**`StreamEvent.type` literal expands** from `Literal["text", "idle_warning"]` to:

```python
Literal["text", "idle_warning", "tool_call", "usage"]
```

with these new optional fields:

```python
tool_name: str | None = None        # set when type == "tool_call"
tool_input: dict[str, object] | None = None   # set when type == "tool_call"
usage: Usage | None = None          # set when type == "usage"
session_id: str | None = None       # set when type == "usage"
```

`__post_init__` extends to enforce that `tool_call` carries `tool_name` and `usage` carries `usage`. Existing `text` and `idle_warning` shape rules unchanged.

**`SessionCaptureFailed`** new error class, subclass of `EdenError`. Same `code/message/hint/cause` constructor as Phase 3a runtime errors. Default `code="session.capture_failed"`.

**`Iteration` and `RunResult`** — no shape changes. The `session_id`, `session_file_path`, and `usage` fields existed since Phase 3a but always carried `None`. Phase 3b populates them.

---

## 2. Architecture

### 2.1 New sub-packages

```
eden/
├── agents/
│   └── claude_code/                 # NEW
│       ├── __init__.py              # claude_code() factory + __all__
│       ├── _agent.py                # _ClaudeCodeAgent dataclass (Protocol-conformant)
│       ├── _argv.py                 # argv builder for `claude --print --output-format stream-json --verbose ...`
│       └── _stream.py               # parse one stream-json line → StreamEvent | None
├── session/                         # NEW
│   ├── __init__.py                  # capture_session() public helper
│   ├── _slug.py                     # claude_projects_slug(cwd)
│   ├── _store.py                    # write_session_copy(): locate + copy + cwd-rewrite
│   └── _encode.py                   # rewrite_paths(line, sandbox_prefix, host_prefix)
├── streaming/_event.py              # MODIFY — extended literal + new optional fields
├── orchestrator/_loop.py            # MODIFY — populate session_id/session_file_path/usage
├── orchestrator/_result.py          # MODIFY — assemble() takes session_id/session_file_path/usage
└── errors.py                        # MODIFY — add SessionCaptureFailed
```

Every new file stays under the project's ~300-LoC budget. The largest expected file is `_stream.py` (~150 LoC).

### 2.2 Per-iteration data flow

```
Phase 3a (unchanged):
  build_command(ctx) → argv = [claude, --print, --output-format, stream-json, --verbose, --model <m>, ...]
  _AgentRunner spawns claude
  stdout is pumped one line at a time

Phase 3b additions:
  for each line: agent.parse_stream(line) → StreamEvent of kind "text" | "tool_call" | "usage" | None
    if ev.type == "usage":
      iter_session_id = ev.session_id
      iter_usage = ev.usage
  on stream EOF (claude exits after emitting `result`):
    if capture_sessions and iter_session_id is not None:
      iter_session_file = capture_session(
          session_id=iter_session_id,
          sandbox_cwd=handle.worktree_path,
          host_repo_path=setup.cwd,
          branch=wt.branch,
          iteration=i,
      )
  iterations.append(Iteration(... session_id=..., session_file_path=..., usage=...))
```

`RunResult.session_id` / `session_file_path` / `usage` carry the **last** iteration's values (caller walks `result.iterations` for per-iteration history or aggregate sums).

### 2.3 Boundaries

- `eden.agents.claude_code.*` knows nothing about the filesystem — it only spawns processes and parses lines.
- `eden.session.*` knows nothing about agents — it locates / copies / rewrites a JSONL given `session_id` + `cwd`.
- `eden.orchestrator._loop` wires the two together at the iteration boundary, exactly as it already wires `_AgentRunner` + `IdleWatchdog`.

---

## 3. Component contracts

### 3.1 `claude_code()` factory

| Param | Type | Default | Effect |
|---|---|---|---|
| `model` | `str` | (required) | Threaded to `--model <model>` |
| `name` | `str` | `"claude-code"` | Stored on `Agent.name`; used in `StreamEvent.agent_name` |
| `effort` | `"low" \| "medium" \| "high" \| None` | `None` | If set, threaded to `--thinking-effort <effort>` |
| `env` | `Mapping[str, str] \| None` | `None` | Per-agent env additions; merged into the orchestrator's already-merged env |
| `capture_sessions` | `bool` | `True` | When `True`, post-iteration `capture_session()` runs; `False` skips it (`session_id` still populated, `session_file_path` stays `None`) |
| `extra_args` | `tuple[str, ...]` | `()` | Escape hatch for unsurfaced Claude CLI flags |

Returns an `Agent` whose `Agent.name`, `Agent.model` reflect the constructor args, and which exposes a non-Protocol attribute `captures_sessions: bool` that the orchestrator reads via `getattr(agent, "captures_sessions", False)` to decide whether to call `capture_session()`.

### 3.2 `_ClaudeCodeAgent` dataclass

```python
@dataclass(frozen=True)
class _ClaudeCodeAgent:
    name: str
    model: str
    captures_sessions: bool
    _effort: Literal["low", "medium", "high"] | None
    _env: Mapping[str, str]
    _extra_args: tuple[str, ...]

    def build_command(self, ctx: IterationContext) -> list[str]: ...   # delegates to _argv
    def parse_stream(self, line: str) -> StreamEvent | None: ...        # delegates to _stream
```

`captures_sessions` is a public `bool` field (not a method) so the orchestrator avoids the Protocol-extension churn of adding `supports_session_capture()` in 3b.

### 3.3 `_argv.build_argv`

```python
def build_argv(
    *,
    model: str,
    effort: Literal["low", "medium", "high"] | None,
    prompt: str,
    extra_args: tuple[str, ...],
) -> list[str]:
```

Produces:

```
claude --print --output-format stream-json --verbose --model <model>
       [--thinking-effort <effort>]
       <extra_args...>
       -- <prompt>
```

`claude` is resolved via `$PATH` at subprocess-spawn time. The prompt is passed positionally after `--`; no shell metacharacters interpreted (Phase 3a's `_AgentRunner` does `subprocess.Popen(argv, ...)` with `shell=False`).

### 3.4 `_stream.parse_line`

```python
def parse_line(
    line: str,
    *,
    agent_name: str,
    iteration: int,
) -> StreamEvent | None:
```

Behavior per Claude Code `stream-json` line shape:

| Line `type` | Mapped event |
|---|---|
| `system` (init metadata) | `None` (drop) |
| `assistant`, content block `text` | `StreamEvent(type="text", text=<delta>, ...)` (one event per content block) |
| `assistant`, content block `tool_use` | `StreamEvent(type="tool_call", tool_name=..., tool_input=...)` |
| `assistant`, content block `thinking` | `None` (drop in 3b; round-trippable from captured JSONL) |
| `user` (tool_result) | `None` (drop in 3b) |
| `result` (final) | `StreamEvent(type="usage", usage=Usage(...), session_id=...)` |
| Malformed JSON | `None` (silently dropped — captured JSONL on disk preserves the raw line for post-mortem) |

`Usage` is constructed from `result.usage.{input_tokens,cache_creation_input_tokens,cache_read_input_tokens,output_tokens}`. `session_id` comes from the top-level `session_id` field on the `result` line.

`timestamp` on every emitted event is `datetime.now(timezone.utc)` at parse time (consistent with Phase 3a's `_loop._utcnow()` pattern).

### 3.5 `eden.session.capture_session`

```python
def capture_session(
    *,
    session_id: str,
    sandbox_cwd: Path,
    host_repo_path: Path,
    branch: str,
    iteration: int,
    home: Path | None = None,
) -> Path:
    """Locate ~/.claude/projects/<slug>/<session_id>.jsonl, copy to
    <host_repo_path>/.eden/sessions/<sanitized-branch>/iter-<i>-<session_id>.jsonl,
    rewriting absolute paths from sandbox_cwd → host worktree paths.
    Returns the destination path. Raises SessionCaptureFailed on any failure.
    """
```

`home` defaults to `Path.home()`; tests inject a tmp path. The destination path's `<sanitized-branch>` uses Phase 3a's `_BRANCH_SANITIZE` rule (`[^A-Za-z0-9._-]+` → `-`, max 64 chars).

The host worktree path (target prefix for rewriting) is the **resolved sandbox-side path's host equivalent** — for `no_sandbox`, `sandbox_cwd` and `host_repo_path` are typically equal; for `docker`, `sandbox_cwd` is `/workspace` and `host_repo_path` is the host worktree path.

### 3.6 `_slug.claude_projects_slug`

```python
def claude_projects_slug(cwd: Path) -> str:
    """Return the Claude Code projects-dir slug for `cwd`.

    Algorithm: take cwd.absolute().as_posix(), replace every '/' with '-',
    strip a leading '-'. Cross-platform: forward and back slashes both
    collapse to '-'.
    """
```

This is the **single point of truth** for Claude Code's filesystem layout assumption. If Claude Code changes its slug rule, only this function needs an update.

### 3.7 `_store.write_session_copy`

```python
def write_session_copy(
    *,
    src: Path,
    dest: Path,
    sandbox_cwd: Path,
    host_repo_path: Path,
) -> None:
    """Read src line by line, decode each as JSON, rewrite paths via
    rewrite_paths(line, sandbox_prefix=str(sandbox_cwd), host_prefix=str(host_repo_path)),
    write each line to dest. dest's parent is mkdir'd."""
```

### 3.8 `_encode.rewrite_paths`

```python
def rewrite_paths(line: str, *, sandbox_prefix: str, host_prefix: str) -> str:
    """Parse `line` as JSON, recursively walk every string value, replace any
    occurrence of sandbox_prefix at the START of the string with host_prefix,
    re-encode. If `line` doesn't parse as JSON, return it unchanged."""
```

Recursion handles dicts, lists, and strings; numbers/bools/null/None pass through. Sandbox-prefix detection uses `value.startswith(sandbox_prefix)` — stricter than substring so we don't rewrite, e.g., a string that happens to contain `/workspace` mid-text.

### 3.9 Mount strategy

- **`no_sandbox`:** Claude Code runs on the host. Eden reads from `~/.claude/projects/<host-cwd-slug>/`. No mount needed. Smoke-tested in 3b.
- **`docker`:** When `agent.captures_sessions=True`, Eden injects an implicit read-write mount of `~/.claude/projects/` → `/root/.claude/projects/` (or wherever the container's `$HOME` is) into `CreateOptions.mounts`. The slug inside the container resolves against `/workspace`; Claude Code writes to `/root/.claude/projects/-workspace/<id>.jsonl` which back-mounts to `~/.claude/projects/-workspace/<id>.jsonl` on the host. The actual `eden.session.capture_session()` call resolves the slug from `sandbox_cwd` (the orchestrator passes `handle.worktree_path`, which is `/workspace` for docker) so the lookup hits the correct path. Wired in 3b for completeness; integration-tested in the Linux-only docker job. Disabled when `capture_sessions=False`.

### 3.10 Orchestrator wiring (`_loop.py`)

Added per-iteration accumulators inside the existing `for i in range(max_iterations):`:

```python
iter_session_id: str | None = None
iter_usage: Usage | None = None
iter_session_file: Path | None = None
```

In the existing line-processing block, after `parse_stream(line)`:

```python
if ev.type == "usage":
    iter_session_id = ev.session_id
    iter_usage = ev.usage
```

After the `_AgentRunner` block exits (claude has emitted `result` and process EOFed) and before the iteration-end hooks run:

```python
if iter_session_id is not None and getattr(agent, "captures_sessions", False):
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
```

The `iterations.append(...)` call extends to:

```python
iterations.append(Iteration(
    index=i,
    completion_signal=iter_completion,
    session_id=iter_session_id,
    session_file_path=iter_session_file,
    usage=iter_usage,
))
```

The final `assemble()` call at the end of `_run_loop` extends to:

```python
last = iterations[-1] if iterations else None
return assemble(
    ...
    session_id=last.session_id if last else None,
    session_file_path=last.session_file_path if last else None,
    usage=last.usage if last else None,
)
```

### 3.11 `assemble()` signature extension (`_result.py`)

Adds three keyword-only parameters: `session_id: str | None`, `session_file_path: Path | None`, `usage: Usage | None`. They flow into the existing `RunResult(...)` constructor (no shape change to `RunResult` itself).

---

## 4. Error handling

| Failure | Behavior | Surfaced as |
|---|---|---|
| `claude` binary missing on PATH | `_AgentRunner` raises (Phase 2 `ProviderUnavailable`-style or `FileNotFoundError` from Popen) | Exception propagates out of `eden.run` |
| `stream-json` line malformed JSON | `parse_line` returns `None`; line silently dropped from event stream (still preserved verbatim in the captured JSONL on disk) | Iteration continues |
| Stream emits no terminal `usage` event | `iter_session_id` stays `None`; capture skipped | `session_id`/`session_file_path` remain `None`; iteration completes normally |
| Source JSONL not on disk after iteration | `capture_session` raises `SessionCaptureFailed`; orchestrator catches; warning event logged | `session_file_path=None`; `session_id` retained from stream |
| Source line not valid JSON during rewrite | `rewrite_paths` returns line unchanged | Captured file contains the offending line verbatim |
| Destination dir un-writable | `SessionCaptureFailed` caught | Same as missing-source |
| Iteration aborted mid-stream (`Aborted`/`IdleTimeout`) | No terminal `usage` event arrives; capture is skipped | Existing 3a teardown semantics |

All capture failures are **soft** — the iteration's stdout, log file, and prior events are unaffected.

---

## 5. Concurrency

**No new threads.** Session capture runs synchronously on the main thread between `_AgentRunner` exit and the `iterations.append(...)` call. The Phase 3a stdout-pump and idle-watchdog threads are unchanged.

---

## 6. Testing strategy

### 6.1 Fake-claude shim

A reusable test fixture (`tests/_fake_claude/`) that emits a deterministic `stream-json` transcript and writes a corresponding session JSONL:

- **`tests/_fake_claude/__init__.py`** — Python helper:
  - Writes a Python script to a tmp dir, named `claude` (executable bit set).
  - The script emits configured stream-json lines to stdout, then writes a session JSONL to `<home>/.claude/projects/<slug>/<session_id>.jsonl`.
  - Returns the tmp dir path.
  - Tests prepend it to `$PATH` via `monkeypatch.setenv` and override `$HOME` to a tmp dir.

- **`tests/_fake_claude/_transcript.py`** — typed builder:
  ```python
  Transcript().text("hi").tool("Read", {"path": "/x"}).result(session_id="abc", usage={...})
  ```

The shim is pure Python (`print(json.dumps(...), flush=True)` line by line). Cross-platform: runs identically on Linux/macOS/Windows.

### 6.2 Unit tests

| File | Coverage |
|---|---|
| `tests/unit/test_streaming_extensions.py` | `tool_call`/`usage` event kinds + `__post_init__` validators |
| `tests/unit/test_claude_code_argv.py` | argv builder with various flag combinations |
| `tests/unit/test_claude_code_stream.py` | `parse_line` over every stream-json shape + malformed JSON |
| `tests/unit/test_session_slug.py` | Cross-platform slug derivation |
| `tests/unit/test_session_rewrite.py` | Path-prefix rewrite over varied JSON shapes |
| `tests/unit/test_session_store.py` | `capture_session` happy path + missing-source + I/O error |
| `tests/unit/test_errors_phase3b.py` | `SessionCaptureFailed` shape |

### 6.3 E2E tests (extends Phase 3a's `tests/e2e/`)

- `tests/e2e/test_claude_code_smoke.py` — full pipeline via fake-claude shim:
  - `claude_code(model=..., capture_sessions=True)` agent
  - `eden.run(...)` end-to-end
  - Assert `RunResult.session_id == <id-from-shim-transcript>`
  - Assert `RunResult.session_file_path` exists and is under `<repo>/.eden/sessions/<branch>/`
  - Assert the file contents have sandbox paths rewritten to host paths
  - Assert `RunResult.usage.output_tokens > 0`
  - Assert at least one `tool_call` event landed in the `on_event` callback
- One additional test for `capture_sessions=False` — `session_id` set from stream, `session_file_path=None`, no file written.

### 6.4 Coverage

Existing 70% gate retained. New code is heavily tested; total coverage projected to stay ≥ 90%.

### 6.5 Real-Claude tests (deferred)

A separately-marked `claude_real` pytest marker is **not** added in 3b. Real-Claude integration tests are Phase 7 polish.

---

## 7. Backwards compatibility

- `simulated_agent` keeps working unchanged. `parse_stream` still returns `None` → orchestrator's existing fallback emits a `text` event → `iter_session_id` stays `None` → `Iteration` and `RunResult` get `session_id=None` exactly as in 3a.
- All existing 3a tests stay green.
- The `Agent` Protocol surface stays the same (no new methods). `captures_sessions` is read off agents via `getattr(agent, "captures_sessions", False)`. Older agents → `False` → no capture attempted.
- `StreamEvent.type` literal expansion is a superset; existing code that only checks `type == "text"` or `type == "idle_warning"` continues to compile and behave identically.

---

## 8. Drop-in promise

The post-3a "agent swap" promise stays intact: replacing `simulated_agent(...)` with `claude_code(model=..., ...)` in any Phase 3a `eden.run(...)` call works without other changes. The orchestrator code that currently always sets `session_id=None` will now populate it when the agent advertises `captures_sessions=True` and emits a `usage` event.

---

## 9. Phase boundary

**Lands in 3b:** Claude Code agent, session JSONL capture (no_sandbox + docker mounting wired, no_sandbox e2e-tested), `StreamEvent` extensions, `SessionCaptureFailed`, populated `Iteration`/`RunResult` session/usage fields.

**Deferred to 3c:** `resume_session` re-entry, `Agent.supports_resume()` / `supports_session_capture()` Protocol extensions.

**Deferred to 4:** docker integration test for session capture (in Linux-only integration job).

**Deferred to 5:** `codex`, `opencode`, `pi` agent factories.

**Deferred to 6:** `interactive(...)` TTY mode + Rich-rendered stdout sink.

---

**Estimated effort:** ~1.5 weeks, matching the original Phase 3 split.

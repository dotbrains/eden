# Eden Phase 5 — Additional Agents (codex, opencode, pi) Design

**Status:** Approved design.

**Predecessors:** Phase 3a (Agent Protocol + simulated_agent + IterationContext). Phase 3b (claude_code reference implementation, StreamEvent extensions, session capture). Latest commit on main: `6667d33`.

**Goal:** Add three additional named agent factories — `codex`, `opencode`, `pi` — built atop a new generic `cli_agent` factory that accepts any line-streaming CLI binary. Each named factory is a thin wrapper with sensible defaults; users plug in their own `build_argv`/`parse_stream` for binary-specific behavior.

**Out of scope (deferred):**
- Structured stream-output parsing for codex/opencode/pi (their JSON schemas may differ; Phase 7 docs add real-world recipes once stabilized).
- Session JSONL capture for non-Claude agents (each agent's session-file location/format differs; Phase 7+ once we have real transcripts).
- Real-binary integration tests (requires installed CLIs + credentials; Phase 7 polish).
- Vendor-specific auth helpers (each agent reads its own env vars per its docs).

---

## 1. Public surface added

```python
# eden/agents/cli/__init__.py
def cli_agent(
    *,
    name: str,
    model: str,
    binary: str,
    build_argv: Callable[[IterationContext], list[str]] | None = None,
    parse_stream: Callable[[str], StreamEvent | None] | None = None,
    captures_sessions: bool = False,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """Build an Agent for any line-streaming CLI tool.

    The default `build_argv` produces ``[binary, *extra_args, ctx.prompt]`` —
    the prompt is appended as the final positional argument. Users override
    for binary-specific flags.

    The default `parse_stream` returns `None` for every line, so the
    orchestrator's fallback emits a `StreamEvent(type="text", ...)` per line.
    Users override for binary-specific structured-output parsing.
    """

# eden/agents/codex.py
def codex(model: str = "gpt-5", *, env=None, extra_args=()) -> Agent: ...

# eden/agents/opencode.py
def opencode(model: str = "claude-opus-4", *, env=None, extra_args=()) -> Agent: ...

# eden/agents/pi.py
def pi(model: str = "pi-3.5", *, env=None, extra_args=()) -> Agent: ...
```

Re-exported from `eden.agents.__init__` and `eden.__init__`:

```python
from eden import cli_agent, codex, opencode, pi
```

---

## 2. Architecture

### 2.1 New + modified files

```
eden/
├── agents/
│   ├── cli/                          # NEW directory
│   │   ├── __init__.py               # NEW — cli_agent factory + _CliAgent dataclass
│   │   └── _argv.py                  # NEW — default build_argv impl
│   ├── codex/                        # NEW directory
│   │   └── __init__.py               # NEW — codex() factory (3-line wrapper)
│   ├── opencode/                     # NEW directory
│   │   └── __init__.py               # NEW — opencode() factory (3-line wrapper)
│   ├── pi/                           # NEW directory
│   │   └── __init__.py               # NEW — pi() factory (3-line wrapper)
│   └── __init__.py                   # MODIFY — re-export 4 new factories
└── __init__.py                       # MODIFY — re-export 4 new factories

tests/
└── unit/
    ├── test_cli_agent.py             # NEW — generic cli_agent tests (~10 tests)
    ├── test_codex_agent.py           # NEW — codex factory shape (~3 tests)
    ├── test_opencode_agent.py        # NEW — opencode factory shape (~3 tests)
    └── test_pi_agent.py              # NEW — pi factory shape (~3 tests)

README.md                             # MODIFY — bump status to phase 5 complete
```

Every new file under the project's ~300-LoC budget. Largest expected: `eden/agents/cli/__init__.py` (~130 LoC).

### 2.2 Boundaries

- `cli_agent` is the foundation. Knows nothing about specific CLIs.
- `codex/opencode/pi` are 3-line wrappers that set `binary=` and `name=` to known values.
- Default `build_argv` is `[binary, *extra_args, ctx.prompt]` — works for line-buffered CLIs that accept a positional prompt argument.
- Default `parse_stream` is `lambda _line: None` — orchestrator's existing fallback emits text events.
- The `Agent` Protocol contract (Phase 3a) is unchanged.

---

## 3. Component contracts

### 3.1 `cli_agent` factory + `_CliAgent` dataclass

```python
@dataclass(frozen=True)
class _CliAgent:
    name: str
    model: str
    captures_sessions: bool
    _binary: str
    _build_argv: Callable[[IterationContext], list[str]] | None
    _parse_stream: Callable[[str], StreamEvent | None] | None
    _env: Mapping[str, str]
    _extra_args: tuple[str, ...]

    def build_command(self, ctx: IterationContext) -> list[str]:
        if self._build_argv is not None:
            return self._build_argv(ctx)
        return [self._binary, *self._extra_args, ctx.prompt]

    def parse_stream(self, line: str) -> StreamEvent | None:
        if self._parse_stream is not None:
            return self._parse_stream(line)
        return None  # orchestrator fallback emits text event
```

Frozen dataclass; satisfies the `Agent` Protocol structurally (with the same `name: str` / `model: str` `@property` discipline that Phase 3b's `_ClaudeCodeAgent` follows).

The factory return type is `Agent` (Protocol) — same as `simulated_agent`. The `captures_sessions` field is read by the orchestrator via `getattr(agent, "captures_sessions", False)`. Default `False` for `cli_agent` because the generic shim doesn't know where the agent writes sessions.

### 3.2 Named wrapper factories

```python
# eden/agents/codex/__init__.py
def codex(
    model: str = "gpt-5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """OpenAI Codex CLI agent. Assumes `codex` binary is on PATH.

    Reference: https://platform.openai.com/docs/codex (or wherever codex is documented).
    """
    return cli_agent(
        name="codex",
        model=model,
        binary="codex",
        env=env,
        extra_args=extra_args,
    )

# eden/agents/opencode/__init__.py
def opencode(
    model: str = "claude-opus-4",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """opencode CLI agent (sst/opencode). Assumes `opencode` binary is on PATH."""
    return cli_agent(
        name="opencode",
        model=model,
        binary="opencode",
        env=env,
        extra_args=extra_args,
    )

# eden/agents/pi/__init__.py
def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """pi CLI agent. Assumes `pi` binary is on PATH."""
    return cli_agent(
        name="pi",
        model=model,
        binary="pi",
        env=env,
        extra_args=extra_args,
    )
```

Each is a 5-line wrapper. The default `model` is illustrative (the real CLI may use different model names); users override via the positional `model` argument.

---

## 4. Error handling

| Failure | Behavior |
|---|---|
| `binary` not on PATH | `FileNotFoundError` from `subprocess.Popen` propagates out of `_AgentRunner.__enter__` (Phase 3a) |
| `build_argv` raises | Propagates out of `agent.build_command(ctx)` to the orchestrator |
| `parse_stream` raises on a line | Propagates; orchestrator does NOT catch (correctness over robustness — a parser bug shouldn't be silently swallowed) |
| Stdout line that the parser drops (`return None`) | Orchestrator's fallback creates `StreamEvent(type="text", text=line, ...)` |

`captures_sessions=False` means the orchestrator's session-capture path is skipped — `Iteration.session_id` and `session_file_path` stay `None`. Users who want session capture for a custom agent set `captures_sessions=True` AND ensure their agent writes a session JSONL to `~/.claude/projects/<slug>/<id>.jsonl` (the path Phase 3b's `capture_session` looks at). For non-Claude agents, this generally requires custom plumbing — Phase 7+ documentation territory.

---

## 5. Concurrency

No new threads in production code. The agent factories are pure constructors; no I/O at construction time.

---

## 6. Testing strategy

### 6.1 Unit tests

**`tests/unit/test_cli_agent.py` (~10 tests):**
- `cli_agent(name, model, binary)` returns an Agent (`isinstance(agent, Agent)` runtime check).
- Default `build_command(ctx)` produces `[binary, ctx.prompt]`.
- `extra_args` threaded correctly: `[binary, *extra_args, ctx.prompt]`.
- Custom `build_argv` callable overrides the default.
- Default `parse_stream(line)` returns `None`.
- Custom `parse_stream` callable overrides.
- `name` and `model` attributes accessible.
- `captures_sessions=False` default; `True` honored.
- Frozen — attribute mutation raises.
- `env` defaults to empty dict; non-empty preserved.

**`tests/unit/test_codex_agent.py` (~3 tests):**
- `codex()` returns Agent with `name="codex"`, `binary="codex"` (verify via `build_command`).
- Default model is `"gpt-5"`; override accepted.
- `extra_args` threaded.

**`tests/unit/test_opencode_agent.py` (~3 tests):** analogous, `name="opencode"`, default model `"claude-opus-4"`.

**`tests/unit/test_pi_agent.py` (~3 tests):** analogous, `name="pi"`, default model `"pi-3.5"`.

### 6.2 No e2e tests in 5

Each named agent depends on a real CLI binary not installed in CI. Phase 5 ships factories; Phase 7 polish adds real-binary integration tests gated by env var + `shutil.which`.

### 6.3 Coverage

70% gate retained. New code is heavily tested.

---

## 7. Backwards compatibility

- All existing tests pass unchanged.
- `simulated_agent` and `claude_code` keep working.
- `cli_agent` is additive; does not affect existing factories.

---

## 8. Phase boundary

**Lands in 5:** `cli_agent` foundation + `codex`/`opencode`/`pi` named wrappers + unit tests + README bump.

**Deferred to 6:** CLI scaffolder (`eden init`).
**Deferred to 7:** structured `parse_stream` for each agent + real-binary integration tests + docs.

---

**Estimated effort:** ~3-4 days. Significantly smaller than 4b/4c because no new infrastructure (HTTP, REST, fake servers) — just factory plumbing on top of the Phase 3a Agent Protocol.

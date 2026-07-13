# Python API: Sessions

Detailed reference for session storage and transcript helper APIs. See
[Python API: Agents](python-api-agents.md) for agent Protocols and factories.

---

## <a id="session-storage"></a>`SessionStorage` Protocol

```python
@runtime_checkable
class SessionStorage(Protocol):
    def extra_mounts(self) -> tuple[Mount, ...]: ...
    def host_capture(
        self, *, handle, session_id, host_repo_path, branch, iteration
    ) -> Path | None: ...
    def sandbox_transfer(self, *, handle, host_session_file, session_id) -> None: ...
```

Per-agent transcript capture, ADR-0012 style. Eden's default Claude Code agent ships a `ClaudeSessionStorage` instance on its `session_storage` attribute (set when `capture_sessions=True`), which the orchestrator delegates to instead of doing the work in `_run_loop`. Out-of-tree agents (codex, pi, opencode wrappers) can ship their own `SessionStorage` implementation to plug in custom transcript layouts without forking the orchestrator. Legacy agents that only expose `captures_sessions: bool` still work: the orchestrator falls back to `ClaudeSessionStorage` for them.

## `ClaudeSessionStorage`

```python
@dataclass(frozen=True)
class ClaudeSessionStorage:
    home: Path | None = None
```

The default `SessionStorage` implementation, used by `claude_code()`. Mounts `~/.claude/projects` into containerized sandboxes and locates Claude's per-iteration JSONL by the project-slug convention. `home=` overrides `~` for tests.

## `CodexSessionStorage`

```python
@dataclass(frozen=True)
class CodexSessionStorage:
    home: Path | None = None
```

The `SessionStorage` implementation used by `codex(capture_sessions=True)` (the default). Mounts `~/.codex/sessions` into containerized sandboxes and walks codex's date-nested directory tree (`<YYYY>/<MM>/<DD>/rollout-<timestamp>-<session_id>.jsonl`) to locate the per-iteration transcript. `home=` overrides `~` for tests.

## `PiSessionStorage`

```python
@dataclass(frozen=True)
class PiSessionStorage:
    home: Path | None = None
```

The `SessionStorage` implementation used by `pi(capture_sessions=True)` (the default). Mounts `~/.pi/agent/sessions` into containerized sandboxes and locates pi's per-iteration JSONL by the `--<encoded-cwd>--/<timestamp>_<session_id>.jsonl` convention. Resume rewrites the session header's `cwd` field via `transfer_pi_session(...)` and places the JSONL inside the sandbox-cwd-encoded directory so pi's project-first resolver doesn't trigger the "fork session?" prompt. `home=` overrides `~` for tests.

## Session Lookup Helpers

```python
def encode_project_path(cwd: PurePath | str) -> str: ...
def claude_host_session_path(
    cwd: PurePath | str,
    session_id: str,
    *,
    projects_dir: Path | None = None,
) -> Path: ...
def claude_sandbox_session_path(
    cwd: PurePath | str,
    session_id: str,
    *,
    projects_dir: PurePath | str,
) -> PurePath: ...
def find_claude_session_on_host(
    session_id: str,
    *,
    projects_dir: Path | None = None,
) -> Path | None: ...
def find_codex_session_on_host(
    session_id: str,
    *,
    sessions_dir: Path | None = None,
) -> Path | None: ...
```

Convenience helpers for tooling that needs to locate captured agent transcripts without constructing a `SessionStorage` instance. Claude helpers use the same project-slug convention as `ClaudeSessionStorage`; Codex lookup walks the date-nested `~/.codex/sessions` tree for `rollout-*-<session_id>.jsonl`.

## `transfer_session`

```python
def transfer_session(
    *,
    source: Path,
    dest: Path,
    source_cwd: str,
    dest_cwd: str,
) -> Path: ...
```

Cross-host helper. Copies a captured session JSONL from `source` to `dest`, rewriting every absolute path that starts with `source_cwd` to start with `dest_cwd`. Use to migrate captured sessions between machines whose worktree paths differ (e.g. `/Users/alice/repo` -> `/home/build/repo`) so the resumed agent sees its own filesystem layout. `dest`'s parent is created. Raises `SessionCaptureFailed` on missing source or I/O error.

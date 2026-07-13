# Agent Factories

Detailed reference for Eden's in-process and dedicated agent factories. See [Agents](agents.md) for the overview, runtime guidance, and authentication notes, [Agent CLI factories](agent-cli-factories.md) for `cli_agent`-backed adapters, and [Agent CLI editor factories](agent-cli-editor-factories.md) for editor-backed adapters.

---

## `simulated_agent`

```python
from eden import simulated_agent

agent = simulated_agent(
    output="hello\n<promise>COMPLETE</promise>\n",
)
```

### Signature

```python
def simulated_agent(
    name: str = "simulated",
    model: str = "deterministic-1",
    *,
    output: str | list[str] | Callable[[IterationContext], str] = "<promise>COMPLETE</promise>\n",
    delay_per_line: float = 0.0,
    fail_with: Exception | None = None,
) -> Agent: ...
```

- `name` — agent identifier surfaced in `StreamEvent.agent_name`. Default `"simulated"`.
- `model` — informational model tag. Default `"deterministic-1"`.
- `output` — what the simulated CLI prints to stdout. A `str`, list of lines, or callable receiving the [`IterationContext`](python-api.md#iterationcontext).
- `delay_per_line` — seconds to sleep between lines (lets you exercise idle-warning logic). Default `0.0`.
- `fail_with` — when set, `build_command(ctx)` raises this exception instead of producing a command.

### What binary it wraps

None — `build_command` returns an argv that invokes the current Python interpreter (`sys.executable`) with an inlined script that prints the configured `output`. No external CLI is required.

### When to use

- Smoke-testing the orchestrator without an installed agent.
- Driving deterministic test fixtures in `tests/unit/` and `tests/e2e/`.
- Examples and documentation snippets that should run anywhere.

`captures_sessions` is not exposed; the simulated agent does not produce session JSONL.

## `claude_code`

```python
from eden import claude_code

agent = claude_code("claude-opus-4-8", effort="high")
```

### Signature

```python
def claude_code(
    model: str,
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_skip_permissions: bool = False,
    permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] | None = None,
    extra_args: tuple[str, ...] = (),
) -> _ClaudeCodeAgent: ...
```

- `model` — Claude model id, threaded into `--model`. Required (positional).
- `name` — agent identifier. Default `"claude-code"`.
- `effort` — optional `--thinking-effort` level (`"low"`, `"medium"`, `"high"`).
- `env` — per-agent environment additions; the orchestrator merges them with the host env.
- `capture_sessions` — when `True`, the orchestrator post-processes each iteration's session JSONL into `.eden/sessions/`. Default `True`.
- `dangerously_skip_permissions` — when `True`, appends `--dangerously-skip-permissions` so Claude does not block on per-tool permission prompts. Safe inside an isolated sandbox; think twice before enabling for `no_sandbox()`, where Claude would gain unprompted access to the host filesystem. Equivalent to `permission_mode="bypassPermissions"`. Default `False`.
- `permission_mode` — graduated tool-approval control, appended as `--permission-mode <mode>`: `"default"` (prompt per tool), `"acceptEdits"` (auto-accept file edits, prompt for the rest), `"plan"` (plan only, no edits), or `"bypassPermissions"` (skip all prompts). Use this instead of the all-or-nothing `dangerously_skip_permissions` for a middle ground — e.g. `"acceptEdits"` for safe autonomous editing or `"plan"` for a read-only planning iteration. Mutually exclusive with `dangerously_skip_permissions=True` (passing both raises `InvalidOptions`). Default `None` (omit the flag).
- `extra_args` — escape hatch for unsurfaced Claude CLI flags. Inserted before the stdin sigil (`-p -`).

### Argv shape

Eden builds `claude --print --output-format stream-json --verbose --model <model> [--thinking-effort ...] [--resume <id>] [--dangerously-skip-permissions] [--permission-mode <mode>] [extra_args...] -p -` and pipes the prompt via stdin. Stdin delivery dodges the Linux 128 KB execve argv-size limit, so prompts of any size are safe.

### Session capture and resume

`captures_sessions=True` is the default. The orchestrator watches `~/.claude/projects/<slug>/<id>.jsonl` and copies it to `.eden/sessions/<branch>/<iteration>.jsonl` after each iteration; `Iteration.session_id` and `Iteration.session_file_path` are populated. Set `capture_sessions=False` to skip this work.

Alongside the main transcript, eden also captures any **subagent/workflow transcripts** Claude wrote as *separate* session files this run — sibling `.jsonl` files carrying `isSidechain: true` entries — copying each (path-rewritten) to `.eden/sessions/<branch>/iter-<n>-sub-<id>.jsonl`. The sweep is scoped to the run by file modification time, so a sandbox slug shared across runs doesn't drag in stale transcripts, and it's best-effort (a failed sub-capture never aborts the run). Subagents recorded *inline* in the main transcript need no special handling — they're already in the main capture. This mainly matters for isolated/cloud providers, where only the main session is otherwise pulled back to the host.

To **resume** a captured session, pass `run(..., resume_session=<id>)` (top-level `run()` argument, not on the factory). Eden appends `--resume <id>` to the argv. Resume requires `max_iterations=1`; otherwise `InvalidOptions` is raised.

### What binary it wraps

The `claude` CLI from Anthropic (Claude Code). Must be installed and authenticated on `$PATH` at `run()` time.

### When to use

- Production runs against Claude Code.
- Workloads where preserving the chat transcript matters (audit, replay, debugging).

### When not to use

- Environments without the `claude` binary; reach for `simulated_agent` or another CLI agent instead.

## `codex`

Moved to [Agent CLI factories](agent-cli-factories.md#codex).

## `opencode`

Moved to [Agent CLI factories](agent-cli-factories.md#opencode).

## `pi`

Moved to [Agent CLI factories](agent-cli-factories.md#pi).

## `cursor`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#cursor).

## `copilot`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#copilot).

## `cli_agent`

Moved to [Agent CLI adapter](agent-cli-adapter.md#cli_agent).

## See also

- [Agent CLI factories](agent-cli-factories.md) — `codex`, `opencode`, and `pi`.
- [Agent CLI editor factories](agent-cli-editor-factories.md) — `cursor` and `copilot`.
- [Agent CLI adapter](agent-cli-adapter.md) — generic `cli_agent` reference.
- [Agents](agents.md) — factory matrix, Flox runtimes, and authentication.
- [Python API: Agents](python-api-agents.md) — public Protocol and session helper reference.

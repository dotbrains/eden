# Claude Code Agent

Detailed reference for the dedicated Claude Code factory. See
[Agent factories](agent-factories.md) for the in-process simulated agent and
[Agents](agents.md) for the factory overview, runtime guidance, and
authentication notes.

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
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_skip_permissions: bool = False,
    permission_mode: Literal["default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"] | None = None,
    extra_args: tuple[str, ...] = (),
) -> _ClaudeCodeAgent: ...
```

- `model` - Claude model id, threaded into `--model`. Required.
- `name` - agent identifier. Default `"claude-code"`.
- `effort` - optional `--thinking-effort` level. `max` is intended for Opus
  models.
- `env` - per-agent environment additions; merged with the host env.
- `capture_sessions` - copy each iteration's session JSONL into
  `.eden/sessions/`. Default `True`.
- `dangerously_skip_permissions` - append `--dangerously-skip-permissions`.
  Safe inside an isolated sandbox; think twice before using `no_sandbox()`.
  Equivalent to `permission_mode="bypassPermissions"`.
- `permission_mode` - graduated tool-approval control via
  `--permission-mode <mode>`. Mutually exclusive with
  `dangerously_skip_permissions=True`.
- `extra_args` - escape hatch for unsurfaced Claude CLI flags, inserted before
  the stdin sigil (`-p -`).

### Argv shape

Eden builds `claude --print --output-format stream-json --verbose --model
<model> [--thinking-effort ...] [--resume <id>]
[--dangerously-skip-permissions] [--permission-mode <mode>] [extra_args...] -p
-` and pipes the prompt via stdin. Stdin delivery avoids the Linux 128 KB
execve argv-size limit, so prompts of any size are safe.

### Session capture and resume

`captures_sessions=True` is the default. The orchestrator watches
`~/.claude/projects/<slug>/<id>.jsonl` and copies it to
`.eden/sessions/<branch>/<iteration>.jsonl` after each iteration;
`Iteration.session_id` and `Iteration.session_file_path` are populated. Set
`capture_sessions=False` to skip this work.

Alongside the main transcript, Eden also captures separate Claude
subagent/workflow transcripts written as sibling `.jsonl` files with
`isSidechain: true` entries. Each is path-rewritten into
`.eden/sessions/<branch>/iter-<n>-sub-<id>.jsonl`. The sweep is scoped to the
run by file modification time, so a reused sandbox slug does not pull in stale
transcripts, and sub-capture failures do not abort the run.

To resume a captured session, pass `run(..., resume_session=<id>)`; Eden appends
`--resume <id>` to the argv. Resume requires `max_iterations=1`; otherwise
`InvalidOptions` is raised.

### What binary it wraps

The `claude` CLI from Anthropic. It must be installed and authenticated on
`$PATH` at `run()` time.

### When to use

- Production runs against Claude Code.
- Workloads where preserving the chat transcript matters.

### When not to use

- Environments without the `claude` binary; use `simulated_agent` or another CLI
  agent instead.

## See also

- [Agent factories](agent-factories.md) - in-process and dedicated factories.
- [Agent CLI factories](agent-cli-factories.md) - `codex`.
- [Agent CLI other factories](agent-cli-other-factories.md) - `opencode` and `pi`.
- [Python API: Agents](python-api-agents.md) - public Protocol and helper reference.

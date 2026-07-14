# Agent CLI Factories

Detailed reference for Eden's Codex factory. See [Agent CLI other factories](agent-cli-other-factories.md) for `opencode` and `pi`, [Agent CLI adapter](agent-cli-adapter.md) for the generic adapter, and [Agent factories](agent-factories.md) for in-process factories.

## `codex`

```python
from eden import codex

agent = codex("gpt-5")
```

### Signature

```python
def codex(
    model: str = "gpt-5",
    *,
    name: str = "codex",
    effort: Literal["low", "medium", "high", "xhigh"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_bypass_approvals_and_sandbox: bool = True,
    approvals_reviewer: Literal["user", "auto_review"] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Builds `codex exec [resume <id>] --json [--dangerously-bypass-approvals-and-sandbox] -m <model> [-c model_reasoning_effort="<level>"] [extra_args ...]` and delivers the prompt via stdin.

### Options

- `effort` — optional reasoning level; threads `-c model_reasoning_effort="<level>"`. One of `"low"`, `"medium"`, `"high"`, `"xhigh"`.
- `capture_sessions` — when `True` (default), the orchestrator post-processes each iteration's session JSONL into `.eden/sessions/` via [`CodexSessionStorage`](python-api.md#codexsessionstorage). Resume a captured session via the top-level `run(..., resume_session=<id>)` (requires `max_iterations=1`).
- `dangerously_bypass_approvals_and_sandbox` — when `True` (default), appends `--dangerously-bypass-approvals-and-sandbox` so codex does not block on per-tool approval prompts. Safe inside an isolated sandbox; think twice before enabling for `no_sandbox()`. Superseded by `approvals_reviewer="auto_review"`.
- `approvals_reviewer` — maps to codex's `approvals_reviewer` config key (`-c approvals_reviewer="<value>"`). When `"auto_review"`, swaps the bypass flag for an interactive approval policy plus codex's most permissive sandbox (`-a on-request -s danger-full-access`), so an AI reviewer mediates per-action approvals instead of skipping them outright — eden's sandbox provider still owns the outer filesystem boundary. `"user"` (and unset) keep the default bypass behaviour. An unrecognised value raises `InvalidOptions`.

### parse_stream

Decodes codex JSONL events: `thread.started` → `session_id`, `item.completed`/`agent_message` → `text`, `item.started`/`command_execution` → `tool_call` (Bash), `error` → `text`. Live display, file logs, and `on_agent_stream_event` callbacks see structured events instead of one-line-per-token noise.

### What binary it wraps

The `codex` CLI from OpenAI. Must be on `$PATH`. The `"gpt-5"` default is illustrative — supply whatever model identifier your installed `codex` accepts.

## `opencode`

Moved to [Agent CLI other factories](agent-cli-other-factories.md#opencode).

## `pi`

Moved to [Agent CLI other factories](agent-cli-other-factories.md#pi).

## `cursor`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#cursor).

Compatibility anchors: <a id="cursor"></a>

## `copilot`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#copilot).

Compatibility anchors: <a id="copilot"></a>

## `cli_agent`

Moved to [Agent CLI adapter](agent-cli-adapter.md#cli_agent).

Compatibility anchors: <a id="cli_agent"></a>

## See also

- [Agent CLI other factories](agent-cli-other-factories.md) — `opencode` and `pi`.
- [Agent factories](agent-factories.md) — `simulated_agent`.
- [Claude Code agent](agent-claude-code.md) — `claude_code`.
- [Agent CLI editor factories](agent-cli-editor-factories.md) — `cursor` and `copilot`.
- [Agent CLI adapter](agent-cli-adapter.md) — generic `cli_agent` reference.
- [Agents](agents.md) — factory matrix and authentication.
- [Python API: Agents](python-api-agents.md) — public Protocol and session helper reference.

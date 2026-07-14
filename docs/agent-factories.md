# Agent Factories

Detailed reference for Eden's in-process agent factory. See [Claude Code agent](agent-claude-code.md) for the dedicated Claude Code factory, [Agents](agents.md) for the overview, and [Agent CLI factories](agent-cli-factories.md) for `cli_agent`-backed adapters.

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

Moved to [Claude Code agent](agent-claude-code.md#claude_code).

## `codex`

Moved to [Agent CLI factories](agent-cli-factories.md#codex).

## `opencode`

Moved to [Agent CLI other factories](agent-cli-other-factories.md#opencode).

## `pi`

Moved to [Agent CLI other factories](agent-cli-other-factories.md#pi).

## `cursor`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#cursor).

## `copilot`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#copilot).

## `cli_agent`

Moved to [Agent CLI adapter](agent-cli-adapter.md#cli_agent).

## See also

- [Claude Code agent](agent-claude-code.md) — dedicated `claude_code` reference.
- [Agent CLI factories](agent-cli-factories.md) — `codex`.
- [Agent CLI other factories](agent-cli-other-factories.md) — `opencode` and `pi`.
- [Agent CLI editor factories](agent-cli-editor-factories.md) — `cursor` and `copilot`.
- [Agent CLI adapter](agent-cli-adapter.md) — generic `cli_agent` reference.
- [Agents](agents.md) — factory matrix and authentication.
- [Python API: Agents](python-api-agents.md) — public Protocol and session helper reference.

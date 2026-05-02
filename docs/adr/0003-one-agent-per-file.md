# ADR 0003 — One agent per file

**Status:** Accepted (2026-05-02).

## Context

Eden ships agent factories for `simulated_agent`, `claude_code`, `codex`, `opencode`, `pi`, plus the generic `cli_agent`. Two layouts were considered:

1. **Single registry file** — `eden/agents.py` containing all factories.
2. **One subpackage per agent** — `eden/agents/<name>/__init__.py` (or a small module per agent).

## Decision

Adopt option 2. Each agent lives in its own module or subpackage:

```
eden/agents/
├── __init__.py          # re-exports + Agent Protocol + IterationContext
├── simulated.py         # simulated_agent factory
├── claude_code.py       # claude-code-specific (session capture)
├── cli/                 # generic cli_agent foundation
├── codex/               # 5-line wrapper over cli_agent
├── opencode/            # 5-line wrapper over cli_agent
└── pi/                  # 5-line wrapper over cli_agent
```

## Consequences

- Each agent file stays small (well under the project's ~300-LoC budget).
- Adding a new agent doesn't touch any existing agent file (no merge conflicts).
- Agent-specific test files mirror the layout: `tests/unit/test_<agent>_agent.py`.
- The `claude_code` agent owns its session-capture logic (`captures_sessions=True`); generic agents don't import it.
- The `__init__.py` re-exports give users a flat import surface: `from eden import claude_code, codex, opencode, pi, cli_agent, simulated_agent`.

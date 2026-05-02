# Eden documentation

Python orchestrator for AI coding agents in sandboxed worktrees.

---

## Getting started

- [What is Eden?](what-is-eden.md) — positioning, feature matrix, when to use it.
- [Quick start](quick-start.md) — `eden init` to first run in five minutes.

## Reference

- [Python API](python-api.md) — every name importable from `eden`.
- [CLI](cli.md) — `eden init`, `eden version`.
- [Configuration](configuration.md) — environment variables, `Logging`, `Timeouts`.
- [Sandbox providers](sandbox-providers.md) — `no_sandbox`, `docker`, `podman`, `isolated`, `daytona`, `vercel`.
- [Agents](agents.md) — `simulated_agent`, `claude_code`, `codex`, `opencode`, `pi`, `cli_agent`.
- [Prompts](prompts.md) — `PromptSource`, args, shell blocks, built-ins.
- [Templates](templates.md) — the `blank` scaffolder template.
- [Errors](errors.md) — the `EdenError` hierarchy.

## Concepts

- [How it works](how-it-works.md) — branch strategies, worktrees, sandbox lifecycle, iteration loop.
- [Custom providers](custom-providers.md) — implementing the `IsolatedSandboxHandle` Protocol.
- [Development](development.md) — repo layout, test markers, lint and type gates, contributing.

## Architecture decision records

- [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md)
- [ADR 0002 — Sync-first public API](adr/0002-sync-first-public-api.md)
- [ADR 0003 — One agent per file](adr/0003-one-agent-per-file.md)

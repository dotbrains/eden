# Eden documentation

Python orchestrator for AI coding agents in sandboxed worktrees.

---

## Getting started

- [What is Eden?](what-is-eden.md) — positioning, feature matrix, when to use it.
- [Quick start](quick-start.md) — `eden init` to first run in five minutes.
- [Tutorial: build your first agent loop](tutorial-first-loop.md) — 10-minute walkthrough that ends with a real agent fixing a real bug.

## Reference

- [Python API](python-api.md) — every name importable from `eden`.
- [CLI](cli.md) — `eden init`, `eden run`, `eden cost`, `eden clean`, `eden replay`, `eden version`.
- [GitHub Action](github-action.md) — run an eden iteration loop in any GitHub workflow.
- [Configuration](configuration.md) — environment variables, `Logging`, `Timeouts`.
- [Sandbox providers](sandbox-providers.md) — `no_sandbox`, `docker`, `podman`, `isolated`, `daytona`, `vercel`.
- [Agents](agents.md) — `simulated_agent`, `claude_code`, `codex`, `opencode`, `pi`, `cli_agent`.
- [Prompts](prompts.md) — `PromptSource`, args, shell blocks, built-ins.
- [Templates](templates.md) — `blank`, `simple-loop`, `sequential-reviewer`, `parallel-planner`, `plan-implement-review`.
- [Errors](errors.md) — the `EdenError` hierarchy.

## Concepts

- [How it works](how-it-works.md) — branch strategies, worktrees, sandbox lifecycle, iteration loop.
- [Custom providers](custom-providers.md) — implementing the `IsolatedSandboxHandle` Protocol.
- [Development](development.md) — repo layout, test markers, lint and type gates, contributing.

## Architecture decision records

- [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md)
- [ADR 0002 — Sync-first public API](adr/0002-sync-first-public-api.md)
- [ADR 0003 — One agent per file](adr/0003-one-agent-per-file.md)
- [ADR 0004 — Structured output via XML tags](adr/0004-structured-output-via-xml-tags.md)
- [ADR 0005 — Container UX hygiene: UID, SELinux, tilde mounts](adr/0005-container-ux-hygiene.md)
- [ADR 0006 — `Sandbox.run()`: caller-managed sandbox lifecycle](adr/0006-sandbox-run-caller-managed-lifecycle.md)
- [ADR 0007 — Interactive sessions: TTY-attached, no loop](adr/0007-interactive-sessions.md)
- [ADR 0008 — Template scaffolding registry](adr/0008-template-scaffolding-registry.md)
- [ADR 0009 — Containerized TTY for `interactive()`](adr/0009-containerized-tty-for-interactive.md)
- [ADR 0010 — Auto-create parent directories for file mounts](adr/0010-auto-create-mount-parent-dirs.md)
- [ADR 0011 — Async API surface](adr/0011-async-api-surface.md)
- [ADR 0012 — OpenTelemetry tracing](adr/0012-otel-tracing.md)

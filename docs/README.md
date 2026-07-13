# Eden documentation

Python orchestrator for AI coding agents in sandboxed worktrees.

---

## Getting started

- [What is Eden?](what-is-eden.md) — positioning, feature matrix, when to use it.
- [Quick start](quick-start.md) — `eden init` to first run in five minutes.
- [Tutorial: build your first agent loop](tutorial-first-loop.md) — 10-minute walkthrough that ends with a real agent fixing a real bug.

## Reference

- [Python API](python-api.md) — canonical index for every name importable from `eden`.
- [Python API: Entry points](python-api-entrypoints.md) — `run`, `interactive`, and async wrappers.
- [Python API: Sandboxes and worktrees](python-api-sandboxes.md) — caller-managed `Sandbox` and worktree creation.
- [Python API: Types](python-api-types.md) — configuration dataclasses.
- [Python API: Results](python-api-results.md) — result dataclasses.
- [Python API: Logging](python-api-logging.md) — stream-event sink configuration.
- [Python API: Streaming](python-api-streaming.md) — stream events and callbacks.
- [Python API: Structured output](python-api-output.md) — `Output`, schema validation, and retries.
- [Python API: Agents](python-api-agents.md) — agent factories and Protocols.
- [Python API: Sessions](python-api-sessions.md) — transcript capture, storage, and helpers.
- [Python API: Lifecycle](python-api-lifecycle.md) — hooks, cancellation, and shutdown callbacks.
- [Python API: Extensibility](python-api-extensibility.md) — provider Protocols.
- [Python API: Display](python-api-display.md) — display sinks and display entries.
- [Python API: Errors and tracing](python-api-errors-tracing.md) — error formatting, tracing, and version metadata.
- [CLI](cli.md) — `eden init`, `eden run`, `eden cost`, `eden clean`, `eden replay`, `eden version`.
- [GitHub Action](github-action.md) — run an eden iteration loop in any GitHub workflow.
- [Configuration](configuration.md) — environment variables, `Logging`, `Timeouts`.
- [Sandbox providers](sandbox-providers.md) — provider matrix and local provider behavior.
- [Container sandbox providers](container-sandbox-providers.md) — Docker and Podman details.
- [Cloud sandbox providers](cloud-sandbox-providers.md) — Daytona, Vercel, and forkd details.
- [Sandbox provider usage](sandbox-provider-usage.md) — selection flowchart and import examples.
- [Agents](agents.md) — factory matrix, Flox runtimes, and authentication.
- [Agent factories](agent-factories.md) — `simulated_agent` and `claude_code`.
- [Agent CLI factories](agent-cli-factories.md) — `codex`, `opencode`, `pi`, and `cli_agent`.
- [Agent CLI editor factories](agent-cli-editor-factories.md) — `cursor` and `copilot`.
- [Agent CLI adapter](agent-cli-adapter.md) — generic `cli_agent` reference.
- [Prompts](prompts.md) — `PromptSource`, args, shell blocks, built-ins.
- [Templates](templates.md) — local `eden init` template reference.
- [Blank template](template-blank.md) — minimal scaffold files and customization.
- [GitHub agent workflow template](github-agent-workflow-template.md) — label-driven GitHub Actions scaffold.
- [Errors](errors.md) — the `EdenError` hierarchy and top-level public errors.
- [Top-level errors](top-level-errors.md) — top-level `EdenError` subclasses.
- [Error recovery](error-recovery.md) — handling strategies and catch-all examples.
- [Sandbox and worktree errors](sandbox-worktree-errors.md) — provider and worktree error families.

## Concepts

- [How it works](how-it-works.md) — branch strategies, worktrees, sandbox lifecycle, iteration loop.
- [Custom providers](custom-providers.md) — `SandboxProvider` and handle Protocol reference.
- [Custom provider protocols](custom-provider-protocols.md) — Protocol reference.
- [Custom provider reference](custom-provider-reference.md) — provider types and factory helpers.
- [Custom provider guide](custom-provider-guide.md) — skeleton implementation, in-tree examples, and conventions.
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

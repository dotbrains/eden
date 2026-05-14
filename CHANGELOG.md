# Changelog

All notable changes to Eden are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (loosely) and the
project adheres to [Semantic Versioning](https://semver.org/) once 1.0
ships.

## Unreleased

### Added

- **`base_branch` parameter** on `run()`, `create_sandbox()`, `create_worktree()`,
  `interactive()`, and their `eden.aio.*` async wrappers. Overrides the fork
  point of the default `merge_to_head` strategy without forcing the caller to
  construct a `BranchStrategy` by hand. Mutually exclusive with
  `branch_strategy=` (the strategy already owns `base`). _(Upstream 0.5.6)._
- **`eden docker build-image` / `eden docker remove-image`** (and `eden podman
  build-image` / `eden podman remove-image`) — Typer sub-apps that wrap the
  `docker`/`podman` CLI against the Dockerfile scaffolded by `eden init`.
  `--image-name` overrides the default `eden:<repo-dir-name>` tag.
  _(Upstream 0.4.6)._
- **`Hook(sudo=True)`** — sandbox hooks (`SandboxHooks.on_sandbox_ready` etc.)
  can now elevate their command via `sudo -E -- sh -c …`, useful for in-container
  `apt-get install` setup steps when the sandbox runs as a non-root user. Host
  hooks reject `sudo=True` (upstream parity — host hooks never elevate).
  _(Upstream 0.4.3)._
- **`parallel-planner-with-review` template** — combines `parallel-planner`'s
  one-planner / N-implementer fan-out with per-branch review running in the
  same `Sandbox` as the implementer (via `create_sandbox` + two `sandbox.run`
  calls). Selectable via `eden init --template parallel-planner-with-review`.
  _(Upstream 0.4.1)._
- **Vercel + Daytona `copy_file_in` directory support** — when the host path
  is a directory, the helper tars+gzips it, base64-encodes, ships via a single
  `exec`, and untars at the target. Files still take the fast path. _(Upstream
  vercel `copyIn` parity.)_
- **`AgentError`** — typed error raised when an agent subprocess exits
  non-zero without matching the completion signal. Carries `agent_name`,
  `exit_code`, `stderr`, and `parsed_error` (extracted from stdout for Codex
  / Pi / OpenCode, which surface errors there rather than on stderr).
- **`CopyToWorktreeError`** — typed error raised when the isolated provider's
  worktree clone fails or exceeds `Timeouts.copy_to_worktree`. Carries
  `source`, `target`, `timeout`, and `timed_out` (true on budget overrun,
  false on permission/disk failure).
- **`Timeouts.copy_to_worktree`** (default 60s) — bounds the isolated
  sandbox's worktree clone. Also exposed per-call as
  `isolated.provider(copy_timeout=...)`; pass `None` to disable.
- **Recovery hint stream event** — the loop emits a copy-pastable recovery
  message before raising `AgentError`, including agent name, exit code,
  parsed error, branch, worktree path, log path, and suggested next-step
  commands (`cd`, `git status`, `git diff`, `eden clean`).
- **`format_agent_error_recovery`** — public helper for formatting the
  recovery message above, exported from `eden.orchestrator._recovery`.

### Changed

- **Inline `prompt="..."` strings are now passed verbatim.** No `{{KEY}}`
  substitution, no `` !`cmd` `` shell expansion, no `{{SOURCE_BRANCH}}` /
  `{{TARGET_BRANCH}}` injection. File-sourced prompts (`prompt_file=...`)
  still go through the full render pipeline. Move templated prompts to a
  file or build the string in Python before passing it inline. _(Mirrors
  upstream's `4032e64`.)_
- **Prompt arg values are now inert during `` !`cmd` `` expansion.**
  `render_prompt` substitutes built-ins, expands shell blocks from the raw
  template, and substitutes user args last. An arg value containing
  `` !`...` `` text is treated as literal data instead of triggering
  subprocess execution. _(Mirrors upstream's `6bc4d74`; closes a
  command-injection vector.)_
- **Agent failures fail fast.** A non-zero exit without a completion signal
  now raises `AgentError` immediately, instead of letting the loop wait for
  `idle_timeout` to fire. Surfaces previously-silent agent crashes.
- **Finalize log line is commit-aware.** Replaces
  `[eden] finalized: applied=True files=N bytes=B` with
  `[eden] no changes to sync` / `[eden] syncing N file(s) to host (B bytes)`
  / `[eden] sync incomplete: N file(s) attempted (B bytes)`.

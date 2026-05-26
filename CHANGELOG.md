# Changelog

All notable changes to Eden are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (loosely) and the
project adheres to [Semantic Versioning](https://semver.org/) once 1.0
ships.

## Unreleased

### Added

- **`CodexSessionStorage`** + codex session capture/resume — `codex()` now
  defaults `capture_sessions=True` and ships a `CodexSessionStorage` instance
  on its `session_storage` attribute, mirroring the claude_code pattern.
  Mounts `~/.codex/sessions` into containerized sandboxes and walks codex's
  date-nested directory tree (`<YYYY>/<MM>/<DD>/rollout-<...>-<id>.jsonl`)
  to locate per-iteration JSONLs. Resume a captured codex session via the
  top-level `run(..., resume_session=<id>)` (requires `max_iterations=1`);
  the invocation becomes `codex exec resume <id> --json ...`. _(Upstream
  parity 0.5.0.)_
- **codex command shape now matches the upstream contract** — invocation is
  `codex exec [resume <id>] --json [--dangerously-bypass-approvals-and-sandbox]
  -m <model> [-c model_reasoning_effort="<level>"] [extra_args ...]` with the
  prompt delivered via stdin. The previous thin `cli_agent` wrapper (which
  ran `codex <prompt>` and emitted no parsed stream events without manual
  `extra_args`) is replaced by a dedicated `_CodexAgent` class.
- **`codex(dangerously_bypass_approvals_and_sandbox=...)`** — opt-out kwarg
  (default `True`). When `True`, appends `--dangerously-bypass-approvals-and-sandbox`
  so codex does not block on per-tool approvals inside a sandbox. Mirrors
  `claude_code(dangerously_skip_permissions=...)` ergonomics.
- **`transfer_session(*, source, dest, source_cwd, dest_cwd)`** — public
  helper that copies a captured session JSONL between hosts, rewriting
  absolute paths that start with `source_cwd` to start with `dest_cwd`.
  Useful for migrating sessions between machines whose worktree paths
  differ. Exported from `eden` and `eden.session`.
- **`CodexSessionStorage` and `transfer_session` exposed at the top level**
  (`from eden import CodexSessionStorage, transfer_session`).
- **`throw_on_duplicate_worktree`** kwarg on `run()`, `create_sandbox()`,
  `create_worktree()`, `interactive()`, and their `eden.aio.*` async wrappers
  (default `True`). When `False` and the named-strategy branch already has an
  on-disk worktree, that worktree is reused (returned with `managed=False` so
  `close()` does not remove it) instead of raising `BranchExists`. Only
  meaningful for `BranchStrategy.named(...)`; `merge_to_head` always carves a
  fresh branch and `head` reuses the host repo. Branches that exist but have
  no on-disk worktree still raise `BranchExists`. _(Upstream parity 0.4.1.)_
- **Codex + pi `parse_stream` parsers** — both agents now decode their
  respective JSONL stream formats into structured `StreamEvent`s instead of
  one-line-per-token text noise. Codex maps `thread.started` →
  `StreamEvent(type="session_id")`, `item.completed` (agent_message) →
  `text`, `item.started` (command_execution) → `tool_call` (Bash), and
  `error` → `text`. Pi maps `message_update` (text_delta) → `text`,
  `tool_execution_start` → `tool_call` for known tools (Bash, WebSearch,
  WebFetch, Agent), `agent_end` → final-message `text`, and
  `agent_error`/`error` → `text`. _(Upstream parity.)_
- **`StreamEvent(type="session_id")`** — new variant for agents whose stream
  announces the session id before any usage data is available (e.g. codex's
  `thread.started`). The orchestrator reads `session_id` from this event the
  same way it reads it from `usage` events, so `Iteration.session_id` now
  populates for codex too.
- **`claude_code(dangerously_skip_permissions=...)`** — when `True`, appends
  `--dangerously-skip-permissions` so Claude does not block on per-tool
  permission prompts inside a sandboxed container. Default `False`. Safe inside
  isolated sandboxes (docker/podman/vercel/daytona/isolated); think twice
  before enabling for `no_sandbox()`. Also propagates to the interactive
  command path. _(Upstream parity 0.4.6.)_
- **`codex(effort=...)`** — optional reasoning-effort level (`"low"`, `"medium"`,
  `"high"`, `"xhigh"`). When set, threads
  `-c model_reasoning_effort="<level>"` into the codex invocation. _(Upstream
  parity.)_
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

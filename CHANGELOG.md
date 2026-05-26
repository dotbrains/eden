# Changelog

All notable changes to Eden are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (loosely) and the
project adheres to [Semantic Versioning](https://semver.org/) once 1.0
ships.

## Unreleased

### Added

- **`"custom"` backlog manager in `eden init`** — selectable via
  `--backlog custom`, scaffolds projects in a deliberately
  broken-until-configured state with `<TODO ...>` markers in the rendered
  `prompt.md`, `.env.example`, and `Dockerfile`. Intended for users whose
  issue tracker isn't one of the four shipped (Shortcut, Asana, in-house
  REST APIs); the agent is expected to wire the markers up on first run
  after reading the scaffolded README. _(Upstream parity 0.6.3.)_
- **`resume_session=` precheck + `SessionNotFound` typed error** — `run()`
  now verifies the session JSONL exists on the host before spawning the
  agent (was: agent failed inside the sandbox with a buried "session not
  found" stderr). `SessionStorage` gains an optional
  `locate_session_on_host(session_id, sandbox_cwd)` method; the
  orchestrator skips the precheck silently when the agent's storage
  doesn't ship one (back-compat for custom impls). `ClaudeSessionStorage`
  derives the project-slug from `sandbox_cwd`; `CodexSessionStorage` walks
  its date-nested tree. _(Upstream parity 0.6.1.)_
- **`docker()` / `podman()` resource options** — three new keyword arguments
  on both provider factories (and on `make_container_provider`):
  - `devices: tuple[str, ...] | None = None` — expose host devices via
    `--device <spec>` (e.g. `("/dev/kvm",)` for nested virtualization or
    `("/dev/dri:/dev/dri:rwm",)` for GPU access).
  - `cpus: float | None = None` — bound the container's CPU usage via
    `--cpus <value>`; useful when multiple sandboxes share a host.
  - `groups: tuple[str | int, ...] | None = None` — add supplementary
    groups to the in-container user via `--group-add`; most commonly
    `("docker",)` for Docker-in-Docker setups bind-mounting the host
    socket. _(Upstream parity 0.6.0.)_
- **opencode `parse_stream` parser + `--format json` + `--dangerously-skip-permissions` + `agent=` mode** — `opencode()` now ships a dedicated `_OpenCodeAgent` class (mirroring `_CodexAgent`) instead of the thin `cli_agent` wrapper. Builds the invocation `opencode run --format json --model <model> [--variant <v>] [--agent <name>] [--dangerously-skip-permissions] [extra_args ...] <prompt>` and parses opencode's JSONL events (`step_start` → `session_id`, `text` → `text`, `tool_use` (`state.status=="completed"`) → `tool_call`, `error` → `text`). Without `--format json` opencode would emit free-form text and Eden would silently drop session ids and tool calls. The new `agent=` kwarg maps to `--agent build` / `--agent plan` for opencode's named modes. _(Upstream parity 0.6.0.)_
- **Host-side git subprocess timeouts** — every host-side `git` invocation (`eden/worktree/_git.py:_run_git`, `branch_exists`, `eden/orchestrator/_setup.py:resolve_target_branch`) now runs with a 60 s deadline. Wedged local git (NFS stall, filesystem repair, runaway hook) raises the new typed `GitCommandTimeout` instead of hanging Eden indefinitely. `_run_git()` accepts a `timeout=` override.
- **Codex per-iteration token usage** — the codex `parse_stream` parser now
  decodes `{"type":"turn.completed","usage":{...}}` events into
  `StreamEvent(type="usage", ...)`, so `Iteration.usage` populates and the
  orchestrator's per-iteration "Context window: NNNk" display works for
  codex runs (matches claude_code). Codex's `cached_input_tokens` maps to
  Eden's `cache_read_input_tokens`; `input_tokens` is reported net of cache
  hits so the split mirrors Claude's accounting. _(Upstream parity 0.6.2.)_

### Fixed

- **Beads `bd close` template** now passes `--reason="..."` instead of a
  positional argument; current Beads releases reject the positional form,
  silently leaving tasks open even though the agent thought it closed them.
  _(Upstream parity 0.6.0.)_
- **GitHub Issues backlog `list_tasks_command`** now passes `--limit 100`
  (previously defaulted to 30) so the parallel-planner sees the full
  dependency graph for backlogs over 30 issues. _(Upstream parity 0.6.0.)_
- **Beads Dockerfile detects host arch** (`amd64` / `arm64` from `uname -m`)
  before downloading the `bd-linux-<arch>` binary; previously hard-coded to
  `amd64` and would 404 on arm64 hosts.
- **GH_TOKEN `.env.example` comment** now links the personal-access-token
  creation page and lists the required scopes (Issues R/W, Metadata R), so
  silent 403s from under-scoped tokens are easier to diagnose. _(Upstream
  parity 0.6.0.)_

### Added

- **Daytona live-API integration test** (`tests/integration/test_daytona_provider.py`)
  — gated on `DAYTONA_API_KEY`; skipped cleanly when the env var is unset.
  Exercises the full provider lifecycle against `https://api.daytona.io`
  (overridable via `DAYTONA_API_URL`): create → exec → stdin-via-base64 →
  copy_file_in (file and directory) → copy_file_out → finalize → idempotent
  close. The integration suite's non-Linux skip in
  `tests/integration/conftest.py` now applies only to docker/podman files
  so REST-based provider tests can run on any OS.
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

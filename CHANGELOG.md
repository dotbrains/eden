# Changelog

All notable changes to Eden are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (loosely) and the
project adheres to [Semantic Versioning](https://semver.org/) once 1.0
ships.

## Unreleased

### Added

- **`codex(approvals_reviewer=...)`** — AI-mediated approval evaluation for the
  codex agent. `"auto_review"` swaps the default
  `--dangerously-bypass-approvals-and-sandbox` for an interactive approval
  policy plus codex's most permissive sandbox
  (`-a on-request -s danger-full-access -c approvals_reviewer="auto_review"`),
  so a reviewer agent mediates per-action approvals instead of skipping them
  outright — eden's sandbox provider still owns the outer filesystem boundary.
  `"user"` (and unset) keep the existing bypass behaviour; an unrecognised
  value raises `InvalidOptions`. Mirrors sandcastle's
  `codex(model, { approvalsReviewer })` (v0.8.0). See `docs/agents.md`.
- **`Logging.stdout()`** — a stdout log sink alongside the existing file sink.
  Writes the same formatted, redacted stream-event lines to the host process's
  stdout instead of a file under `.eden/logs/` — useful in CI, where the job
  log is the natural destination. `RunResult.log_file_path` is `None` for
  stdout-logged runs. Constructing `Logging(type="file")` without a `path` (or
  `type="stdout"` with one) now raises `InvalidOptions`. Mirrors sandcastle's
  `logging: { type: "stdout" }`. See `docs/configuration.md`.

- **`claude_code(permission_mode=...)`** — graduated tool-approval control for
  the Claude Code agent, appended as `--permission-mode <mode>`. Accepts
  `"default"`, `"acceptEdits"`, `"plan"`, or `"bypassPermissions"`, giving a
  middle ground between prompting on every tool and the existing all-or-nothing
  `dangerously_skip_permissions` — e.g. `"acceptEdits"` for safe autonomous
  editing inside a sandbox or `"plan"` for a read-only planning iteration. The
  two options are mutually exclusive; passing both (or an unrecognised mode)
  raises `InvalidOptions`. `dangerously_skip_permissions` is unchanged and stays
  the equivalent of `permission_mode="bypassPermissions"`. Mirrors sandcastle's
  `claudeCode(model, { permissionMode })`. See `docs/agents.md` and
  `docs/python-api.md`.

## [0.2.0] - 2026-06-10

### Added

- **`Timeouts.git_setup`** — a per-command deadline (default `60.0` s) for the
  host-side git plumbing `run()` executes while carving and tearing down a
  worktree: `git worktree add`/`remove`, branch/worktree listing, `status`, and
  the `origin` fast-forward when reusing a clean worktree. Previously these were
  bound by a hard-coded 60 s constant with no override; raise it on slow
  filesystems (NFS, networked volumes) or very large repos where worktree
  creation legitimately takes longer. Honored by `run()`, `interactive()`, and
  `create_sandbox(timeouts=...)`; the standalone `create_worktree()` helper
  carves at the 60 s default (pass `git_timeout=` to override). Mirrors
  sandcastle's `gitSetupMs`. See `docs/python-api.md` and
  `docs/configuration.md`.
- **Per-agent Flox runtime** — every agent factory now accepts an optional
  `flox_env=<dir>` pointing at a directory that ships its own Flox env
  (`.flox/env/manifest.toml`). When set, Eden runs the agent CLI inside it via
  `flox activate -d <dir> -- <argv>`, so each agent type gets its own declared,
  lockfile-pinned toolchain instead of inheriting the host's (mirrors
  [blacksmith's per-identity Flox env](https://github.com/dotbrains/blacksmith/pull/2)).
  Enforced when present: a declared env whose manifest is missing — or a missing
  `flox` binary — raises the new `FloxEnvError`; set `EDEN_ALLOW_NO_FLOX=1` to
  skip activation where Flox is unavailable (Windows / CI smoke tests). Agents
  that don't declare a `flox_env` are unchanged. See ADR-0014 and
  `docs/agents.md`.
- **`forkd` sandbox provider** — a new isolated/finalizing provider
  (`eden.sandboxes.forkd`) that runs agents inside
  [forkd](https://github.com/deeplethe/forkd) Firecracker microVMs via forkd's
  E2B-compatible Python SDK. Spawns a child VM from a warm `snapshot`, runs the
  agent, and patch-syncs changes back to the host worktree on `finalize()` —
  the same diff/pull/apply flow as the daytona/vercel providers. The SDK is an
  optional dependency (`pip install eden-agent[forkd]`) imported lazily inside
  `create()`, so the module stays importable on hosts without forkd;
  `ProviderUnavailable` is raised at create time. Linux + KVM only. Pass
  `sandbox_factory=` to fully control SDK construction (controller URL, memory
  limits, live-branch checkpoints).
- **Flox dev environment + Flox-based Linux/macOS CI** — a declarative,
  lockfile-pinned [Flox](https://flox.dev) environment lives under `.flox/`
  and is the source of truth for the toolchain on Linux/macOS. `flox activate`
  provisions Python 3.11/3.12/3.13, git, gh, docker/podman clients,
  pre-commit, and make, then auto-builds `.venv` via
  `pip install -e ".[dev]"` (guarded by a stamp so repeat activations stay
  fast). `EDEN_PYTHON` selects which interpreter the venv is built from
  (default `python3.11`), so the 3.11/3.12/3.13 matrix is preserved. The
  venv is exported onto `PATH` from the activation hook so both interactive
  `flox activate` and `flox activate -- <cmd>` (CI) resolve the venv. CI's
  Ubuntu/macOS legs now run inside Flox; the **Windows leg stays native**
  (`actions/setup-python` + pip) because Flox is Linux/macOS only and eden
  ships Windows-specific path handling. ruff and mypy remain pip-pinned in
  the venv (exact `pyproject.toml [dev]` versions), not in the Flox
  manifest, to keep local/CI parity.

### Fixed

- **Reused named-branch worktrees refresh from origin** — when
  `create_worktree(strategy=BranchStrategy.named(...),
  throw_on_duplicate_worktree=False)` reuses an existing on-disk
  worktree, eden now runs `git fetch origin <branch>` +
  `git merge --ff-only origin/<branch>` on a clean worktree so the agent
  doesn't run against stale code. Every failure mode is non-fatal and
  falls back to plain reuse: a detached HEAD (e.g. paused mid-rebase) is
  left untouched, a failed fetch (no `origin`, offline, branch missing
  upstream) reuses as-is, and a diverged branch (where `--ff-only`
  refuses) preserves unpushed work. A dirty worktree is reused untouched
  with no fetch. _(Upstream parity sandcastle v0.7.0,
  `fastForwardFromOrigin`.)_
- **Init non-TTY test no longer brittle under colour** — the
  `eden init` non-interactive assertion stripped ANSI escapes, rich box
  borders, and wrapping whitespace before matching the flag name, since
  Typer renders the `BadParameter` error through rich and splits
  `--sandbox` into per-character colour spans on colour-capable CI
  terminals. Test-only; the `init` behaviour itself was already correct.

### Changed

- **`eden init` fully non-interactive** — when stdin is not a TTY and a
  required option flag (`--sandbox`, `--agent`, `--model`, `--template`,
  `--backlog`) is missing, init now fails fast naming the absent flag
  instead of hanging on (or aborting cryptically out of) the prompt
  library. Pass every flag, or `--yes` to accept defaults. Interactive
  TTY behaviour is unchanged. _(Upstream parity sandcastle v0.7.0.)_

### Added

- **`RunResult.resume(prompt)` and `RunResult.fork(prompt)` methods** —
  sugar for `eden.run(agent=..., sandbox=..., cwd=..., prompt=prompt,
  resume_session=result.session_id)` with the original `run()` context
  carried on the result. `.fork()` writes a **new** session id while
  continuing from the captured state (claude `--fork-session`, codex
  `exec fork <id>`), so concurrent fan-out (`r.fork(a)` and `r.fork(b)`
  in parallel) doesn't corrupt the parent. Safe concurrent fork also
  needs distinct `branch_strategy=BranchStrategy.named(...)` per child.
  `eden.run()` and `Sandbox.run()` also accept `fork_session=True`
  directly. _(Upstream parity sandcastle v0.6.6, 58f335f.)_
- **`completion_timeout` bounds the trailing-line drain** — once the
  iteration's completion signal is matched, eden swaps the idle timer
  for a shorter total budget (default `60.0` seconds) while draining
  trailing lines. A child process that keeps the agent's stdout pipe
  open after the signal no longer hangs the run until `idle_timeout`
  (default 10 min) trips; on `completion_timeout` expiry the iteration
  succeeds with a warning, commits intact. `total_timeout=None`
  preserves the pre-port behaviour. _(Upstream parity sandcastle
  v0.6.6, ddc26ba.)_
- **`pi()` session capture + resume** — `pi(capture_sessions=True)` is
  the new default; pi sessions captured under
  `~/.pi/agent/sessions/--<enc-cwd>--/<ts>_<id>.jsonl` are copied to
  `.eden/sessions/<branch>/iter-<i>-<id>.jsonl` with the JSONL header's
  `cwd` rewritten. Resume rewrites it back to the sandbox cwd and lands
  the file under `--<encoded-sandbox-cwd>--/` so pi's project-first
  resolver doesn't trigger the "fork session?" prompt. New
  `PiSessionStorage` exported from `eden`. _(Upstream parity sandcastle
  v0.6.6, 932aa70.)_
- **`pi(thinking=...)` option** — forwards `--thinking <level>` to the
  pi CLI. Accepted: `"off"`, `"minimal"`, `"low"`, `"medium"`, `"high"`,
  `"xhigh"`. _(Upstream parity sandcastle v0.6.6, 1201b4d.)_
- **`PromptError.exit_code` structured field** — when a `` !`command` ``
  shell-block expansion fails, the subprocess exit code is now an
  attribute on the raised `PromptError` (not just in the message), so
  callers can branch programmatically (e.g. retry only on transient
  codes). `None` for non-exec failures (missing files, unknown
  placeholders). _(Upstream parity sandcastle v0.6.6, b9b9712.)_
- **Bounded rolling tail for accumulated stdout** — the orchestrator's
  per-run `stdout_chunks` is now a `BoundedTail` (default 64 KiB)
  instead of an unbounded `list[str]`. Multi-hour agent runs no longer
  grow the buffer linearly with output volume. The three consumers
  (`parse_stdout_error`, `Output.object` / `Output.string` extraction,
  the final `RunResult.stdout`) all care about the tail, not the head,
  so bounding is sound. Public class `BoundedTail` is available under
  `eden.orchestrator._bounded_tail` for downstream reuse. _(Upstream
  parity sandcastle's `boundedTail.ts`.)_
- **`LC_ALL=C` pinned on host-side git invocations** — `_run_git`,
  `branch_exists`, and `resolve_target_branch` now run git under a
  fixed C locale via the new `c_locale_env()` helper. Eden parses
  porcelain output today so the immediate fix is defensive, but a
  caller that later substring-matches git stderr (e.g. "fatal:
  invalid reference") would silently break under non-English locales
  without this pin. _(Upstream parity sandcastle 0.6.1, 46eb483.)_
- **Process-wide shutdown registry** — new `eden.register_shutdown(cb)`
  installs at most one `SIGINT` / `SIGTERM` / `atexit` handler per signal
  and fans out to a set of synchronous teardown callbacks. Returns an
  idempotent unregister. `eden.run()` uses it to close the sandbox handle
  and worktree on `SIGTERM`, which Python's default handler terminates
  without running `try/finally` — previously this leaked containers and
  isolated worktrees when the parent died abruptly. Callers managing
  their own resources can register custom teardowns. `SIGINT` re-raises
  `KeyboardInterrupt` after running teardowns so `try/finally` still
  runs; `SIGTERM` exits with code `143`. _(Upstream parity sandcastle's
  `shutdownRegistry.ts`.)_
- **Interactive `{{KEY}}` placeholder collection** — `eden.interactive()`
  now prompts the user via stdin for any `{{KEY}}` placeholder not
  supplied in `prompt_args` instead of raising `PromptError`. Built-in
  keys (`SOURCE_BRANCH` / `TARGET_BRANCH`) are skipped. Default
  behaviour autodetects: collect when stdin is a TTY, skip otherwise
  (CI runs still surface the existing error). Pass `collect_args=True` /
  `False` to force. Helpers `find_missing_keys` and `collect_missing_args`
  are exported from `eden.prompt` for reuse. _(Upstream parity
  sandcastle's `findMissingPromptArgKeys` + interactive arg loop.)_
- **Copy-pastable finalize-failure recovery** — when an isolated
  provider's `finalize(target)` raises or returns `applied=False`, the
  orchestrator now emits a structured recovery message via the stream
  sink listing the isolated worktree path, the host target, the error,
  and an `rsync -a --exclude=.git --exclude=.eden <iso>/ <target>/`
  command the user can paste to complete the merge manually. The local
  `isolated` provider also marks its temp worktree as preserved on
  finalize failure (`handle.preserve()`) so the rsync target actually
  exists. Replaces the previous single-line `[eden] finalize failed:
  {exc}` log. _(Upstream parity sandcastle's `buildRecoveryMessage`.)_
- **"List is pre-filtered" hint in `simple-loop` and `sequential-reviewer`
  templates** — both prompts now state, after the
  `!`{list_tasks_command}` ` block, that the list has already been filtered to
  tasks ready for work and that an empty list means nothing to do this
  iteration. Without this, agents would sometimes re-query the tracker with a
  broader filter and pull in tasks outside the configured label set when their
  own list came back empty. The `parallel-planner*` templates already had this
  hint; this brings the other two templates to parity. _(Upstream parity
  sandcastle 0.6.4.)_
- **`Output.object(schema=...)` accepts validator classes directly** —
  pydantic v2 `BaseModel` subclasses (detected via `model_validate`),
  pydantic v1 `BaseModel` subclasses (detected via `parse_obj` +
  `__fields__`), and anything else callable. Previously users had to
  pass `schema=MyModel.model_validate` to dodge BaseModel's
  positional-arg incompatibility; now `schema=MyModel` Just Works.
  No new dependencies — detection is via `getattr` duck-typing. New
  helper `eden.output._validator.resolve_validator`. _(Upstream parity
  0.6.1.)_
- **`cursor()` agent factory** — wraps Cursor's CLI binary (named `agent`).
  Builds `agent --print --output-format stream-json --model <model>
  [--force] [extra_args ...] <prompt>`. Includes a 120 KB pre-flight
  prompt-size guard (positional argv → execve `ARG_MAX`) that raises
  `InvalidOptions(code="config.prompt_too_long")` instead of letting the
  runner die with `OSError: Argument list too long`. Optional `force=True`
  is cursor's equivalent of Claude's `dangerously_skip_permissions`.
  Parser handles cursor's `tool_call` events and delegates
  Claude-compatible `assistant`/`result` shapes to Claude's parser.
  `captures_sessions=False` (resume not supported). _(Upstream parity 0.6.0.)_
- **`copilot()` agent factory** — wraps GitHub's `copilot` CLI binary.
  Builds `copilot -p <prompt> --output-format json --model <model>
  [--allow-all-tools] [--effort <level>] [extra_args ...]`. Same 120 KB
  pre-flight guard. Optional `effort: "low"|"medium"|"high"` and
  `allow_all_tools=True` (Copilot's equivalent of
  `dangerously_skip_permissions`). Parser decodes Copilot JSONL events
  (`assistant.message_delta` → `text`, `tool.execution_start` →
  `tool_call` (normalising lowercase `"bash"` → `"Bash"`), `result` →
  `session_id`, `error`/`agent_error` → `text`).
  `captures_sessions=False`. _(Upstream parity 0.6.0.)_
- **`assert_prompt_fits_argv` helper** — shared pre-flight check at
  `eden/agents/_argv_guards.py` for agents that pass the prompt
  positionally. Conservative 120 KB byte cap (UTF-8) leaves headroom
  for envp + remaining argv under Linux's ~128 KB `ARG_MAX`.
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
  `branch_strategy=` (the strategy already owns `base`). _(Sandcastle 0.5.6)._
- **`eden docker build-image` / `eden docker remove-image`** (and `eden podman
  build-image` / `eden podman remove-image`) — Typer sub-apps that wrap the
  `docker`/`podman` CLI against the Dockerfile scaffolded by `eden init`.
  `--image-name` overrides the default `eden:<repo-dir-name>` tag.
  _(Sandcastle 0.4.6)._
- **`Hook(sudo=True)`** — sandbox hooks (`SandboxHooks.on_sandbox_ready` etc.)
  can now elevate their command via `sudo -E -- sh -c …`, useful for in-container
  `apt-get install` setup steps when the sandbox runs as a non-root user. Host
  hooks reject `sudo=True` (sandcastle parity — host hooks never elevate).
  _(Sandcastle 0.4.3)._
- **`parallel-planner-with-review` template** — combines `parallel-planner`'s
  one-planner / N-implementer fan-out with per-branch review running in the
  same `Sandbox` as the implementer (via `create_sandbox` + two `sandbox.run`
  calls). Selectable via `eden init --template parallel-planner-with-review`.
  _(Sandcastle 0.4.1)._
- **Vercel + Daytona `copy_file_in` directory support** — when the host path
  is a directory, the helper tars+gzips it, base64-encodes, ships via a single
  `exec`, and untars at the target. Files still take the fast path. _(Sandcastle
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
  sandcastle's `4032e64`.)_
- **Prompt arg values are now inert during `` !`cmd` `` expansion.**
  `render_prompt` substitutes built-ins, expands shell blocks from the raw
  template, and substitutes user args last. An arg value containing
  `` !`...` `` text is treated as literal data instead of triggering
  subprocess execution. _(Mirrors sandcastle's `6bc4d74`; closes a
  command-injection vector.)_
- **Agent failures fail fast.** A non-zero exit without a completion signal
  now raises `AgentError` immediately, instead of letting the loop wait for
  `idle_timeout` to fire. Surfaces previously-silent agent crashes.
- **Finalize log line is commit-aware.** Replaces
  `[eden] finalized: applied=True files=N bytes=B` with
  `[eden] no changes to sync` / `[eden] syncing N file(s) to host (B bytes)`
  / `[eden] sync incomplete: N file(s) attempted (B bytes)`.

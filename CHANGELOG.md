# Changelog

All notable changes to Eden are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (loosely) and the
project adheres to [Semantic Versioning](https://semver.org/) once 1.0
ships.

## Unreleased

### Added

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

# ADR 0013 — Resume support requires filesystem-backed session storage

**Status:** Accepted (2026-05-26).

## Context

Per-agent transcript capture lives behind the `SessionStorage` Protocol in `eden/session/_protocol.py` — every agent can expose a `session_storage` object the orchestrator delegates capture, transfer, and host-side persistence to. Today the only in-tree implementation is `ClaudeSessionStorage` (`eden/session/_claude.py`), which:

- Mounts `~/.claude/projects/` into the container so Claude Code's per-iteration JSONL ends up readable on the host.
- Locates the JSONL by Claude's project-slug convention and copies it into `.eden/sessions/<branch>/iter-<n>-<id>.jsonl`, rewriting sandbox→host paths line-by-line.
- Returns `None` from `sandbox_transfer(...)` for resume — Claude Code reads the original mount, so no push-back is needed.

The Protocol shape leaves the door open to non-file backends. A SQLite-backed agent (OpenCode is the live example) could in principle satisfy `SessionStorage` by serialising the relevant database row(s) to a string the same store can round-trip back.

Implementing that for a real SQLite-backed agent turns out to be a different and far heavier problem than file transfer. The conversation state lives **inside** a local database file whose schema is private to the agent, may change between versions, is not addressable by a stable per-session path, and can hold rows for many sessions in one file. "Serialise the row(s) to a string" means reaching into another tool's database, understanding its schema, extracting a subgraph, and re-inserting it on the other side — coupling eden to an undocumented, versioned storage internal. By contrast, file-backed agents (Claude Code, Codex, Pi) persist one self-contained record per session on disk that we can copy verbatim and rewrite by line.

## Decision

Resumability via `run(..., resume_session=<id>)` is supported only for agents whose session record is **filesystem-backed** — a discrete file (or set of files) per session that eden can read, transfer, and write as opaque content, applying at most line-level path rewriting.

If an agent's session state is only available in a local database (e.g. OpenCode's SQLite store), eden does **not** implement resume for it. Such a provider ships with `captures_sessions=False` and no `session_storage` attribute, so `resume_session=` is effectively a no-op for it — the existing `SessionStorage` mechanism, with no special-casing.

This was confirmed feasible for Codex: its sessions are filesystem JSONL rollout files under `~/.codex/sessions/`, with SQLite used only as an index over those files, not as the source of truth — so Codex qualifies, even though no `CodexSessionStorage` ships today.

## Consequences

- OpenCode (`eden/agents/opencode/__init__.py`) remains usable, just non-resumable. The `captures_sessions=False` default on `cli_agent` already encodes this.
- Future agent provider documentation (when added) drops any "serialise the relevant row(s)" SQLite guidance and states the filesystem requirement as a must-have for resume.
- The implicit "Persisted session storage" capability becomes a hard filesystem gate: a database row addressable only via the agent's own DB does not satisfy it.
- Adding a `CodexSessionStorage` / `PiSessionStorage` is straightforward — copy `ClaudeSessionStorage`, swap the slug + projects-dir conventions, set `captures_sessions=True` in the agent factory.
- Reversible in principle — if a future agent's DB exposes a clean, documented per-session export/import path, this can be revisited — but the default stance is "filesystem or no resume."

## See also

- [`docs/python-api.md` — `SessionStorage` Protocol](../python-api.md#session-storage).
- `eden/session/_protocol.py` — Protocol definition.
- `eden/session/_claude.py` — the one in-tree implementation.

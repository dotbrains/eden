"""Per-agent session storage Protocol.

Eden's session capture started as a Claude Code-only feature — the
orchestrator's ``_run_loop`` knew the JSONL transcript lived at
``~/.claude/projects/<slug>/<session_id>.jsonl`` and how to mount that
directory into a container. Other agents (codex, opencode, pi) have
their own transcript formats and locations.

Upstream's ADR-0012 moved this knowledge per-agent: every agent can
expose a ``session_storage`` object that the orchestrator delegates to
for three things —

* **Pre-flight mounts** the sandbox needs so the agent can write its
  transcript (e.g. mounting ``~/.claude`` into the container).
* **Capture** the transcript onto the host after each iteration.
* **Transfer** a captured transcript back into the sandbox before the
  next iteration when ``resume_session=`` is in play (not all agents
  need this — claude-code reads from its own mount; codex / pi can
  push the file back to its expected location).

The ``SessionStorage`` Protocol below is intentionally narrow so
existing agents don't have to migrate at once: the orchestrator falls
back to its legacy ``captures_sessions: bool`` shim when an agent does
not expose ``session_storage``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from eden.providers._protocols import SandboxHandle
from eden.providers._types import Mount


@runtime_checkable
class SessionStorage(Protocol):
    """Hook surface for per-agent transcript capture."""

    def extra_mounts(self) -> tuple[Mount, ...]:
        """Mounts the sandbox needs so the agent can write its session.

        Return ``()`` if the agent writes to a path the sandbox already
        has access to (e.g. inside the worktree). For Claude Code on
        Docker, return ``(Mount(host=~/.claude/projects, sandbox=...),)``.
        """
        ...

    def host_capture(
        self,
        *,
        handle: SandboxHandle,
        session_id: str,
        host_repo_path: Path,
        branch: str,
        iteration: int,
    ) -> Path | None:
        """Pull the per-iteration transcript onto the host.

        Returns the path on the host filesystem of the captured
        transcript, or ``None`` if capture is unavailable for this
        iteration (e.g. agent didn't emit a session id yet).

        Implementations may raise ``eden.errors.SessionCaptureFailed``;
        the orchestrator catches it and surfaces a warning event without
        aborting the run.
        """
        ...

    def sandbox_transfer(
        self,
        *,
        handle: SandboxHandle,
        host_session_file: Path,
        session_id: str,
    ) -> None:
        """Push a captured session JSONL back into the sandbox for resume.

        Called only when the orchestrator is starting an iteration with
        ``resume_session=<id>`` and the captured file lives on the host.
        For agents that always write directly to a sandbox-mounted host
        path (claude_code on docker via ``~/.claude``), this can be a
        no-op.
        """
        ...


__all__ = ["SessionStorage"]

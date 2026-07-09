"""Session-storage resolution and per-iteration capture helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from eden.errors import SessionCaptureFailed
from eden.providers._protocols import SandboxHandle
from eden.streaming import StreamEvent

if TYPE_CHECKING:
    from datetime import datetime

    from eden.agents._protocol import Agent
    from eden.logging._file import FileLogSink
    from eden.logging._stdout import StdoutLogSink
    from eden.session._protocol import SessionStorage


def resolve_session_storage(agent: Agent) -> SessionStorage | None:
    """Return custom session storage, or legacy Claude storage when enabled."""
    storage: SessionStorage | None = getattr(agent, "session_storage", None)
    if storage is not None:
        return storage
    if getattr(agent, "captures_sessions", False):
        from eden.session._claude import ClaudeSessionStorage

        return ClaudeSessionStorage()
    return None


def capture_iteration_session(
    *,
    session_storage: SessionStorage | None,
    handle: SandboxHandle,
    session_id: str | None,
    host_repo_path: Path,
    target_branch: str,
    iteration: int,
    since: float,
    agent_name: str,
    timestamp: datetime,
    sink: FileLogSink | StdoutLogSink | None,
) -> Path | None:
    """Capture one iteration transcript, logging soft capture failures."""
    if session_id is None or session_storage is None:
        return None
    try:
        return session_storage.host_capture(
            handle=handle,
            session_id=session_id,
            host_repo_path=host_repo_path,
            branch=target_branch,
            iteration=iteration,
            since=since,
        )
    except SessionCaptureFailed as exc:
        if sink is not None:
            sink.write(
                StreamEvent(
                    type="text",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=timestamp,
                    text=f"[eden] session capture failed: {exc}",
                )
            )
        return None


__all__ = ["capture_iteration_session", "resolve_session_storage"]

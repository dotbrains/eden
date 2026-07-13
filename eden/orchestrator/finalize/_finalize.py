"""Finalize isolated sandbox changes and emit recovery guidance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from eden.logging._file import FileLogSink
from eden.logging._stdout import StdoutLogSink
from eden.orchestrator._summary import format_finalize_line
from eden.orchestrator.finalize._finalize_recovery import format_finalize_recovery
from eden.providers._protocols import SandboxHandle
from eden.streaming import StreamEvent


def _preserve_if_supported(handle: SandboxHandle) -> bool:
    preserve = getattr(handle, "preserve", None)
    if not callable(preserve):
        return False
    try:
        preserve()
    except Exception:
        pass
    return True


def finalize_sandbox(
    *,
    handle: SandboxHandle,
    target_path: Path,
    agent_name: str,
    iteration: int,
    timestamp: Callable[[], datetime],
    sink: FileLogSink | StdoutLogSink | None,
) -> None:
    """Finalize isolated providers and write success/recovery log events."""
    if not hasattr(handle, "finalize"):
        return
    try:
        result = handle.finalize(target=target_path)
    except Exception as exc:
        preserved = _preserve_if_supported(handle)
        if sink is not None:
            sink.write(
                StreamEvent(
                    type="text",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=timestamp(),
                    text=format_finalize_recovery(
                        isolated_path=handle.worktree_path,
                        target_path=target_path,
                        error=exc,
                        preserved=preserved,
                    ),
                )
            )
        return

    if sink is not None:
        sink.write(
            StreamEvent(
                type="text",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=timestamp(),
                text=format_finalize_line(result),
            )
        )
    if result.applied or sink is None:
        return

    preserved = _preserve_if_supported(handle)
    sink.write(
        StreamEvent(
            type="text",
            agent_name=agent_name,
            iteration=iteration,
            timestamp=timestamp(),
            text=format_finalize_recovery(
                isolated_path=handle.worktree_path,
                target_path=target_path,
                files_failed=result.files_changed,
                preserved=preserved,
            ),
        )
    )


__all__ = ["finalize_sandbox"]

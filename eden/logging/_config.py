"""Logging configuration dataclass + factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from eden.streaming import StreamEvent


@dataclass(frozen=True)
class Logging:
    type: Literal["file"]
    path: Path
    level: Literal["debug", "info", "warn", "error"] = "info"
    on_agent_stream_event: Callable[[StreamEvent], None] | None = field(default=None)

    @staticmethod
    def file(
        path: str | Path,
        level: Literal["debug", "info", "warn", "error"] = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
    ) -> Logging:
        """Configure file logging.

        ``on_agent_stream_event`` is invoked for every agent-emitted stream
        event (``text``, ``tool_call``, ``usage``) in addition to writing to
        the log file. Intended for forwarding the agent's output stream to an
        external observability system. Errors raised by the callback are
        swallowed so a broken forwarder cannot kill the run.

        Idle warnings and orchestrator-internal text events are NOT forwarded
        through this callback — use the top-level ``on_event`` argument to
        ``run()`` for those.
        """
        return Logging(
            type="file",
            path=Path(path),
            level=level,
            on_agent_stream_event=on_agent_stream_event,
        )

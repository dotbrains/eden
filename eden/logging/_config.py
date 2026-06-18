"""Logging configuration dataclass + factories."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from eden.errors import InvalidOptions
from eden.streaming import StreamEvent


@dataclass(frozen=True)
class Logging:
    type: Literal["file", "stdout"]
    path: Path | None = None
    level: Literal["debug", "info", "warn", "error"] = "info"
    on_agent_stream_event: Callable[[StreamEvent], None] | None = field(default=None)
    verbose: bool = False
    """When ``True``, emit a ``StreamEvent(type="raw")`` carrying each literal,
    unparsed agent stdout line — written to the log alongside the human-readable
    events and forwarded through ``on_agent_stream_event``. Lets external
    observability systems see the bytes a parser discards (e.g. the JSON behind
    a ``claude`` stream-json line). Off by default. Mirrors upstream's
    ``logging: { verbose: true }`` (v0.10.0)."""

    def __post_init__(self) -> None:
        if self.type not in ("file", "stdout"):
            raise InvalidOptions(
                code="config.invalid_options",
                message=f'Logging.type must be "file" or "stdout"; got {self.type!r}',
            )
        if self.type == "file" and self.path is None:
            raise InvalidOptions(
                code="config.invalid_options",
                message='Logging(type="file") requires a path; use Logging.file(path)',
            )
        if self.type == "stdout" and self.path is not None:
            raise InvalidOptions(
                code="config.invalid_options",
                message='Logging(type="stdout") does not take a path; use Logging.stdout()',
            )

    @staticmethod
    def file(
        path: str | Path,
        level: Literal["debug", "info", "warn", "error"] = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
        verbose: bool = False,
    ) -> Logging:
        """Configure file logging.

        ``on_agent_stream_event`` is invoked for every agent-emitted stream
        event (``text``, ``tool_call``, ``usage``, ``session_id``, and — when
        ``verbose`` — ``raw``) in addition to writing to the log file. Intended
        for forwarding the agent's output stream to an external observability
        system. Errors raised by the callback are swallowed so a broken
        forwarder cannot kill the run.

        ``verbose`` additionally surfaces each literal, unparsed stdout line as
        a ``raw`` event (see :class:`Logging`).

        Idle warnings and orchestrator-internal text events are NOT forwarded
        through this callback — use the top-level ``on_event`` argument to
        ``run()`` for those.
        """
        return Logging(
            type="file",
            path=Path(path),
            level=level,
            on_agent_stream_event=on_agent_stream_event,
            verbose=verbose,
        )

    @staticmethod
    def stdout(
        level: Literal["debug", "info", "warn", "error"] = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
        verbose: bool = False,
    ) -> Logging:
        """Configure stdout logging.

        Formats and redacts events exactly like the file sink but writes them
        to the host process's stdout instead of a log file — useful in CI,
        where the job log is the natural destination and a file under
        ``.eden/logs/`` would go unread. ``RunResult.log_file_path`` is
        ``None`` for stdout-logged runs. Mirrors upstream's
        ``logging: { type: "stdout" }``.

        ``on_agent_stream_event`` and ``verbose`` behave as for :meth:`file`.
        """
        return Logging(
            type="stdout",
            path=None,
            level=level,
            on_agent_stream_event=on_agent_stream_event,
            verbose=verbose,
        )

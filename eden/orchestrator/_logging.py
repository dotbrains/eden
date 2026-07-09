"""Run-loop logging sink setup and agent event forwarding."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from eden.logging._config import Logging
from eden.logging._file import FileLogSink, default_log_path
from eden.logging._stdout import StdoutLogSink
from eden.streaming import StreamEvent

LoopSink = FileLogSink | StdoutLogSink


class LoopLogger:
    def __init__(self, *, config: Logging, sink: LoopSink, log_path: Path | None) -> None:
        self.config = config
        self.sink = sink
        self.log_path = log_path
        self._agent_stream_cb = config.on_agent_stream_event

    @classmethod
    def open(
        cls,
        *,
        logging_cfg: Logging | None,
        host_repo_path: Path,
        branch: str,
        target_branch: str | None,
        name: str | None,
        env_values: tuple[str, ...],
    ) -> LoopLogger:
        config = logging_cfg or Logging.file(
            default_log_path(
                host_repo_path=host_repo_path,
                branch=branch,
                target_branch=target_branch,
                name=name,
            )
        )
        if config.type == "file" and config.path is not None:
            return cls(
                config=config,
                log_path=config.path,
                sink=FileLogSink.open(
                    config.path,
                    level=config.level,
                    env_values=env_values,
                ),
            )
        return cls(
            config=config,
            log_path=None,
            sink=StdoutLogSink(level=config.level, env_values=env_values),
        )

    def write(self, event: StreamEvent) -> None:
        self.sink.write(event)

    def close(self) -> None:
        self.sink.close()

    def forward_agent_event(self, event: StreamEvent) -> None:
        """Fire ``Logging.on_agent_stream_event`` for agent-derived events."""
        if self._agent_stream_cb is None:
            return
        if event.type not in ("text", "tool_call", "usage", "session_id", "raw"):
            return
        try:
            self._agent_stream_cb(event)
        except Exception:
            pass

    def emit_idle_warning(
        self,
        *,
        agent_name: str,
        iteration: int,
        timestamp: datetime,
        minutes_idle: int,
        on_event: Callable[[StreamEvent], None] | None,
    ) -> None:
        event = StreamEvent(
            type="idle_warning",
            agent_name=agent_name,
            iteration=iteration,
            timestamp=timestamp,
            minutes_idle=minutes_idle,
        )
        self.write(event)
        if on_event is not None:
            on_event(event)

    def emit_raw(
        self,
        *,
        agent_name: str,
        iteration: int,
        timestamp: datetime,
        text: str,
    ) -> None:
        if not self.config.verbose:
            return
        event = StreamEvent(
            type="raw",
            agent_name=agent_name,
            iteration=iteration,
            timestamp=timestamp,
            text=text,
        )
        self.write(event)
        self.forward_agent_event(event)


__all__ = ["LoopLogger", "LoopSink"]

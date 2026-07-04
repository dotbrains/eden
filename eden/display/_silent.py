"""SilentDisplay: records every entry, prints nothing.

The primary use is tests — assert against ``display.entries`` to verify
the orchestrator emitted what you expected.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field

from eden.display._types import (
    DisplayEntry,
    IntroEntry,
    Severity,
    SpinnerEntry,
    StatusEntry,
    SummaryEntry,
    TaskLogEntry,
    TextChunkEntry,
    TextEntry,
    ToolCallEntry,
)


@dataclass
class SilentDisplay:
    entries: list[DisplayEntry] = field(default_factory=list)

    def intro(self, title: str) -> None:
        self.entries.append(IntroEntry(title=title))

    def status(self, message: str, severity: Severity = "info") -> None:
        self.entries.append(StatusEntry(message=message, severity=severity))

    def text(self, message: str) -> None:
        self.entries.append(TextEntry(message=message))

    def text_chunk(self, chunk: str) -> None:
        self.entries.append(TextChunkEntry(message=chunk))

    def tool_call(self, name: str, formatted_args: str) -> None:
        self.entries.append(ToolCallEntry(name=name, formatted_args=formatted_args))

    def summary(self, title: str, rows: Mapping[str, str]) -> None:
        self.entries.append(SummaryEntry(title=title, rows=dict(rows)))

    @contextmanager
    def spinner(self, message: str) -> Iterator[None]:
        self.entries.append(SpinnerEntry(message=message))
        yield

    @contextmanager
    def task_log(self, title: str) -> Iterator[Callable[[str], None]]:
        msgs: list[str] = []
        yield msgs.append
        self.entries.append(TaskLogEntry(title=title, messages=tuple(msgs)))

    def reset(self) -> None:
        self.entries.clear()


__all__ = ["SilentDisplay"]

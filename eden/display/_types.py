"""Tagged-union dataclasses for the Display ADT.

The ``DisplayEntry`` union — every kind
of thing a `Display` sink can emit is one of these immutable structs.
Tests use :class:`eden.display.SilentDisplay` to record entries and
assert against them; production sinks (file / terminal) render them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["info", "success", "warn", "error"]


@dataclass(frozen=True)
class IntroEntry:
    title: str
    tag: Literal["intro"] = "intro"


@dataclass(frozen=True)
class StatusEntry:
    message: str
    severity: Severity = "info"
    tag: Literal["status"] = "status"


@dataclass(frozen=True)
class SpinnerEntry:
    message: str
    tag: Literal["spinner"] = "spinner"


@dataclass(frozen=True)
class SummaryEntry:
    title: str
    rows: Mapping[str, str] = field(default_factory=dict)
    tag: Literal["summary"] = "summary"


@dataclass(frozen=True)
class TaskLogEntry:
    title: str
    messages: tuple[str, ...] = ()
    tag: Literal["taskLog"] = "taskLog"


@dataclass(frozen=True)
class TextEntry:
    message: str
    tag: Literal["text"] = "text"


@dataclass(frozen=True)
class ToolCallEntry:
    name: str
    formatted_args: str
    tag: Literal["toolCall"] = "toolCall"


DisplayEntry = (
    IntroEntry
    | StatusEntry
    | SpinnerEntry
    | SummaryEntry
    | TaskLogEntry
    | TextEntry
    | ToolCallEntry
)


__all__ = [
    "DisplayEntry",
    "IntroEntry",
    "Severity",
    "SpinnerEntry",
    "StatusEntry",
    "SummaryEntry",
    "TaskLogEntry",
    "TextEntry",
    "ToolCallEntry",
]

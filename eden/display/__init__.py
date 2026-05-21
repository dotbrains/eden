"""Display abstraction — swappable sinks for orchestrator → user output.

Ports sandcastle's tagged-ADT Display from ``src/Display.ts``. Sinks
shipped:

* :class:`SilentDisplay` — records entries for tests, prints nothing.
* :class:`FileDisplay` — append-only file log; for unattended runs.
* :class:`RichDisplay` — live terminal output powered by ``rich``.

All three satisfy the :class:`Display` Protocol; user code can pass any
of them (or a custom one) wherever eden accepts a display sink. The
core orchestrator does not require a display — call sites that have one
use it, the rest fall back to today's stream events.
"""

from __future__ import annotations

from eden.display._file import FileDisplay
from eden.display._protocol import Display
from eden.display._rich import RichDisplay
from eden.display._silent import SilentDisplay
from eden.display._types import (
    DisplayEntry,
    IntroEntry,
    Severity,
    SpinnerEntry,
    StatusEntry,
    SummaryEntry,
    TaskLogEntry,
    TextEntry,
    ToolCallEntry,
)

__all__ = [
    "Display",
    "DisplayEntry",
    "FileDisplay",
    "IntroEntry",
    "RichDisplay",
    "Severity",
    "SilentDisplay",
    "SpinnerEntry",
    "StatusEntry",
    "SummaryEntry",
    "TaskLogEntry",
    "TextEntry",
    "ToolCallEntry",
]

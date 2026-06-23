"""Display Protocol — the sink surface for orchestrator → user output.

A ``Display`` accepts seven kinds of events:

* ``intro(title)`` — banner at the top of a run.
* ``status(message, severity)`` — single-line status, severity tagged.
* ``text(message)`` — plain message line.
* ``tool_call(name, formatted_args)`` — agent tool invocation, distinct
  from regular text so terminal sinks can dim or indent.
* ``summary(title, rows)`` — boxed key/value summary at end of run.
* ``spinner(message)`` — context manager wrapping a long operation; the
  sink renders a spinner / progress indicator while the block runs.
* ``task_log(title)`` — context manager yielding a ``message(str)``
  callback; lines pushed during the block are collected and emitted on
  exit (success or failure).

Two notable design points:

* Python lacks Effect.Effect, so ``spinner`` / ``task_log`` are
  context managers rather than higher-order effect wrappers.
* ``task_log`` exposes the message-sink callback on ``__enter__`` rather
  than passing it to an effect closure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Protocol

from eden.display._types import Severity


class Display(Protocol):
    def intro(self, title: str) -> None: ...

    def status(self, message: str, severity: Severity = "info") -> None: ...

    def text(self, message: str) -> None: ...

    def tool_call(self, name: str, formatted_args: str) -> None: ...

    def summary(self, title: str, rows: Mapping[str, str]) -> None: ...

    @contextmanager
    def spinner(self, message: str) -> Iterator[None]:  # pragma: no cover - Protocol
        yield

    @contextmanager
    def task_log(
        self, title: str
    ) -> Iterator[Callable[[str], None]]:  # pragma: no cover - Protocol
        def _noop(_: str) -> None:
            return None

        yield _noop


__all__ = ["Display"]

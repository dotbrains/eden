"""FileDisplay: append-only file sink for run output.

Used when eden runs unattended (CI, scheduled jobs) and the operator
wants the orchestrator's narration captured to a file rather than
streamed live.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from eden.display._types import Severity


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class FileDisplay:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._mid_line = False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._delimiter()

    @property
    def path(self) -> Path:
        return self._path

    def _delimiter(self) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(f"\n--- Run started: {_now()} ---\n")
        self._mid_line = False

    def _append(self, line: str) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            if self._mid_line:
                f.write("\n")
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
        self._mid_line = False

    def _append_raw(self, chunk: str) -> None:
        if not chunk:
            return
        with self._path.open("a", encoding="utf-8") as f:
            f.write(chunk)
        self._mid_line = not chunk.endswith("\n")

    def intro(self, title: str) -> None:
        # FileDisplay deliberately skips the intro banner — file logs
        # don't benefit from visual separators beyond the delimiter we
        # already wrote on construction.
        return None

    def status(self, message: str, severity: Severity = "info") -> None:
        del severity  # All severities flatten to a single log line.
        self._append(message)

    def text(self, message: str) -> None:
        self._append(message)

    def text_chunk(self, chunk: str) -> None:
        self._append_raw(chunk)

    def tool_call(self, name: str, formatted_args: str) -> None:
        self._append(f"{name}({formatted_args})")

    def summary(self, title: str, rows: Mapping[str, str]) -> None:
        lines = [title]
        lines.extend(f"  {k}: {v}" for k, v in rows.items())
        self._append("\n".join(lines))

    @contextmanager
    def spinner(self, message: str) -> Iterator[None]:
        self._append(f"{message}...")
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            self._append(f"{message} done ({elapsed:.1f}s)")

    @contextmanager
    def task_log(self, title: str) -> Iterator[Callable[[str], None]]:
        self._append(title)
        msgs: list[str] = []
        start = time.monotonic()
        try:
            yield msgs.append
            elapsed = time.monotonic() - start
            for m in msgs:
                self._append(f"  {m}")
            self._append(f"{title} done ({elapsed:.1f}s)")
        except BaseException:
            elapsed = time.monotonic() - start
            for m in msgs:
                self._append(f"  {m}")
            self._append(f"{title} failed ({elapsed:.1f}s)")
            raise


__all__ = ["FileDisplay"]

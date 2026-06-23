"""File-sink writer + default log-path generator."""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Literal

from eden.logging._format import format_line
from eden.logging._redact import redact
from eden.streaming import StreamEvent

# Sanitize: collapse path separators, whitespace, and Windows-illegal filename
# characters (< > : " * ? |) into a single dash. Keep alphanumerics, dot,
# underscore, and dash.
_BRANCH_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")
_BRANCH_MAX = 64
_NAME_MAX_WHEN_TRUNCATED = 20


def _sanitize_label(value: str) -> str:
    return _BRANCH_SANITIZE.sub("-", value).strip("-")


def _join_log_labels(parts: list[str]) -> str:
    safe_parts = [safe for part in parts if (safe := _sanitize_label(part))]
    if not safe_parts:
        return "run"
    safe = "-".join(safe_parts)
    if len(safe) <= _BRANCH_MAX:
        return safe
    if len(safe_parts) == 1:
        return safe[:_BRANCH_MAX]

    # Preserve the final label, usually ``name``, because that is the
    # human-chosen discriminator in parallel runs. Long target/branch labels
    # are still visible as the prefix.
    suffix = safe_parts[-1][:_NAME_MAX_WHEN_TRUNCATED]
    prefix = "-".join(safe_parts[:-1])
    prefix_len = max(1, _BRANCH_MAX - len(suffix) - 1)
    return f"{prefix[:prefix_len].rstrip('-')}-{suffix}"


def default_log_path(
    *,
    host_repo_path: Path,
    branch: str,
    target_branch: str | None = None,
    name: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Compute a default run log path under ``<repo>/.eden/logs``.

    The filename includes the resolved worktree branch, and optionally the
    target branch and caller-provided run name. That makes parallel runs easier
    to distinguish while keeping the legacy ``<branch>-<utc>.log`` shape when
    the extra labels are omitted.
    """
    parts: list[str] = []
    if target_branch:
        parts.append(target_branch)
    parts.append(branch)
    if name:
        parts.append(name)
    safe = _join_log_labels(parts)
    moment = now or datetime.now(UTC)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    return host_repo_path / ".eden" / "logs" / f"{safe}-{stamp}.log"


class FileLogSink:
    """Append-mode plain-text log sink. Redaction applied on every write.

    Thread-safe: ``write`` and ``close`` are serialized by an internal lock.
    """

    def __init__(
        self,
        *,
        path: Path,
        level: Literal["debug", "info", "warn", "error"],
        env_values: tuple[str, ...],
        fp: IO[str],
    ) -> None:
        self.path = path
        self.level = level
        self._env_values = env_values
        self._fp: IO[str] | None = fp
        self._lock = threading.Lock()

    @staticmethod
    def open(
        path: Path,
        *,
        level: Literal["debug", "info", "warn", "error"],
        env_values: Iterable[str],
    ) -> FileLogSink:
        path.parent.mkdir(parents=True, exist_ok=True)
        fp = path.open("a", encoding="utf-8")
        # Per-run delimiter so multiple runs sharing one log file are
        # visually separable. UTC ISO-8601 with seconds precision.
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        fp.write(f"--- Run started: {ts} ---\n")
        fp.flush()
        return FileLogSink(
            path=path,
            level=level,
            env_values=tuple(env_values),
            fp=fp,
        )

    def write(self, event: StreamEvent) -> None:
        with self._lock:
            if self._fp is None:
                return
            line = format_line(event, level=self.level)
            line = redact(line, env_values=self._env_values)
            self._fp.write(line + "\n")
            self._fp.flush()

    def close(self) -> None:
        with self._lock:
            if self._fp is None:
                return
            try:
                self._fp.flush()
                self._fp.close()
            finally:
                self._fp = None

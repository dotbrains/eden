"""Call-log types for the test bind-mount sandbox provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ExecCall:
    cmd: str
    cwd: Path | None
    env_keys: tuple[str, ...]
    timeout: float | None
    stdin: str | None = None


@dataclass(frozen=True)
class CopyCall:
    direction: str
    host: Path
    sandbox: Path


@dataclass
class CallLog:
    """Append-only record of every call dispatched through the test handle."""

    exec_calls: list[ExecCall] = field(default_factory=list)
    copy_calls: list[CopyCall] = field(default_factory=list)
    closed: bool = False

    def reset(self) -> None:
        self.exec_calls.clear()
        self.copy_calls.clear()
        self.closed = False


__all__ = ["CallLog", "CopyCall", "ExecCall"]

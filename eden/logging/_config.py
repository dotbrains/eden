"""Logging configuration dataclass + factory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Logging:
    type: Literal["file"]
    path: Path
    level: Literal["debug", "info", "warn", "error"] = "info"

    @staticmethod
    def file(
        path: str | Path,
        level: Literal["debug", "info", "warn", "error"] = "info",
    ) -> Logging:
        return Logging(type="file", path=Path(path), level=level)

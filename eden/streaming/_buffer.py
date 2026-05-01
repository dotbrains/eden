"""Accumulate partial chunks into newline-delimited lines."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextDeltaBuffer:
    _residual: str = ""
    _emitted: int = field(default=0, init=False, repr=False)

    def feed(self, chunk: str) -> list[str]:
        if not chunk:
            return []
        combined = self._residual + chunk
        if "\n" not in combined:
            self._residual = combined
            return []
        lines = combined.split("\n")
        self._residual = lines.pop()
        return lines

    def flush(self) -> str:
        out = self._residual
        self._residual = ""
        return out

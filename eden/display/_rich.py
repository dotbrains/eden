"""RichDisplay: live terminal sink powered by the ``rich`` library.

Eden already depends on rich (pyproject), so we lean on
``rich.console.Console`` for colored output and ``rich.status.Status``
for spinners.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import IO, Any

from eden.display._types import Severity

_SEVERITY_STYLE: dict[Severity, str] = {
    "info": "bold cyan",
    "success": "bold green",
    "warn": "bold yellow",
    "error": "bold red",
}


class RichDisplay:
    """Live terminal display.

    ``console=`` accepts an injected ``rich.console.Console`` (useful for
    tests that want to capture output via ``record=True`` /
    ``file=StringIO``). Defaults to a fresh ``Console()``.
    """

    def __init__(self, console: Any | None = None, *, file: IO[str] | None = None) -> None:
        if console is None:
            from rich.console import Console

            console = Console(file=file) if file is not None else Console()
        self._console = console

    def intro(self, title: str) -> None:
        self._console.rule(f"[bold inverse] {title} [/]")

    def status(self, message: str, severity: Severity = "info") -> None:
        style = _SEVERITY_STYLE.get(severity, "white")
        prefix = {"info": "•", "success": "✓", "warn": "!", "error": "✗"}.get(severity, "•")
        self._console.print(f"[{style}]{prefix} {message}[/]")

    def text(self, message: str) -> None:
        self._console.print(message)

    def tool_call(self, name: str, formatted_args: str) -> None:
        self._console.print(f"[dim]{name}({formatted_args})[/dim]")

    def summary(self, title: str, rows: Mapping[str, str]) -> None:
        # rich.table.Table would be heavier; for one-shot summaries a
        # plain block of bold-key / dim-value lines reads naturally.
        self._console.print(f"[bold]{title}[/bold]")
        for k, v in rows.items():
            self._console.print(f"  [bold]{k}[/bold]: [dim]{v}[/dim]")

    @contextmanager
    def spinner(self, message: str) -> Iterator[None]:
        # rich.status.Status — auto-updates a small spinner glyph until
        # the context exits.
        with self._console.status(message):
            start = time.monotonic()
            try:
                yield
            finally:
                elapsed = time.monotonic() - start
                self._console.print(f"  [dim]{message} done ({elapsed:.1f}s)[/dim]")

    @contextmanager
    def task_log(self, title: str) -> Iterator[Callable[[str], None]]:
        self._console.print(f"[bold]{title}[/bold]")
        msgs: list[str] = []

        def _append(msg: str) -> None:
            msgs.append(msg)

        start = time.monotonic()
        try:
            yield _append
            elapsed = time.monotonic() - start
            for m in msgs:
                self._console.print(f"  [dim]{m}[/dim]")
            self._console.print(f"  [green]✓[/green] {title} ({elapsed:.1f}s)")
        except BaseException:
            elapsed = time.monotonic() - start
            for m in msgs:
                self._console.print(f"  [dim]{m}[/dim]")
            self._console.print(f"  [red]✗[/red] {title} failed ({elapsed:.1f}s)")
            raise


__all__ = ["RichDisplay"]

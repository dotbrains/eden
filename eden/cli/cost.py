"""`eden cost` — aggregate token usage from captured session JSONLs.

Walks ``<repo>/.eden/sessions/<branch>/iter-*-<session-id>.jsonl`` and sums
the ``usage`` recorded on each session's terminal ``result`` line. Prints a
per-branch breakdown plus an overall total.

Usage records are emitted by Claude Code's stream-json output and captured
verbatim by ``eden.session.capture_session``; the sums match what
``RunResult.usage`` reports for individual runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eden._types import Usage

console = Console()


@dataclass
class _Bucket:
    sessions: int = 0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    def add(self, usage: Usage) -> None:
        self.iterations += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cache_creation_tokens += usage.cache_creation_input_tokens
        self.cache_read_tokens += usage.cache_read_input_tokens

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )


def _parse_session_usage(jsonl: Path) -> Usage | None:
    """Return the most recent ``result``-line usage in ``jsonl``, or None.

    Claude Code emits one ``result`` line per session (at the end), but if a
    session was resumed mid-run, multiple ``result`` lines may appear. The
    last one represents the cumulative usage for that session.
    """
    last_usage: Usage | None = None
    try:
        with jsonl.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") != "result":
                    continue
                raw = obj.get("usage")
                if not isinstance(raw, dict):
                    continue
                try:
                    last_usage = Usage(
                        input_tokens=int(raw.get("input_tokens", 0)),
                        cache_creation_input_tokens=int(raw.get("cache_creation_input_tokens", 0)),
                        cache_read_input_tokens=int(raw.get("cache_read_input_tokens", 0)),
                        output_tokens=int(raw.get("output_tokens", 0)),
                    )
                except (TypeError, ValueError):
                    continue
    except OSError:
        return None
    return last_usage


def _fmt_int(n: int) -> str:
    return f"{n:>12,}"


def cost_command(
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to inspect"),  # noqa: B008
    branch: str | None = typer.Option(None, "--branch", help="Limit to one sanitized branch dir"),
) -> None:
    """Aggregate token usage from .eden/sessions/ session JSONLs."""
    repo = (cwd or Path.cwd()).resolve()
    sessions_dir = repo / ".eden" / "sessions"
    if not sessions_dir.is_dir():
        console.print(f"[yellow]no .eden/sessions/ in {repo}[/yellow]")
        raise typer.Exit(code=0)

    by_branch: dict[str, _Bucket] = {}
    overall = _Bucket()
    branch_dirs = sorted(p for p in sessions_dir.iterdir() if p.is_dir())
    if branch is not None:
        branch_dirs = [p for p in branch_dirs if p.name == branch]

    for branch_dir in branch_dirs:
        bucket = _Bucket()
        sessions: set[str] = set()
        for jsonl in sorted(branch_dir.glob("iter-*-*.jsonl")):
            usage = _parse_session_usage(jsonl)
            if usage is None:
                continue
            bucket.add(usage)
            overall.add(usage)
            # session_id is the part after the last "-" before ".jsonl"
            stem = jsonl.stem  # iter-<n>-<session-id>
            try:
                sid = stem.split("-", 2)[2]
            except IndexError:
                sid = stem
            sessions.add(sid)
        bucket.sessions = len(sessions)
        if bucket.iterations > 0:
            by_branch[branch_dir.name] = bucket

    if not by_branch:
        console.print(f"[yellow]no usage found under {sessions_dir.relative_to(repo)}[/yellow]")
        raise typer.Exit(code=0)

    overall.sessions = sum(b.sessions for b in by_branch.values())
    table = Table(
        title=f"Token usage — {sessions_dir.relative_to(repo)}",
        title_justify="left",
    )
    table.add_column("branch", style="cyan", no_wrap=True)
    table.add_column("sessions", justify="right")
    table.add_column("iters", justify="right")
    table.add_column("input", justify="right")
    table.add_column("output", justify="right")
    table.add_column("cache-create", justify="right")
    table.add_column("cache-read", justify="right")
    table.add_column("total", justify="right", style="bold")

    for name, b in sorted(by_branch.items()):
        table.add_row(
            name,
            str(b.sessions),
            str(b.iterations),
            _fmt_int(b.input_tokens),
            _fmt_int(b.output_tokens),
            _fmt_int(b.cache_creation_tokens),
            _fmt_int(b.cache_read_tokens),
            _fmt_int(b.total_tokens),
        )
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        str(overall.sessions),
        str(overall.iterations),
        _fmt_int(overall.input_tokens),
        _fmt_int(overall.output_tokens),
        _fmt_int(overall.cache_creation_tokens),
        _fmt_int(overall.cache_read_tokens),
        _fmt_int(overall.total_tokens),
    )
    console.print(table)

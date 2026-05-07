"""`eden replay` — pretty-print a captured session's transcript.

Reads a session JSONL captured by ``eden.session.capture_session`` and
formats it as a human-readable transcript: system messages, user turns,
assistant text, and tool uses. Useful for debugging an agent run after
the fact without re-executing it.

Argument forms:

- ``eden replay <path/to/iter-N-SESSION.jsonl>`` — explicit path.
- ``eden replay <branch>/<iter>`` — picks
  ``.eden/sessions/<branch>/iter-<iter>-*.jsonl``.
- ``eden replay <session-id>`` — searches under ``.eden/sessions/`` for a
  filename ending in ``-<session-id>.jsonl``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def _resolve_session_path(target: str, *, repo: Path) -> Path:
    """Return the session JSONL file matching ``target``.

    Resolution order:
    1. ``target`` is a path that exists on disk → use as-is.
    2. ``target`` looks like ``<branch>/<iter>`` → glob
       ``.eden/sessions/<branch>/iter-<iter>-*.jsonl``.
    3. Otherwise → glob ``.eden/sessions/**/-<target>.jsonl``.

    Raises ``typer.BadParameter`` if no match is found or multiple match.
    """
    direct = Path(target)
    if direct.is_file():
        return direct.resolve()

    sessions = repo / ".eden" / "sessions"
    if not sessions.is_dir():
        raise typer.BadParameter(f"no .eden/sessions/ in {repo}")

    if "/" in target:
        branch, _, iter_part = target.partition("/")
        try:
            iter_n = int(iter_part)
        except ValueError as exc:
            raise typer.BadParameter(
                f"invalid <branch>/<iter> form {target!r}: iter must be an integer"
            ) from exc
        matches = sorted((sessions / branch).glob(f"iter-{iter_n}-*.jsonl"))
    else:
        matches = sorted(sessions.glob(f"**/iter-*-{target}.jsonl"))

    if not matches:
        raise typer.BadParameter(f"no session matches {target!r} under {sessions}")
    if len(matches) > 1:
        joined = "\n  ".join(str(p) for p in matches)
        raise typer.BadParameter(
            f"{target!r} is ambiguous; matched:\n  {joined}\npass an explicit path"
        )
    return matches[0].resolve()


def _format_user(obj: dict[str, Any]) -> str | None:
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                elif block.get("type") == "tool_result":
                    raw = block.get("content")
                    if isinstance(raw, str):
                        parts.append(f"[tool result] {raw}")
        if parts:
            return "\n".join(parts)
    return None


def _format_assistant(obj: dict[str, Any]) -> tuple[list[str], list[tuple[str, dict[str, Any]]]]:
    """Return (text-blocks, [(tool_name, tool_input), ...]) from an assistant entry."""
    msg = obj.get("message")
    text_blocks: list[str] = []
    tool_uses: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(msg, dict):
        return text_blocks, tool_uses
    content = msg.get("content")
    if not isinstance(content, list):
        return text_blocks, tool_uses
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str):
                text_blocks.append(text)
        elif btype == "tool_use":
            name = block.get("name")
            tool_input = block.get("input") or {}
            if isinstance(name, str) and isinstance(tool_input, dict):
                tool_uses.append((name, tool_input))
    return text_blocks, tool_uses


def _short_input(tool_input: dict[str, Any]) -> str:
    """Return a one-line summary of a tool_use's input args."""
    parts = []
    for k, v in tool_input.items():
        v_str = str(v)
        if len(v_str) > 80:
            v_str = v_str[:77] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def replay_command(
    target: str = typer.Argument(..., help="Session path, <branch>/<iter>, or session-id"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo containing .eden/sessions"),  # noqa: B008
    show_tools: bool = typer.Option(True, "--tools/--no-tools", help="Show tool_use blocks"),
) -> None:
    """Pretty-print a captured session JSONL transcript."""
    repo = (cwd or Path.cwd()).resolve()
    path = _resolve_session_path(target, repo=repo)
    console.print(f"[dim]session:[/dim] {path}")
    console.rule()

    try:
        fp = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise typer.BadParameter(f"cannot read {path}: {exc}") from exc

    final_usage: dict[str, Any] | None = None
    with fp:
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
            entry_type = obj.get("type")
            if entry_type == "system":
                # Initial system entry carries metadata; show only the model.
                model = obj.get("model")
                if isinstance(model, str):
                    console.print(f"[dim]system: model={model}[/dim]")
            elif entry_type == "user":
                text = _format_user(obj)
                if text:
                    console.print(Panel(text, title="user", border_style="cyan", expand=False))
            elif entry_type == "assistant":
                text_blocks, tool_uses = _format_assistant(obj)
                for text in text_blocks:
                    console.print(
                        Panel(Markdown(text), title="assistant", border_style="green", expand=False)
                    )
                if show_tools:
                    for name, tool_input in tool_uses:
                        console.print(
                            f"[yellow]→ {name}[/yellow]([dim]{_short_input(tool_input)}[/dim])"
                        )
            elif entry_type == "result":
                usage = obj.get("usage")
                if isinstance(usage, dict):
                    final_usage = usage

    if final_usage is not None:
        console.rule()
        in_t = final_usage.get("input_tokens", 0)
        out_t = final_usage.get("output_tokens", 0)
        cc_t = final_usage.get("cache_creation_input_tokens", 0)
        cr_t = final_usage.get("cache_read_input_tokens", 0)
        console.print(
            f"[dim]usage:[/dim] input={in_t:,} output={out_t:,} "
            f"cache-create={cc_t:,} cache-read={cr_t:,}"
        )

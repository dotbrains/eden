"""Public factory for the Claude Code-backed Agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from eden.agents.claude_code._agent import _ClaudeCodeAgent


def claude_code(
    model: str,
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    extra_args: tuple[str, ...] = (),
) -> _ClaudeCodeAgent:
    """Build a Claude Code-backed Agent.

    Args:
        model: Claude model id (threaded into ``--model``).
        name: Agent identifier (default ``"claude-code"``).
        effort: Optional ``--thinking-effort`` level.
        env: Per-agent environment additions (merged by the orchestrator).
        capture_sessions: When ``True``, the orchestrator post-processes each
            iteration's session JSONL into ``.eden/sessions/...``.
        extra_args: Escape hatch for unsurfaced Claude CLI flags. Inserted
            before the ``--`` prompt separator.
    """
    return _ClaudeCodeAgent(
        name=name,
        model=model,
        captures_sessions=capture_sessions,
        _effort=effort,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
    )


__all__ = ["claude_code"]

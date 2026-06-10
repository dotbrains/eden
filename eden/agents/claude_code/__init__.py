"""Public factory for the Claude Code-backed Agent."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from eden.agents.claude_code._agent import _ClaudeCodeAgent

_DEFAULT_MODEL = "claude-opus-4-7"


def claude_code(
    model: str = _DEFAULT_MODEL,
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_skip_permissions: bool = False,
    extra_args: tuple[str, ...] = (),
    flox_env: str | Path | None = None,
) -> _ClaudeCodeAgent:
    """Build a Claude Code-backed Agent.

    Args:
        model: Claude model id (threaded into ``--model``). Defaults to
            ``"claude-opus-4-7"`` — bump in lockstep with the
            latest-stable Opus release; pin explicitly for reproducible
            runs.
        name: Agent identifier (default ``"claude-code"``).
        effort: Optional ``--thinking-effort`` level.
        env: Per-agent environment additions (merged by the orchestrator).
        capture_sessions: When ``True``, the orchestrator post-processes each
            iteration's session JSONL into ``.eden/sessions/...``.
        dangerously_skip_permissions: When ``True``, appends
            ``--dangerously-skip-permissions`` so Claude does not block on
            per-tool permission prompts. Safe inside an isolated sandbox
            (docker/podman/vercel/daytona/isolated providers); think twice
            before enabling for ``no_sandbox()``, where Claude would gain
            unprompted access to the host filesystem.
        extra_args: Escape hatch for unsurfaced Claude CLI flags. Inserted
            before the ``--`` prompt separator.
        flox_env: Optional path to a directory containing a Flox env
            (``.flox/env/manifest.toml``). When set, the orchestrator runs the
            agent CLI inside it via ``flox activate -d <dir> -- <argv>`` so the
            agent gets its own declared toolchain. Enforced when present: a
            missing manifest or ``flox`` binary raises ``FloxEnvError`` (set
            ``EDEN_ALLOW_NO_FLOX=1`` to skip activation without Flox installed).
    """
    from eden.session._claude import ClaudeSessionStorage

    return _ClaudeCodeAgent(
        name=name,
        model=model,
        captures_sessions=capture_sessions,
        _effort=effort,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
        _dangerously_skip_permissions=dangerously_skip_permissions,
        _session_storage=ClaudeSessionStorage() if capture_sessions else None,
        flox_env=flox_env,
    )


__all__ = ["claude_code"]

"""RunResult continuation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from eden.errors import InvalidOptions

if TYPE_CHECKING:
    from eden._types import RunResult


def continue_run_result(
    result: RunResult,
    *,
    prompt: str,
    fork: bool,
    overrides: dict[str, Any],
) -> RunResult:
    """Shared implementation of ``RunResult.resume`` / ``.fork``."""
    if result._ctx is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=("RunResult has no captured run context; cannot resume / fork"),
            hint="resume / fork only work on results returned by eden.run()",
        )
    if result.session_id is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "RunResult has no session_id; cannot resume / fork. The agent "
                "either did not capture a session or did not emit one this run."
            ),
            hint=(
                "ensure the agent has capture_sessions=True (default for "
                "claude_code / codex / pi) and that the iteration produced a "
                "session id"
            ),
        )

    from eden.orchestrator import run as _run

    kwargs: dict[str, Any] = {
        "agent": result._ctx.agent,
        "sandbox": result._ctx.sandbox,
        "cwd": result._ctx.cwd,
        "prompt": prompt,
        "resume_session": result.session_id,
        "fork_session": fork,
    }
    kwargs.update(overrides)
    return _run(**kwargs)


__all__ = ["continue_run_result"]

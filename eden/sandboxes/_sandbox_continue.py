"""Resume/fork helpers for reusable sandbox sessions."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from eden._types import RunResult
from eden.errors import InvalidOptions


def continue_sandbox_session(
    *,
    run: Callable[..., RunResult],
    last_session_id: str | None,
    prompt: str,
    fork: bool,
    overrides: Mapping[str, object],
) -> RunResult:
    if last_session_id is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"no captured session to {'fork' if fork else 'resume'}; "
                "call run() first on an agent that captures sessions"
            ),
            hint=(
                "claude_code captures sessions by default; cli_agent needs capture_sessions=True"
            ),
        )
    kwargs: dict[str, object] = dict(overrides)
    kwargs["prompt"] = prompt
    kwargs["resume_session"] = last_session_id
    kwargs["fork_session"] = fork
    return run(**kwargs)


__all__ = ["continue_sandbox_session"]

"""Runtime error classes re-exported through ``eden.errors``."""

from __future__ import annotations

from pathlib import Path

from eden._error_base import EdenError, _format


class StructuredOutputError(EdenError):
    """Raised when ``run(output=...)`` fails to extract or validate a payload."""

    def __init__(
        self,
        *,
        code: str = "output.extraction_failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        tag: str,
        raw_matched: str | None,
        branch: str,
        preserved_worktree_path: object = None,
        session_id: str | None = None,
        session_file_path: object = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.tag = tag
        self.raw_matched = raw_matched
        self.branch = branch
        self.preserved_worktree_path = preserved_worktree_path
        self.session_id = session_id
        self.session_file_path = session_file_path
        super().__init__(_format(code, message, hint))


class CopyToWorktreeError(EdenError):
    """Raised when the isolated provider's worktree clone fails or times out."""

    def __init__(
        self,
        *,
        code: str = "copy.to_worktree_failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        source: object = None,
        target: object = None,
        timeout: float | None = None,
        timed_out: bool = False,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.source = source
        self.target = target
        self.timeout = timeout
        self.timed_out = timed_out
        super().__init__(_format(code, message, hint))


class AgentError(EdenError):
    """Raised when the agent subprocess exits non-zero without a completion signal."""

    def __init__(
        self,
        *,
        code: str = "agent.failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        agent_name: str = "",
        exit_code: int | None = None,
        stderr: str = "",
        parsed_error: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.agent_name = agent_name
        self.exit_code = exit_code
        self.stderr = stderr
        self.parsed_error = parsed_error
        super().__init__(_format(code, message, hint))


class SessionCaptureFailed(EdenError):
    """Raised when capture_session() can't locate, read, or write the JSONL."""

    def __init__(
        self,
        *,
        code: str = "session.capture_failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class SessionNotFound(EdenError):
    """Raised when ``resume_session=<id>`` references no host-side transcript."""

    def __init__(
        self,
        *,
        session_id: str,
        agent_name: str,
        expected_path: Path | None = None,
        hint: str | None = None,
    ) -> None:
        self.code = "session.not_found"
        self.session_id = session_id
        self.agent_name = agent_name
        self.expected_path = expected_path
        path_suffix = f" (expected at {expected_path})" if expected_path is not None else ""
        message = (
            f"resume_session={session_id!r} not found on host for agent {agent_name!r}{path_suffix}"
        )
        self.message = message
        self.hint = hint or (
            "verify the id is correct, or list captured sessions under <repo>/.eden/sessions/"
        )
        super().__init__(_format(self.code, message, self.hint))

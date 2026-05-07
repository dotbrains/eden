"""Base + Phase 3a runtime errors for the eden package.

Convention: every concrete error accepts a ``cause`` keyword argument that
stores the originating exception as a named attribute. ``cause`` does NOT
set ``__cause__``; callers who want chained tracebacks must use
``raise XError(..., cause=e) from e``.
"""

from __future__ import annotations

import builtins


class EdenError(Exception):
    """Base for every error raised from the eden package."""


def _format(code: str, message: str, hint: str | None) -> str:
    """Return ``[code] message`` with an optional newline-prefixed hint."""
    base = f"[{code}] {message}"
    return f"{base}\nhint: {hint}" if hint else base


class ConfigError(EdenError):
    """Configuration / kwarg / environment problem detected before any side effect."""


class InvalidOptions(ConfigError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class PromptError(ConfigError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class EnvMergeError(ConfigError):
    def __init__(
        self,
        *,
        code: str = "config.env_merge",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class CwdError(ConfigError):
    def __init__(
        self,
        *,
        code: str = "config.cwd",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class HookError(EdenError):
    """Base for host- and sandbox-hook failures."""


class HookFailed(HookError):
    def __init__(
        self,
        *,
        code: str = "hook.failed",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class HookTimeout(HookError):
    def __init__(
        self,
        *,
        code: str = "hook.timeout",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class EdenTimeoutError(EdenError, builtins.TimeoutError):
    """Time-budget exceeded. Subclasses builtins.TimeoutError so callers can
    catch either or both."""


class IdleTimeout(EdenTimeoutError):
    def __init__(
        self,
        *,
        code: str = "timeout.idle",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class StepTimeout(EdenTimeoutError):
    def __init__(
        self,
        *,
        code: str = "timeout.step",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(_format(code, message, hint))


class Aborted(EdenError):
    def __init__(self, *, reason: str = "abort-signal") -> None:
        self.reason = reason
        super().__init__(f"aborted: {reason}")


class StructuredOutputError(EdenError):
    """Raised when ``run(output=...)`` fails to extract or validate a payload.

    Failure modes:
    - The configured XML tag was not found in stdout (``raw_matched`` is ``None``).
    - The tag contents failed ``json.loads`` (``cause`` carries the parse error).
    - The schema callable raised (``cause`` carries the validation error).

    Carries ``branch`` and ``preserved_worktree_path`` so callers can recover
    side effects without losing the run's commits and worktree state.
    """

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
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.tag = tag
        self.raw_matched = raw_matched
        self.branch = branch
        self.preserved_worktree_path = preserved_worktree_path
        super().__init__(_format(code, message, hint))


class SessionCaptureFailed(EdenError):
    """Raised when capture_session() can't locate, read, or write the JSONL.

    Always a soft failure — the orchestrator catches it and surfaces a warning
    event without aborting the run.
    """

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


class RestError(EdenError):
    """Non-2xx response from a REST API. Carries status, body, url for debugging.

    `status=0` indicates a connection-level failure (no HTTP response).
    Catch this at the orchestrator boundary; never let it leak into user
    code as a generic `RequestException`.
    """

    def __init__(
        self,
        *,
        code: str = "rest.error",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.status = status
        self.body = body
        self.url = url
        super().__init__(_format(code, message, hint))


class RestAuthError(RestError):
    """401/403 — Bearer token rejected or insufficient permissions."""

    def __init__(
        self,
        *,
        code: str = "rest.auth",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            cause=cause,
            status=status,
            body=body,
            url=url,
        )


class RestNotFoundError(RestError):
    """404 — resource (sandbox/file) not found."""

    def __init__(
        self,
        *,
        code: str = "rest.not_found",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            cause=cause,
            status=status,
            body=body,
            url=url,
        )


class RestRateLimited(RestError):
    """429 — server-side rate-limit; retry already exhausted."""

    def __init__(
        self,
        *,
        code: str = "rest.rate_limited",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            cause=cause,
            status=status,
            body=body,
            url=url,
        )

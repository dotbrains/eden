"""REST-provider error classes re-exported through ``eden.errors``."""

from __future__ import annotations

from eden._error_base import EdenError, _format
from eden._redact import redact_secrets


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
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.message = redact_secrets(message)
        self.hint = hint
        self.cause = cause
        self.status = status
        self.body = redact_secrets(body)
        self.url = redact_secrets(url)
        self.retryable = retryable
        super().__init__(_format(code, self.message, hint))


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
        retryable: bool = False,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            cause=cause,
            status=status,
            body=body,
            url=url,
            retryable=retryable,
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
        retryable: bool = False,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            cause=cause,
            status=status,
            body=body,
            url=url,
            retryable=retryable,
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
        retryable: bool = True,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            cause=cause,
            status=status,
            body=body,
            url=url,
            retryable=retryable,
        )

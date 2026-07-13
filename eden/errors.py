"""Runtime errors for the eden package.

Concrete errors store ``cause`` without setting ``__cause__``. Callers who
want chained tracebacks must use ``raise XError(..., cause=e) from e``.
"""

from __future__ import annotations

import builtins

from eden._error_base import EdenError as EdenError
from eden._error_base import _format as _format
from eden._rest_errors import RestAuthError as RestAuthError
from eden._rest_errors import RestError as RestError
from eden._rest_errors import RestNotFoundError as RestNotFoundError
from eden._rest_errors import RestRateLimited as RestRateLimited
from eden._runtime_errors import AgentError as AgentError
from eden._runtime_errors import CopyToWorktreeError as CopyToWorktreeError
from eden._runtime_errors import SessionCaptureFailed as SessionCaptureFailed
from eden._runtime_errors import SessionNotFound as SessionNotFound
from eden._runtime_errors import StructuredOutputError as StructuredOutputError


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


class FloxEnvError(ConfigError):
    """Raised when an agent declares a ``flox_env`` that cannot be activated.

    The declared env must contain ``.flox/env/manifest.toml`` and activation
    requires ``flox`` on ``PATH`` unless ``EDEN_ALLOW_NO_FLOX=1`` is set.
    """

    def __init__(
        self,
        *,
        code: str = "config.flox_env",
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
    """Prompt resolution or expansion failed.

    ``exit_code`` is set for non-zero ``!command`` shell-block expansions.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        exit_code: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.exit_code = exit_code
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

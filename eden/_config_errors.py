"""Configuration error classes."""

from __future__ import annotations

from eden._error_base import EdenError, _format


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
    ``timeout`` is set for timed-out shell-block expansions.
    ``elapsed_ms`` is set when a shell-block command was attempted.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        exit_code: int | None = None,
        timeout: float | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.exit_code = exit_code
        self.timeout = timeout
        self.elapsed_ms = elapsed_ms
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


__all__ = [
    "ConfigError",
    "CwdError",
    "EnvMergeError",
    "FloxEnvError",
    "InvalidOptions",
    "PromptError",
]

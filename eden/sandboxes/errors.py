"""Sandbox-provider exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from eden._error_base import EdenError, _format
from eden._redact import redact_secrets

if TYPE_CHECKING:
    from eden.providers._types import ExecResult


class SandboxError(EdenError):
    """Base for sandbox-provider errors."""

    def __init__(
        self,
        *,
        code: str = "sandbox.error",
        message: str,
        hint: str | None = None,
        retryable: bool = False,
        cause: Exception | None = None,
    ) -> None:
        self.code = code
        self.message = redact_secrets(message)
        self.hint = hint
        self.retryable = retryable
        self.cause = cause
        super().__init__(_format(code, self.message, hint))


class ProviderUnavailable(SandboxError):
    def __init__(self, *, provider: str, binary: str) -> None:
        self.provider = provider
        self.binary = binary
        super().__init__(
            code="sandbox.provider_unavailable",
            message=f"provider {provider!r} requires binary {binary!r} on PATH",
            retryable=False,
        )


class ImageNotFound(SandboxError):
    def __init__(self, *, image: str, stderr: str) -> None:
        self.image = image
        self.stderr = redact_secrets(stderr)
        super().__init__(
            code="sandbox.image_not_found",
            message=f"docker image {image!r} not found locally\n{self.stderr}",
            retryable=False,
        )


class ContainerStartFailed(SandboxError):
    def __init__(self, *, image: str, exit_code: int, stderr: str) -> None:
        self.image = image
        self.exit_code = exit_code
        self.stderr = redact_secrets(stderr)
        super().__init__(
            code="sandbox.container_start_failed",
            message=f"docker run for image {image!r} failed (exit {exit_code})\n{self.stderr}",
            retryable=False,
        )


class ExecFailed(SandboxError):
    def __init__(self, *, result: ExecResult, argv_or_cmd: str) -> None:
        self.result = result
        self.argv_or_cmd = argv_or_cmd
        stderr = redact_secrets(result.stderr)
        super().__init__(
            code="sandbox.exec_failed",
            message=f"command {argv_or_cmd!r} failed (exit {result.exit_code})\n{stderr}",
            retryable=False,
        )


class ExecTimeout(SandboxError):
    def __init__(
        self,
        *,
        cmd: str,
        timeout: float,
        partial_stdout: str,
        partial_stderr: str,
    ) -> None:
        self.cmd = cmd
        self.timeout = timeout
        self.partial_stdout = partial_stdout
        self.partial_stderr = redact_secrets(partial_stderr)
        super().__init__(
            code="sandbox.exec_timeout",
            message=f"command {cmd!r} timed out after {timeout}s",
            retryable=True,
        )


class ContainerStartTimeout(SandboxError):
    """The docker/podman container-creation sequence exceeded its deadline."""

    def __init__(self, *, binary: str, timeout: float) -> None:
        self.binary = binary
        self.timeout = timeout
        super().__init__(
            code="sandbox.container_start_timeout",
            message=f"{binary} container start timed out after {timeout}s",
            retryable=True,
        )


class ImageUidMismatch(SandboxError):
    """Container image's USER UID does not match the configured ``container_uid``."""

    def __init__(self, *, image: str, image_uid: int, expected_uid: int) -> None:
        self.image = image
        self.image_uid = image_uid
        self.expected_uid = expected_uid
        super().__init__(
            code="sandbox.image_uid_mismatch",
            message=(
                f"image {image!r} was built with UID {image_uid}, "
                f"but the configured UID is {expected_uid}. "
                f"Rebuild the image with --build-arg AGENT_UID={expected_uid} "
                f"AGENT_GID=<gid>, or pass container_uid={image_uid} to match the image."
            ),
            retryable=False,
        )


from eden.sandboxes._config_errors import (  # noqa: E402
    MountConfigError,
    MountHostMissing,
    PortNotDeclared,
    ProcessKillFailed,
    ProcessNotFound,
    UnsupportedStrategy,
)

__all__ = [
    "ContainerStartFailed",
    "ContainerStartTimeout",
    "ExecFailed",
    "ExecTimeout",
    "ImageNotFound",
    "ImageUidMismatch",
    "MountConfigError",
    "MountHostMissing",
    "PortNotDeclared",
    "ProcessKillFailed",
    "ProcessNotFound",
    "ProviderUnavailable",
    "SandboxError",
    "UnsupportedStrategy",
]

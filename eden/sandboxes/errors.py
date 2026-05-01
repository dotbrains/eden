"""Sandbox-provider exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from eden.errors import EdenError

if TYPE_CHECKING:
    from eden.providers._types import ExecResult, StrategyTag


class SandboxError(EdenError):
    """Base for sandbox-provider errors."""


class ProviderUnavailable(SandboxError):
    def __init__(self, *, provider: str, binary: str) -> None:
        self.provider = provider
        self.binary = binary
        super().__init__(f"provider {provider!r} requires binary {binary!r} on PATH")


class ImageNotFound(SandboxError):
    def __init__(self, *, image: str, stderr: str) -> None:
        self.image = image
        self.stderr = stderr
        super().__init__(f"docker image {image!r} not found locally\n{stderr}")


class ContainerStartFailed(SandboxError):
    def __init__(self, *, image: str, exit_code: int, stderr: str) -> None:
        self.image = image
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"docker run for image {image!r} failed (exit {exit_code})\n{stderr}")


class ExecFailed(SandboxError):
    def __init__(self, *, result: ExecResult, argv_or_cmd: str) -> None:
        self.result = result
        self.argv_or_cmd = argv_or_cmd
        super().__init__(
            f"command {argv_or_cmd!r} failed (exit {result.exit_code})\n{result.stderr}"
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
        self.partial_stderr = partial_stderr
        super().__init__(f"command {cmd!r} timed out after {timeout}s")


class UnsupportedStrategy(SandboxError):
    def __init__(self, *, provider: str, strategy: StrategyTag) -> None:
        self.provider = provider
        self.strategy = strategy
        super().__init__(f"provider {provider!r} does not support strategy {strategy!r}")

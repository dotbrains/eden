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


class ImageUidMismatch(SandboxError):
    """Container image's USER UID does not match the configured ``container_uid``.

    Raised by the docker / podman pre-flight inspection so users find out
    *before* a container starts and writes files with the wrong owner.
    """

    def __init__(self, *, image: str, image_uid: int, expected_uid: int) -> None:
        self.image = image
        self.image_uid = image_uid
        self.expected_uid = expected_uid
        super().__init__(
            f"image {image!r} was built with UID {image_uid}, "
            f"but the configured UID is {expected_uid}. "
            f"Rebuild the image with --build-arg AGENT_UID={expected_uid} "
            f"AGENT_GID=<gid>, or pass container_uid={image_uid} to match the image."
        )


class MountConfigError(SandboxError):
    """Invalid bind-mount configuration detected before container startup."""

    def __init__(self, *, sandbox_path: object, parent: object, sandbox_homedir: object) -> None:
        self.sandbox_path = sandbox_path
        self.parent = parent
        self.sandbox_homedir = sandbox_homedir
        super().__init__(
            f"cannot mount file to {sandbox_path!r}: parent directory {parent!r} "
            f"is outside the sandbox home directory ({sandbox_homedir!r}). "
            "Mount the parent directory instead, or rebuild the image with that "
            "parent directory pre-created."
        )


class MountHostMissing(SandboxError):
    """Bind-mount host path does not exist."""

    def __init__(self, *, host_path: object) -> None:
        self.host_path = host_path
        super().__init__(
            f"cannot bind-mount missing host path {host_path!r}; "
            "create it first or remove the mount"
        )


class UnsupportedStrategy(SandboxError):
    def __init__(self, *, provider: str, strategy: StrategyTag) -> None:
        self.provider = provider
        self.strategy = strategy
        super().__init__(f"provider {provider!r} does not support strategy {strategy!r}")

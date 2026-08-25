"""Sandbox configuration, mount, port, and process errors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from eden._redact import redact_secrets
from eden.sandboxes.errors import SandboxError

if TYPE_CHECKING:
    from eden.providers._types import StrategyTag


class MountConfigError(SandboxError):
    """Invalid bind-mount configuration detected before container startup."""

    def __init__(self, *, sandbox_path: object, parent: object, sandbox_homedir: object) -> None:
        self.sandbox_path = sandbox_path
        self.parent = parent
        self.sandbox_homedir = sandbox_homedir
        super().__init__(
            code="sandbox.mount_config",
            message=(
                f"cannot mount file to {sandbox_path!r}: parent directory {parent!r} "
                f"is outside the sandbox home directory ({sandbox_homedir!r}). "
                "Mount the parent directory instead, or rebuild the image with that "
                "parent directory pre-created."
            ),
            retryable=False,
        )


class MountHostMissing(SandboxError):
    """Bind-mount host path does not exist."""

    def __init__(self, *, host_path: object) -> None:
        self.host_path = host_path
        super().__init__(
            code="sandbox.mount_host_missing",
            message=(
                f"cannot bind-mount missing host path {host_path!r}; "
                "create it first or remove the mount"
            ),
            retryable=False,
        )


class UnsupportedStrategy(SandboxError):
    def __init__(self, *, provider: str, strategy: StrategyTag) -> None:
        self.provider = provider
        self.strategy = strategy
        super().__init__(
            code="sandbox.unsupported_strategy",
            message=f"provider {provider!r} does not support strategy {strategy!r}",
            retryable=False,
        )


class PortNotDeclared(SandboxError):
    """A port was exposed at runtime but was not declared at container create time."""

    def __init__(self, *, port: int, container_id: str) -> None:
        self.port = port
        self.container_id = container_id
        super().__init__(
            code="sandbox.port_not_declared",
            message=(
                f"port {port} was not declared at container create time "
                f"(container {container_id!r}); pass ports= to the provider factory"
            ),
            retryable=False,
        )


class ProcessNotFound(SandboxError):
    """Background process id not found on the provider."""

    def __init__(self, *, process_id: str, provider: str) -> None:
        self.process_id = process_id
        self.provider = provider
        super().__init__(
            code="sandbox.process_not_found",
            message=f"process {process_id!r} not found on provider {provider!r}",
            retryable=False,
        )


class ProcessKillFailed(SandboxError):
    """Provider failed to kill a background process."""

    def __init__(self, *, process_id: str, provider: str, detail: str) -> None:
        self.process_id = process_id
        self.provider = provider
        self.detail = redact_secrets(detail)
        super().__init__(
            code="sandbox.process_kill_failed",
            message=f"failed to kill process {process_id!r} on {provider!r}: {self.detail}",
            retryable=False,
        )


__all__ = [
    "MountConfigError",
    "MountHostMissing",
    "PortNotDeclared",
    "ProcessKillFailed",
    "ProcessNotFound",
    "UnsupportedStrategy",
]

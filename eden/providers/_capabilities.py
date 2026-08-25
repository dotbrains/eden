"""Declarative capability map for built-in sandbox providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from eden.providers._protocols import SandboxProvider

PortSupport = Literal["dynamic", "static", "unsupported"]


@dataclass(frozen=True)
class ProviderCapabilities:
    ports: PortSupport
    background_exec: bool


_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "no_sandbox": ProviderCapabilities(ports="dynamic", background_exec=True),
    "docker": ProviderCapabilities(ports="static", background_exec=True),
    "podman": ProviderCapabilities(ports="static", background_exec=True),
    "isolated": ProviderCapabilities(ports="dynamic", background_exec=True),
    "daytona": ProviderCapabilities(ports="dynamic", background_exec=True),
    "vercel": ProviderCapabilities(ports="static", background_exec=True),
  # forkd guest agent exposes no public port-forward or background-exec SDK surface.
    "forkd": ProviderCapabilities(ports="unsupported", background_exec=False),
}

_DEFAULT = ProviderCapabilities(ports="unsupported", background_exec=False)


def capabilities_for(provider: SandboxProvider) -> ProviderCapabilities:
    """Return declared capabilities for a provider, or fully unsupported defaults."""
    return _CAPABILITIES.get(provider.name, _DEFAULT)


__all__ = ["PortSupport", "ProviderCapabilities", "capabilities_for"]

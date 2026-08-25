"""Tests for provider capability declarations."""

from __future__ import annotations

import pytest

from eden.providers._capabilities import capabilities_for
from eden.sandboxes import docker, forkd, no_sandbox, vercel

pytestmark = pytest.mark.unit


def test_no_sandbox_dynamic_ports_and_background() -> None:
    caps = capabilities_for(no_sandbox.provider())
    assert caps.ports == "dynamic"
    assert caps.background_exec is True


def test_docker_static_ports_and_background() -> None:
    caps = capabilities_for(docker.provider())
    assert caps.ports == "static"
    assert caps.background_exec is True


def test_forkd_unsupported_capabilities() -> None:
    caps = capabilities_for(forkd.provider())
    assert caps.ports == "unsupported"
    assert caps.background_exec is False


def test_vercel_static_ports() -> None:
    caps = capabilities_for(vercel.provider(access_token="t"))
    assert caps.ports == "static"
    assert caps.background_exec is True


def test_unknown_provider_defaults_unsupported() -> None:
    from eden.providers._helpers import make_bind_mount_provider
    from eden.providers._protocols import BindMountSandboxHandle
    from eden.providers._types import CreateOptions

    def _create(opts: CreateOptions) -> BindMountSandboxHandle:
        raise RuntimeError("unused")

    custom = make_bind_mount_provider(name="custom-foo", create=_create)
    caps = capabilities_for(custom)
    assert caps.ports == "unsupported"
    assert caps.background_exec is False

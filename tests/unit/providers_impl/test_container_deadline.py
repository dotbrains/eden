"""Verify the shared deadline for the docker/podman container-start sequence."""

from __future__ import annotations

import subprocess

import pytest

from eden.providers._impl.container_deadline import container_start_deadline
from eden.sandboxes.errors import ContainerStartTimeout

pytestmark = pytest.mark.unit


def test_remaining_shrinks_within_budget() -> None:
    with container_start_deadline(binary="docker", timeout=10.0) as remaining:
        first = remaining()
        second = remaining()
        assert 0 < second <= first <= 10.0


def test_exhausted_budget_raises_container_start_timeout() -> None:
    with container_start_deadline(binary="docker", timeout=0.0) as remaining:
        with pytest.raises(ContainerStartTimeout) as excinfo:
            remaining()
    assert excinfo.value.binary == "docker"
    assert excinfo.value.timeout == 0.0


def test_subprocess_timeout_expired_becomes_container_start_timeout() -> None:
    with pytest.raises(ContainerStartTimeout) as excinfo:
        with container_start_deadline(binary="podman", timeout=5.0):
            raise subprocess.TimeoutExpired(cmd=["podman", "run"], timeout=5.0)
    assert excinfo.value.binary == "podman"
    assert excinfo.value.timeout == 5.0


def test_other_exceptions_propagate_unchanged() -> None:
    with pytest.raises(ValueError):
        with container_start_deadline(binary="docker", timeout=5.0):
            raise ValueError("unrelated failure")

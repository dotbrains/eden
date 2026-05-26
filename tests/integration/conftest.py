"""Session-scoped fixtures for docker integration tests."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_DOCKER_ONLY_PREFIXES: tuple[str, ...] = ("test_docker", "test_podman")


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Skip docker/podman integration tests on non-Linux runners.

    REST-based cloud-provider tests (daytona, vercel) work everywhere, so
    they are NOT skipped here — they gate themselves on the relevant
    credentials env var inside the test module.
    """
    if sys.platform == "linux":
        return None
    if collection_path.is_file() and collection_path.name.startswith(_DOCKER_ONLY_PREFIXES):
        return True
    return None


_DOCKERFILE = Path(__file__).resolve().parent / "Dockerfile"


def _hash_dockerfile() -> str:
    return hashlib.sha256(_DOCKERFILE.read_bytes()).hexdigest()[:12]


@pytest.fixture(scope="session")
def eden_test_image() -> Iterator[str]:
    if not shutil.which("docker"):
        pytest.skip("docker binary not available")

    info = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if info.returncode != 0:
        pytest.skip("docker daemon not reachable")

    tag = f"eden-test:{_hash_dockerfile()}"
    inspect = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
        text=True,
    )
    if inspect.returncode != 0:
        build = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                tag,
                "-f",
                str(_DOCKERFILE),
                str(_DOCKERFILE.parent),
            ],
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            pytest.fail(
                f"failed to build {tag}: {build.stderr}",
                pytrace=False,
            )
    yield tag

"""Verify `eden docker build-image` / `eden podman build-image` subcommands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _seed_dockerfile(repo: Path) -> None:
    (repo / ".eden").mkdir(parents=True, exist_ok=True)
    (repo / ".eden" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")


def test_docker_build_image_missing_dockerfile(runner: CliRunner, tmp_path: Path) -> None:
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/docker"),
    ):
        result = runner.invoke(app, ["docker", "build-image"])
    assert result.exit_code == 1
    assert "no .eden/Dockerfile" in (result.output or "") + (result.stderr or "")


def test_docker_build_image_invokes_docker(
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    _seed_dockerfile(tmp_path)
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/docker"),
        patch("eden.cli._image.subprocess.run", return_value=completed) as run_mock,
    ):
        result = runner.invoke(app, ["docker", "build-image", "--image-name", "my:tag"])
    assert result.exit_code == 0, result.output
    argv = run_mock.call_args[0][0]
    assert argv[0] == "/usr/bin/docker"
    assert argv[1] == "build"
    assert "-t" in argv and argv[argv.index("-t") + 1] == "my:tag"
    assert "-f" in argv
    dockerfile_arg = argv[argv.index("-f") + 1]
    assert dockerfile_arg.endswith(str(Path(".eden") / "Dockerfile"))


def test_docker_build_image_accepts_custom_dockerfile(
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "Dockerfile.custom"
    custom.write_text("FROM scratch\n", encoding="utf-8")
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/docker"),
        patch("eden.cli._image.subprocess.run", return_value=completed) as run_mock,
    ):
        result = runner.invoke(
            app,
            ["docker", "build-image", "--dockerfile", str(custom)],
        )
    assert result.exit_code == 0, result.output
    argv = run_mock.call_args[0][0]
    assert argv[0] == "/usr/bin/docker"
    assert argv[1] == "build"
    assert "-f" in argv
    assert argv[argv.index("-f") + 1] == str(custom)
    assert argv[-1] == str(tmp_path)


def test_docker_remove_image_invokes_docker(runner: CliRunner, tmp_path: Path) -> None:
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/docker"),
        patch("eden.cli._image.subprocess.run", return_value=completed) as run_mock,
    ):
        result = runner.invoke(app, ["docker", "remove-image", "--image-name", "foo:bar"])
    assert result.exit_code == 0, result.output
    argv = run_mock.call_args[0][0]
    assert argv == ["/usr/bin/docker", "image", "rm", "foo:bar"]


def test_podman_build_image_invokes_podman(runner: CliRunner, tmp_path: Path) -> None:
    repo = tmp_path / "My Repo!"
    (repo / ".eden").mkdir(parents=True)
    (repo / ".eden" / "Containerfile").write_text("FROM scratch\n", encoding="utf-8")
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    with (
        patch("eden.cli._image.Path.cwd", return_value=repo),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/podman"),
        patch("eden.cli._image.subprocess.run", return_value=completed) as run_mock,
    ):
        result = runner.invoke(app, ["podman", "build-image"])
    assert result.exit_code == 0, result.output
    argv = run_mock.call_args[0][0]
    assert argv[0] == "/usr/bin/podman"
    assert "-t" in argv
    assert "-f" in argv
    build_file = argv[argv.index("-f") + 1]
    assert build_file.endswith(str(Path(".eden") / "Containerfile"))
    tag = argv[argv.index("-t") + 1]
    assert tag == "eden:my-repo"


def test_podman_build_image_accepts_custom_containerfile(
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "Containerfile.custom"
    custom.write_text("FROM scratch\n", encoding="utf-8")
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/podman"),
        patch("eden.cli._image.subprocess.run", return_value=completed) as run_mock,
    ):
        result = runner.invoke(
            app,
            ["podman", "build-image", "--containerfile", str(custom)],
        )
    assert result.exit_code == 0, result.output
    argv = run_mock.call_args[0][0]
    assert argv[0] == "/usr/bin/podman"
    assert argv[1] == "build"
    assert "-f" in argv
    assert argv[argv.index("-f") + 1] == str(custom)
    assert argv[-1] == str(tmp_path)


def test_docker_build_image_binary_missing(runner: CliRunner, tmp_path: Path) -> None:
    _seed_dockerfile(tmp_path)
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["docker", "build-image"])
    assert result.exit_code == 1
    assert "docker not found" in (result.output or "") + (result.stderr or "")


def test_docker_build_image_propagates_nonzero(runner: CliRunner, tmp_path: Path) -> None:
    _seed_dockerfile(tmp_path)
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=42
    )
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/docker"),
        patch("eden.cli._image.subprocess.run", return_value=completed),
    ):
        result = runner.invoke(app, ["docker", "build-image"])
    assert result.exit_code == 42

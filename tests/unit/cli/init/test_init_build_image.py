"""Verify `eden init --build-image`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.cli.cli_init_fixtures"]


def test_init_does_not_build_image_by_default(runner: CliRunner, repo_dir: Path) -> None:
    with patch("eden.cli.init._build_image") as build_mock:
        result = runner.invoke(app, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    assert (repo_dir / ".eden" / "Dockerfile").is_file()
    build_mock.assert_not_called()


def test_init_build_image_uses_selected_runtime_and_image_name(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    with patch("eden.cli.init._build_image") as build_mock:
        result = runner.invoke(
            app,
            [
                "init",
                "--yes",
                "--sandbox",
                "podman",
                "--image-name",
                "eden:agent",
                "--build-image",
            ],
        )
    assert result.exit_code == 0, result.output
    assert (repo_dir / ".eden" / "Containerfile").is_file()
    build_mock.assert_called_once_with(binary="podman", image_name="eden:agent")

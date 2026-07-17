"""Verify Podman-specific image command defaults."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


def test_podman_build_image_missing_containerfile(tmp_path: Path) -> None:
    with (
        patch("eden.cli._image.Path.cwd", return_value=tmp_path),
        patch("eden.cli._image.shutil.which", return_value="/usr/bin/podman"),
    ):
        result = CliRunner().invoke(app, ["podman", "build-image"])
    assert result.exit_code == 1
    assert "no .eden/Containerfile" in (result.output or "") + (result.stderr or "")

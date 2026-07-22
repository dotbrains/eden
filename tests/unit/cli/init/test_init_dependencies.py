"""Verify `eden init` dependency helper behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from eden.cli import _init_dependencies as deps

pytestmark = pytest.mark.unit


def test_init_detects_package_manager_from_package_json(repo_dir: Path) -> None:
    (repo_dir / "package.json").write_text(
        '{"packageManager": "pnpm@9.0.0"}',
        encoding="utf-8",
    )
    assert deps.detect_package_manager(repo_dir) == "pnpm"


def test_init_detects_package_manager_from_lockfile(repo_dir: Path) -> None:
    (repo_dir / "yarn.lock").write_text("", encoding="utf-8")
    assert deps.detect_package_manager(repo_dir) == "yarn"


def test_init_dependency_command_matches_package_manager() -> None:
    assert deps.add_dependency_command("bun", "zod") == "bun add zod"
    assert deps.add_dependency_command("pnpm", "zod") == "pnpm add zod"
    assert deps.add_dependency_command("yarn", "zod") == "yarn add zod"
    assert deps.add_dependency_command("npm", "zod") == "npm install zod"


def test_init_detects_existing_host_dependency(repo_dir: Path) -> None:
    (repo_dir / "package.json").write_text(
        '{"devDependencies": {"zod": "^4.0.0"}}',
        encoding="utf-8",
    )
    assert deps.has_host_dependency(repo_dir, "zod") is True
    assert deps.has_host_dependency(repo_dir, "tsx") is False


def test_missing_template_dependencies_filters_existing_packages(repo_dir: Path) -> None:
    (repo_dir / "package.json").write_text(
        '{"dependencies": {"zod": "^4.0.0"}}',
        encoding="utf-8",
    )
    assert deps.missing_template_dependencies(repo_dir, ("zod", "tsx")) == ("tsx",)


def test_install_dependency_runs_detected_command() -> None:
    with patch("eden.cli._init_dependencies.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0

        assert deps.install_dependency("pnpm", "zod") == 0

    run_mock.assert_called_once_with(["pnpm", "add", "zod"], check=False)

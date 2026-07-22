"""Dependency detection helpers for ``eden init`` next-step output."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def detect_package_manager(repo: Path) -> str:
    """Return npm/pnpm/yarn/bun using package.json or lockfiles."""
    package_json = repo / "package.json"
    if package_json.exists():
        try:
            raw = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        package_manager = raw.get("packageManager")
        if isinstance(package_manager, str):
            manager = package_manager.split("@", 1)[0]
            if manager in {"npm", "pnpm", "yarn", "bun"}:
                return manager
    lockfiles = (
        ("bun.lockb", "bun"),
        ("bun.lock", "bun"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
    )
    for filename, manager in lockfiles:
        if (repo / filename).exists():
            return manager
    return "npm"


def add_dependency_command(package_manager: str, dependency: str) -> str:
    if package_manager == "pnpm":
        return f"pnpm add {dependency}"
    if package_manager == "yarn":
        return f"yarn add {dependency}"
    if package_manager == "bun":
        return f"bun add {dependency}"
    return f"npm install {dependency}"


def has_host_dependency(repo: Path, dependency: str) -> bool:
    package_json = repo / "package.json"
    if not package_json.exists():
        return False
    try:
        raw = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = raw.get(key)
        if isinstance(deps, dict) and dependency in deps:
            return True
    return False


def missing_template_dependencies(repo: Path, dependencies: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dependency for dependency in dependencies if not has_host_dependency(repo, dependency)
    )


def install_dependency(package_manager: str, dependency: str) -> int:
    command = add_dependency_command(package_manager, dependency).split()
    proc = subprocess.run(command, check=False)
    return proc.returncode

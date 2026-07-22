"""Filesystem writes and post-create output for `eden init`."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from eden.cli._init_dependencies import (
    add_dependency_command as _add_dependency_command,
)
from eden.cli._init_dependencies import (
    detect_package_manager as _detect_package_manager,
)
from eden.cli._init_dependencies import (
    has_host_dependency as _has_host_dependency,
)
from eden.cli._init_dependencies import (
    install_dependency as _install_dependency,
)
from eden.cli._init_dependencies import (
    missing_template_dependencies as _missing_template_dependencies,
)
from eden.cli._init_templates import TEMPLATE_METADATA as _TEMPLATE_METADATA

console = Console(stderr=True)


def scaffold_init_files(
    *,
    target: Path,
    repo: Path,
    files: dict[str, str],
    template: str,
    sandbox: str,
    image_name: str,
    install_template_deps: bool = False,
) -> None:
    files = _build_file_names_for_sandbox(files, sandbox=sandbox)
    outputs: list[tuple[Path, str]] = []
    for name, contents in files.items():
        out = (target / name).resolve()
        if not out.is_relative_to(repo):
            console.print(f"[red]refusing to write outside repo: {out}[/red]")
            raise typer.Exit(code=1)
        if out.exists():
            console.print(f"[red]refusing to overwrite existing {out}[/red]")
            raise typer.Exit(code=1)
        outputs.append((out, contents))

    target.mkdir(parents=True)
    for out, contents in outputs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(contents, encoding="utf-8")

    typer.secho(f"✓ scaffolded {target}", fg="green")
    _install_template_dependencies(
        repo=repo,
        template=template,
        install_template_deps=install_template_deps,
    )
    _print_next_steps(repo=repo, template=template, sandbox=sandbox, image_name=image_name)


def _build_file_names_for_sandbox(files: dict[str, str], *, sandbox: str) -> dict[str, str]:
    if sandbox != "podman" or "Dockerfile" not in files:
        return files
    renamed = dict(files)
    renamed["Containerfile"] = renamed.pop("Dockerfile")
    return renamed


def _print_next_steps(*, repo: Path, template: str, sandbox: str, image_name: str) -> None:
    meta = _TEMPLATE_METADATA[template]
    typer.echo(f"Template: {meta.name} - {meta.description}")
    typer.echo("Next steps:")
    typer.echo("  1. cp .eden/.env.example .eden/.env  # then fill in your API keys")
    step = 2
    dependencies = tuple(dep for dep in meta.dependencies if not _has_host_dependency(repo, dep))
    if dependencies:
        package_manager = _detect_package_manager(repo)
        for dependency in dependencies:
            typer.echo(f"  {step}. {_add_dependency_command(package_manager, dependency)}")
            step += 1
    build_file = "Containerfile" if sandbox == "podman" else "Dockerfile"
    typer.echo(
        f"  {step}. {sandbox} build "
        f"--build-arg AGENT_UID=$(id -u) --build-arg AGENT_GID=$(id -g) "
        f"-t {image_name} -f .eden/{build_file} ."
    )
    step += 1
    typer.echo(f"  {step}. python .eden/main.py")


def _install_template_dependencies(
    *,
    repo: Path,
    template: str,
    install_template_deps: bool,
) -> None:
    if not install_template_deps:
        return
    dependencies = _missing_template_dependencies(repo, _TEMPLATE_METADATA[template].dependencies)
    if not dependencies:
        return
    package_manager = _detect_package_manager(repo)
    for dependency in dependencies:
        command = _add_dependency_command(package_manager, dependency)
        typer.echo(f"Installing template dependency: {command}")
        exit_code = _install_dependency(package_manager, dependency)
        if exit_code != 0:
            console.print(f"[red]template dependency install failed: {command}[/red]")
            raise typer.Exit(code=exit_code)

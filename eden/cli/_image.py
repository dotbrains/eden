"""Shared image-lifecycle commands for the ``eden docker`` / ``eden podman``
Typer sub-apps.

Both subcommands default to the Dockerfile that ``eden init`` scaffolds at
``.eden/Dockerfile``; ``--image-name`` overrides the default
``eden:<repo-dir-name>`` tag.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

_console = Console(stderr=True)


def _default_image_name() -> str:
    return f"eden:{Path.cwd().name.lower()}"


def _resolve_binary(binary: str) -> str:
    resolved = shutil.which(binary)
    if resolved is None:
        _console.print(f"[red]{binary} not found on PATH[/red]")
        raise typer.Exit(code=1)
    return resolved


def _dockerfile_path() -> Path:
    path = Path.cwd() / ".eden" / "Dockerfile"
    if not path.is_file():
        _console.print(f"[red]no .eden/Dockerfile at {path}[/red] — run `eden init` first.")
        raise typer.Exit(code=1)
    return path


def _custom_build_file(path: Path, *, flag: str) -> Path:
    resolved = path.expanduser()
    if not resolved.is_file():
        _console.print(f"[red]{flag} path is not a file: {resolved}[/red]")
        raise typer.Exit(code=1)
    return resolved


def _build_uid_gid() -> tuple[int, int]:
    # Windows lacks os.getuid/getgid; the scaffolded Dockerfile defaults its
    # ARG AGENT_UID/AGENT_GID anyway, so a sentinel matching the scaffold
    # default is fine for Windows build invocations.
    if sys.platform == "win32":
        return 1000, 1000
    return os.getuid(), os.getgid()


def build_image(*, binary: str, image_name: str | None, build_file: Path | None = None) -> None:
    bin_path = _resolve_binary(binary)
    build_file_flag = "--dockerfile" if binary == "docker" else "--containerfile"
    dockerfile = (
        _custom_build_file(build_file, flag=build_file_flag)
        if build_file is not None
        else _dockerfile_path()
    )
    tag = image_name or _default_image_name()
    uid, gid = _build_uid_gid()
    # Inherit caller UID/GID into the build args so the scaffolded
    # ``ARG AGENT_UID`` / ``ARG AGENT_GID`` lines pick them up — same default
    # eden's ``eden init`` next-steps tells the user to use.
    argv = [
        bin_path,
        "build",
        "--build-arg",
        f"AGENT_UID={uid}",
        "--build-arg",
        f"AGENT_GID={gid}",
        "-t",
        tag,
        "-f",
        str(dockerfile),
        str(Path.cwd()),
    ]
    _console.print(f"[cyan]→ {' '.join(argv)}[/cyan]")
    proc = subprocess.run(argv, check=False)
    if proc.returncode != 0:
        raise typer.Exit(code=proc.returncode)
    _console.print(f"[green]built {tag}[/green]")


def remove_image(*, binary: str, image_name: str | None) -> None:
    bin_path = _resolve_binary(binary)
    tag = image_name or _default_image_name()
    argv = [bin_path, "image", "rm", tag]
    _console.print(f"[cyan]→ {' '.join(argv)}[/cyan]")
    proc = subprocess.run(argv, check=False)
    if proc.returncode != 0:
        raise typer.Exit(code=proc.returncode)
    _console.print(f"[green]removed {tag}[/green]")


def make_image_app(*, binary: str) -> typer.Typer:
    """Build a Typer sub-app exposing ``build-image`` and ``remove-image``."""
    app = typer.Typer(
        name=binary,
        help=f"Manage the {binary} image used by eden's sandbox.",
        no_args_is_help=True,
        add_completion=False,
    )

    @app.command(
        name="build-image",
        help=f"Build the {binary} image from .eden/Dockerfile.",
    )
    def _build(
        image_name: str | None = typer.Option(
            None,
            "--image-name",
            help="Image tag to build (default: eden:<repo-dir-name>)",
        ),
        build_file: Path | None = typer.Option(  # noqa: B008
            None,
            "--dockerfile" if binary == "docker" else "--containerfile",
            help=(
                "Custom Dockerfile to build with the current directory as context."
                if binary == "docker"
                else "Custom Containerfile to build with the current directory as context."
            ),
        ),
    ) -> None:
        build_image(binary=binary, image_name=image_name, build_file=build_file)

    @app.command(
        name="remove-image",
        help=f"Remove the {binary} image previously built by eden.",
    )
    def _remove(
        image_name: str | None = typer.Option(
            None,
            "--image-name",
            help="Image tag to remove (default: eden:<repo-dir-name>)",
        ),
    ) -> None:
        remove_image(binary=binary, image_name=image_name)

    return app


__all__ = ["build_image", "make_image_app", "remove_image"]

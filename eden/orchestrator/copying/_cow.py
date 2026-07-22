"""Copy paths with copy-on-write acceleration when available."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def copy_path(src: Path, dst: Path) -> None:
    if _try_copy_on_write(src, dst):
        return
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def _try_copy_on_write(src: Path, dst: Path) -> bool:
    if src.is_dir() and dst.exists():
        return False
    flags = ["-cR"] if sys.platform == "darwin" else ["-R", "--reflink=auto"]
    try:
        subprocess.run(
            ["cp", *flags, str(src), str(dst)],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


__all__ = ["copy_path"]

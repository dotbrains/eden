"""Low-level container mount path helper behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._impl.container_mounts import _expand_sandbox_tilde, _file_mount_parents
from eden.providers._types import Mount
from eden.sandboxes.errors import MountConfigError

pytestmark = pytest.mark.unit


def test_expand_sandbox_tilde_root() -> None:
    expanded = _expand_sandbox_tilde(Path("~"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/home/agent")


def test_expand_sandbox_tilde_with_subpath() -> None:
    expanded = _expand_sandbox_tilde(Path("~/.config/x"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/home/agent/.config/x")


def test_expand_sandbox_tilde_passthrough_for_absolute() -> None:
    expanded = _expand_sandbox_tilde(Path("/etc/hosts"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/etc/hosts")


def test_expand_sandbox_tilde_resolves_relative_under_workspace() -> None:
    expanded = _expand_sandbox_tilde(Path("cache/npm"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/workspace/cache/npm")


def test_expand_sandbox_tilde_raises_when_homedir_missing() -> None:
    with pytest.raises(ValueError, match="sandbox_homedir"):
        _expand_sandbox_tilde(Path("~/x"), sandbox_homedir=None)


def test_file_mount_parents_includes_files_under_homedir(tmp_path: Path) -> None:
    """File mounts under SANDBOX_HOMEDIR contribute their parent dirs."""
    f = tmp_path / "config"
    f.write_text("x")
    mounts = [
        Mount(host=f, sandbox=Path("/home/agent/.config/gh/hosts.yml")),
    ]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == [Path("/home/agent/.config/gh")]


def test_file_mount_parents_skips_directory_mounts(tmp_path: Path) -> None:
    """Directory mounts don't need parent prep; docker handles them."""
    d = tmp_path / "dir"
    d.mkdir()
    mounts = [Mount(host=d, sandbox=Path("/home/agent/.npm"))]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == []


def test_file_mount_parents_skips_paths_outside_homedir(tmp_path: Path) -> None:
    """File mounts outside the agent home fail with a clear config error."""
    f = tmp_path / "secret"
    f.write_text("x")
    mounts = [Mount(host=f, sandbox=Path("/etc/foo/bar.conf"))]
    with pytest.raises(MountConfigError) as ex:
        _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert "/etc/foo" in str(ex.value)


def test_file_mount_parents_dedupes(tmp_path: Path) -> None:
    """Two file mounts in the same parent only create that parent once."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_text("a")
    b.write_text("b")
    mounts = [
        Mount(host=a, sandbox=Path("/home/agent/.config/x.yml")),
        Mount(host=b, sandbox=Path("/home/agent/.config/y.yml")),
    ]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == [Path("/home/agent/.config")]


def test_file_mount_parents_skips_homedir_itself(tmp_path: Path) -> None:
    """A file mount directly into ``~`` doesn't need parent prep; it IS the homedir."""
    f = tmp_path / "a"
    f.write_text("a")
    # Sandbox path /home/agent/foo -> parent is /home/agent (the homedir itself).
    mounts = [Mount(host=f, sandbox=Path("/home/agent/.bashrc"))]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == []

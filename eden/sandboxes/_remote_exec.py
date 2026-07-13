"""Shared file sync helpers for exec-only sandbox providers."""

from __future__ import annotations

import base64
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from eden.providers._impl import patch_sync
from eden.providers._impl.dir_upload import upload_dir_via_tar
from eden.providers._types import ExecResult, FinalizeResult
from eden.sandboxes._remote_rest_exec import snapshot_via_rest_exec, upload_tree_via_rest_exec
from eden.sandboxes._remote_snapshot import (
    parse_sha256sum_snapshot,
    path_arg,
    snapshot_command,
)
from eden.sandboxes.errors import ExecFailed


class ExecFn(Protocol):
    def __call__(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult: ...


def copy_file_in_via_exec(
    exec_fn: ExecFn,
    *,
    host: Path,
    sandbox: Path,
    quote_paths: bool = False,
) -> None:
    if host.is_dir():
        result = upload_dir_via_tar(exec_fn, host=host, sandbox=sandbox)
        if result.exit_code != 0:
            raise ExecFailed(
                result=result,
                argv_or_cmd=f"copy_file_in (dir) {host} -> {sandbox}",
            )
        return

    b64 = base64.b64encode(host.read_bytes()).decode("ascii")
    result = exec_fn(
        f"mkdir -p {path_arg(sandbox.parent, quote_paths=quote_paths)} && "
        f"echo {b64} | base64 -d > {path_arg(sandbox, quote_paths=quote_paths)}",
    )
    if result.exit_code != 0:
        raise ExecFailed(
            result=result,
            argv_or_cmd=f"copy_file_in {host} -> {sandbox}",
        )


def copy_file_out_via_exec(
    exec_fn: ExecFn,
    *,
    sandbox: Path,
    host: Path,
    quote_paths: bool = False,
) -> None:
    result = exec_fn(f"base64 {path_arg(sandbox, quote_paths=quote_paths)}")
    if result.exit_code != 0:
        raise ExecFailed(
            result=result,
            argv_or_cmd=f"copy_file_out {sandbox} -> {host}",
        )
    host.parent.mkdir(parents=True, exist_ok=True)
    host.write_bytes(base64.b64decode(result.stdout))


def snapshot_via_exec(
    exec_fn: ExecFn,
    *,
    root: Path,
    quote_root: bool = False,
) -> dict[Path, str]:
    result = exec_fn(snapshot_command(root, quote_root=quote_root))
    return parse_sha256sum_snapshot(result.stdout)


def upload_tree_via_exec(
    exec_fn: ExecFn,
    *,
    src: Path,
    dst: Path,
    quote_paths: bool = False,
) -> None:
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if any(part in (".git", ".eden") for part in rel.parts):
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        target = dst / rel
        result = exec_fn(
            f"mkdir -p {path_arg(target.parent, quote_paths=quote_paths)} && "
            f"echo {b64} | base64 -d > {path_arg(target, quote_paths=quote_paths)}",
        )
        if result.exit_code != 0:
            raise RuntimeError(f"upload of {rel} failed: {result.stderr}")


def finalize_from_remote_snapshot(
    *,
    snapshot: Callable[[], dict[Path, str]],
    copy_file_out: Callable[[Path, Path], None],
    baseline: dict[Path, str],
    worktree_path: Path,
    target: Path,
) -> FinalizeResult:
    try:
        after = snapshot()
    except Exception:
        return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)

    diff_result = patch_sync.diff(before=baseline, after=after)
    if not (diff_result.added or diff_result.changed or diff_result.removed):
        return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = Path(tmp_root_str)
        for rel in sorted(diff_result.added | diff_result.changed):
            copy_file_out(worktree_path / rel, tmp_root / rel)
        return patch_sync.apply(diff_result, src=tmp_root, dst=target)


__all__ = [
    "ExecFn",
    "copy_file_in_via_exec",
    "copy_file_out_via_exec",
    "finalize_from_remote_snapshot",
    "parse_sha256sum_snapshot",
    "snapshot_command",
    "snapshot_via_exec",
    "snapshot_via_rest_exec",
    "upload_tree_via_exec",
    "upload_tree_via_rest_exec",
]

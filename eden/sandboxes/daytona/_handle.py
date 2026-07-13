"""Daytona sandbox handle implementation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.errors import RestNotFoundError
from eden.providers._impl.http_rest import RestClient
from eden.providers._types import ExecResult, FinalizeResult
from eden.sandboxes._remote_exec import (
    copy_file_in_via_exec,
    copy_file_out_via_exec,
    finalize_from_remote_snapshot,
    snapshot_via_rest_exec,
)
from eden.sandboxes.daytona._exec_payload import build_exec_payload


@dataclass
class DaytonaHandle:
    client: RestClient
    sandbox_id: str
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        payload = build_exec_payload(
            cmd,
            cwd=cwd,
            env=env,
            timeout=timeout,
            stdin=stdin,
        )
        try:
            resp = self.client.post(
                f"/toolbox/{self.sandbox_id}/process/execute",
                json=payload,
            )
        except Exception as exc:
            return ExecResult(
                stdout="",
                stderr=str(exc),
                exit_code=-1,
            )
        stdout = str(resp.get("stdout", ""))
        stderr = str(resp.get("stderr", ""))
        exit_code = int(resp.get("exit_code", resp.get("exitCode", 0)))
        if on_line is not None:
            for line in stdout.splitlines():
                on_line(line)
        return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        copy_file_in_via_exec(self.exec, host=host, sandbox=sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        copy_file_out_via_exec(self.exec, sandbox=sandbox, host=host)

    def finalize(self, target: Path) -> FinalizeResult:
        endpoint = f"/toolbox/{self.sandbox_id}/process/execute"
        return finalize_from_remote_snapshot(
            snapshot=lambda: snapshot_via_rest_exec(
                self.client,
                endpoint,
                root=self.worktree_path,
            ),
            copy_file_out=self.copy_file_out,
            baseline=self.baseline,
            worktree_path=self.worktree_path,
            target=target,
        )

    def close(self) -> None:
        try:
            self.client.delete(f"/api/sandbox/{self.sandbox_id}")
        except RestNotFoundError:
            pass
        except Exception:
            pass
        finally:
            self.client.close()


__all__ = ["DaytonaHandle"]

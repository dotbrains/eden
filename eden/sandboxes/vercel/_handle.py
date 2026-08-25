"""Vercel sandbox handle implementation."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.errors import RestNotFoundError
from eden.providers._impl.http_rest import RestClient
from eden.providers._types import ExecResult, ExposedPort, FinalizeResult
from eden.sandboxes._remote_exec import (
    copy_file_in_via_exec,
    copy_file_out_via_exec,
    finalize_from_remote_snapshot,
    snapshot_via_rest_exec,
)
from eden.sandboxes.errors import PortNotDeclared
from eden.sandboxes.vercel._process import start_vercel_process


@dataclass
class VercelHandle:
    client: RestClient
    session_id: str
    name: str
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]
    team_id: str | None
    routes: dict[int, str] = field(default_factory=dict)

    def _params(self) -> dict[str, str] | None:
        return {"teamId": self.team_id} if self.team_id else None

    def _cmd_endpoint(self) -> str:
        return f"/v2/sandboxes/sessions/{self.session_id}/cmd"

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
        if stdin is not None:
            b64 = base64.b64encode(stdin.encode("utf-8")).decode("ascii")
            cmd = f"printf '%s' {b64} | base64 -d | ({cmd})"
        payload: dict[str, object] = {"command": cmd, "wait": True}
        if cwd is not None:
            payload["cwd"] = cwd.as_posix()
        if env:
            payload["env"] = dict(env)
        if timeout is not None:
            payload["timeout"] = timeout
        try:
            resp = self.client.post(
                self._cmd_endpoint(),
                json=payload,
                params=self._params(),
            )
        except Exception as exc:
            return ExecResult(stdout="", stderr=str(exc), exit_code=-1)
        stdout = str(resp.get("stdout", ""))
        stderr = str(resp.get("stderr", ""))
        exit_code = int(resp.get("exit_code", resp.get("exitCode", 0)))
        if on_line is not None:
            for line in stdout.splitlines():
                on_line(line)
        return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

    def start(
        self,
        cmd: str,
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> object:
        return start_vercel_process(
            self.client,
            session_id=self.session_id,
            cmd=cmd,
            cwd=cwd,
            env=env,
            team_id=self.team_id,
            timeout=None,
        )

    def expose_port(self, port: int, *, public: bool = False) -> ExposedPort:
        url = self.routes.get(port)
        if url is None:
            raise PortNotDeclared(port=port, container_id=self.name)
        return ExposedPort(port=port, url=url, public=public)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        copy_file_in_via_exec(self.exec, host=host, sandbox=sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        copy_file_out_via_exec(self.exec, sandbox=sandbox, host=host)

    def finalize(self, target: Path) -> FinalizeResult:
        return finalize_from_remote_snapshot(
            snapshot=lambda: snapshot_via_rest_exec(
                self.client,
                self._cmd_endpoint(),
                root=self.worktree_path,
                params=self._params(),
            ),
            copy_file_out=self.copy_file_out,
            baseline=self.baseline,
            worktree_path=self.worktree_path,
            target=target,
        )

    def close(self) -> None:
        try:
            self.client.delete(
                f"/v2/sandboxes/{self.name}",
                params=self._params(),
            )
        except RestNotFoundError:
            pass
        except Exception:
            pass
        finally:
            self.client.close()


__all__ = ["VercelHandle"]

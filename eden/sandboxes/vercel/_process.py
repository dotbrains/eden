"""Vercel background process handle."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import ExecResult, ProcessStatus
from eden.sandboxes.errors import ProcessKillFailed, ProcessNotFound


@dataclass
class VercelProcess:
    client: RestClient
    session_id: str
    cmd_id: str
    team_id: str | None
    cmd: str
    _killed: bool = False
    _lines: list[str] = field(default_factory=list)

    def _params(self) -> dict[str, str] | None:
        return {"teamId": self.team_id} if self.team_id else None

    def _cmd_path(self, suffix: str = "") -> str:
        base = f"/v2/sandboxes/sessions/{self.session_id}/cmd/{self.cmd_id}"
        return base + suffix

    def status(self) -> ProcessStatus:
        try:
            resp = self.client.get(self._cmd_path(), params=self._params())
        except Exception:
            return ProcessStatus(state="failed", exit_code=-1)
        exit_code = resp.get("exitCode", resp.get("exit_code"))
        running = resp.get("running", resp.get("status") == "running")
        if running:
            return ProcessStatus(state="running", exit_code=None)
        if self._killed:
            return ProcessStatus(state="killed", exit_code=int(exit_code or 0))
        code = int(exit_code or 0)
        if code == 0:
            return ProcessStatus(state="exited", exit_code=0)
        return ProcessStatus(state="failed", exit_code=code)

    def output(self) -> Iterator[str]:
        try:
            resp = self.client.get(self._cmd_path("/logs"), params=self._params())
        except Exception:
            return
        logs = resp.get("logs", resp.get("output", ""))
        if isinstance(logs, list):
            for entry in logs:
                line = str(entry.get("text", entry.get("message", entry)))
                self._lines.append(line)
                yield line
            return
        text = str(logs)
        for line in text.splitlines():
            self._lines.append(line)
            yield line

    def write(self, data: str) -> None:
        self.client.post(
            self._cmd_path("/input"),
            json={"input": data},
            params=self._params(),
        )

    def wait(self, *, timeout: float | None = None) -> ExecResult:
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        while True:
            st = self.status()
            if st.state != "running":
                break
            if deadline is not None and time.monotonic() > deadline:
                from eden.sandboxes.errors import ExecTimeout

                raise ExecTimeout(
                    cmd=self.cmd,
                    timeout=timeout or 0.0,
                    partial_stdout="\n".join(self._lines),
                    partial_stderr="",
                )
            time.sleep(0.1)
        try:
            resp = self.client.get(self._cmd_path(), params=self._params())
        except Exception as exc:
            return ExecResult(stdout="", stderr=str(exc), exit_code=-1)
        stdout = str(resp.get("stdout", ""))
        stderr = str(resp.get("stderr", ""))
        exit_code = int(resp.get("exitCode", resp.get("exit_code", st.exit_code or 0)))
        return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

    def kill(self) -> None:
        try:
            self.client.post(self._cmd_path("/kill"), json={}, params=self._params())
        except Exception as exc:
            raise ProcessKillFailed(
                process_id=self.cmd_id,
                provider="vercel",
                detail=str(exc),
            ) from exc
        self._killed = True


def start_vercel_process(
    client: RestClient,
    *,
    session_id: str,
    cmd: str,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    team_id: str | None,
    timeout: float | None,
) -> VercelProcess:
    payload: dict[str, Any] = {"command": cmd, "wait": False}
    if cwd is not None:
        payload["cwd"] = cwd.as_posix()
    if env:
        payload["env"] = dict(env)
    if timeout is not None:
        payload["timeout"] = timeout
    params = {"teamId": team_id} if team_id else None
    try:
        resp = client.post(
            f"/v2/sandboxes/sessions/{session_id}/cmd",
            json=payload,
            params=params,
        )
    except Exception as exc:
        raise ProcessNotFound(process_id="<pending>", provider="vercel") from exc
    cmd_id = str(resp.get("cmdId") or resp.get("id") or resp.get("commandId") or "")
    if not cmd_id:
        raise ProcessNotFound(process_id=json.dumps(resp), provider="vercel")
    return VercelProcess(
        client=client,
        session_id=session_id,
        cmd_id=cmd_id,
        team_id=team_id,
        cmd=cmd,
    )


__all__ = ["VercelProcess", "start_vercel_process"]

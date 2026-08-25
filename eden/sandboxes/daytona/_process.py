"""Daytona background process handle."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import ExecResult, ProcessStatus
from eden.sandboxes.daytona._exec_payload import build_exec_payload
from eden.sandboxes.errors import ProcessKillFailed


@dataclass
class DaytonaProcess:
    """Session-scoped Daytona process. ``kill()`` deletes the whole session."""

    client: RestClient
    sandbox_id: str
    session_id: str
    command_id: str
    cmd: str
    _killed: bool = False
    _lines: list[str] = field(default_factory=list)

    def _session_base(self) -> str:
        return f"/toolbox/{self.sandbox_id}/process/session/{self.session_id}"

    def status(self) -> ProcessStatus:
        try:
            resp = self.client.get(f"{self._session_base()}/command/{self.command_id}")
        except Exception:
            return ProcessStatus(state="failed", exit_code=-1)
        exit_code = resp.get("exit_code", resp.get("exitCode"))
        running = resp.get("running", resp.get("status") in ("running", "RUNNING"))
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
            resp = self.client.get(
                f"{self._session_base()}/command/{self.command_id}/logs",
                params={"follow": "false"},
            )
        except Exception:
            return
        logs = resp.get("logs", resp.get("output", ""))
        if isinstance(logs, list):
            for entry in logs:
                line = str(entry.get("text", entry.get("message", entry)))
                self._lines.append(line)
                yield line
            return
        for line in str(logs).splitlines():
            self._lines.append(line)
            yield line

    def write(self, data: str) -> None:
        self.client.post(
            f"{self._session_base()}/command/{self.command_id}/input",
            json={"input": data},
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
            resp = self.client.get(f"{self._session_base()}/command/{self.command_id}")
        except Exception as exc:
            return ExecResult(stdout="", stderr=str(exc), exit_code=-1)
        stdout = str(resp.get("stdout", ""))
        stderr = str(resp.get("stderr", ""))
        exit_code = int(resp.get("exit_code", resp.get("exitCode", st.exit_code or 0)))
        return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

    def kill(self) -> None:
        try:
            self.client.delete(self._session_base())
        except Exception as exc:
            raise ProcessKillFailed(
                process_id=self.session_id,
                provider="daytona",
                detail=str(exc),
            ) from exc
        self._killed = True


def start_daytona_process(
    client: RestClient,
    *,
    sandbox_id: str,
    cmd: str,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    timeout: float | None,
    stdin: str | None = None,
) -> DaytonaProcess:
    session_resp = client.post(f"/toolbox/{sandbox_id}/process/session", json={})
    session_id = str(session_resp.get("sessionId") or session_resp.get("id") or "")
    payload = build_exec_payload(cmd, cwd=cwd, env=env, timeout=timeout, stdin=stdin)
    payload["runAsync"] = True
    exec_resp = client.post(
        f"/toolbox/{sandbox_id}/process/session/{session_id}/exec",
        json=payload,
    )
    command_id = str(
        exec_resp.get("commandId") or exec_resp.get("id") or exec_resp.get("cmdId") or ""
    )
    return DaytonaProcess(
        client=client,
        sandbox_id=sandbox_id,
        session_id=session_id,
        command_id=command_id,
        cmd=cmd,
    )


__all__ = ["DaytonaProcess", "start_daytona_process"]

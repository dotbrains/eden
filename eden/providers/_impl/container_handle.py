"""Container runtime handle shared by docker and podman providers."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.abort import AbortSignal
from eden.providers._process_local import start_local_process
from eden.providers._types import ExecResult, ExposedPort
from eden.sandboxes._exec import stream_exec
from eden.sandboxes.errors import PortNotDeclared
from eden.streaming._bounded_tail import DEFAULT_MAX_CHARS


def _wait_interactive_process(proc: subprocess.Popen[bytes], signal: AbortSignal | None) -> int:
    while True:
        if signal is not None and signal.is_aborted():
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            signal.raise_if_aborted()
        try:
            return proc.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            time.sleep(0)


@dataclass
class ContainerHandle:
    binary: str
    container_id: str
    worktree_path: Path
    host_worktree_path: Path
    max_output_tail_chars: int = DEFAULT_MAX_CHARS
    declared_ports: tuple[int, ...] = field(default_factory=tuple)

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
        argv: list[str] = [self.binary, "exec", "-i"]
        if cwd is not None:
            argv.extend(["-w", cwd.as_posix()])
        if env:
            for k, v in env.items():
                argv.extend(["-e", f"{k}={v}"])
        argv.extend([self.container_id, "/bin/sh", "-c", cmd])
        return stream_exec(
            argv,
            cmd_for_error=cmd,
            shell=False,
            on_line=on_line,
            timeout=timeout,
            stdin=stdin,
            max_output_tail_chars=self.max_output_tail_chars,
        )

    def start(
        self,
        cmd: str,
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> object:
        argv: list[str] = [self.binary, "exec", "-i"]
        if cwd is not None:
            argv.extend(["-w", cwd.as_posix()])
        if env:
            for k, v in env.items():
                argv.extend(["-e", f"{k}={v}"])
        argv.extend([self.container_id, "/bin/sh", "-c", cmd])
        return start_local_process(argv, cmd_for_error=cmd, shell=False)

    def expose_port(self, port: int, *, public: bool = False) -> ExposedPort:
        if port not in self.declared_ports:
            raise PortNotDeclared(port=port, container_id=self.container_id)
        proc = subprocess.run(
            [self.binary, "port", self.container_id, str(port)],
            capture_output=True,
            text=True,
            check=True,
        )
        line = proc.stdout.strip().splitlines()[0]
        host_part, _, mapped = line.rpartition(":")
        host = host_part or "127.0.0.1"
        url = f"http://{host}:{mapped}"
        return ExposedPort(port=port, url=url, public=public)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        subprocess.run(
            [self.binary, "cp", str(host), f"{self.container_id}:{sandbox.as_posix()}"],
            check=True,
            capture_output=True,
            text=True,
        )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        subprocess.run(
            [self.binary, "cp", f"{self.container_id}:{sandbox.as_posix()}", str(host)],
            check=True,
            capture_output=True,
            text=True,
        )

    def interactive_exec(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        signal: AbortSignal | None = None,
    ) -> int:
        """Run ``argv`` inside the container with a TTY attached."""
        if signal is not None:
            signal.raise_if_aborted()
        cmd: list[str] = [self.binary, "exec", "-it"]
        if cwd is not None:
            cmd.extend(["-w", cwd.as_posix()])
        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])
        cmd.append(self.container_id)
        cmd.extend(argv)
        proc = subprocess.Popen(cmd)
        return _wait_interactive_process(proc, signal)

    def close(self) -> None:
        proc = subprocess.run(
            [self.binary, "kill", self.container_id],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return None
        if "no such container" in (proc.stderr or "").lower():
            return None
        return None


_ContainerHandle = ContainerHandle

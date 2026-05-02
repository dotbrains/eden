"""Fake Daytona REST server for e2e tests.

Spins a ThreadingHTTPServer on localhost:<random-port> registering the three
endpoints _DaytonaHandle uses. Sandbox state lives in a tmp directory; commands
run via subprocess.run against that dir, so the e2e test exercises the real
snapshot/diff/apply flow without an actual Daytona account.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


def start_fake_daytona(
    *,
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
) -> str:
    """Start a fake-daytona ThreadingHTTPServer on a random port.

    Routes:
      POST /api/sandbox                   → create state_dir/<id>/, return {"id": <id>}
      POST /toolbox/<id>/process/execute  → subprocess.run(cmd, cwd=state_dir/<id>)
      DELETE /api/sandbox/<id>            → shutil.rmtree(state_dir/<id>)

    Sets DAYTONA_API_KEY=test-token and DAYTONA_API_URL=<base_url> via
    monkeypatch.setenv. Returns the base_url string.

    Server runs on a daemon thread; pytest fixture finalizer should call
    server.shutdown() to clean up.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    sandboxes: dict[str, Path] = {}

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return  # silence

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            try:
                return json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return {}

        def _send_json(self, status: int, body: dict[str, object]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:
            payload = self._read_json()
            if self.path == "/api/sandbox":
                sb_id = uuid.uuid4().hex[:12]
                sb_root = state_dir / sb_id
                sb_root.mkdir(parents=True, exist_ok=True)
                # Create the workspace dir up-front; commands run in there.
                (sb_root / "workspace").mkdir(parents=True, exist_ok=True)
                sandboxes[sb_id] = sb_root
                self._send_json(200, {"id": sb_id})
                return
            if self.path.startswith("/toolbox/") and self.path.endswith("/process/execute"):
                sb_id = self.path.split("/")[2]
                exec_root = sandboxes.get(sb_id)
                if exec_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                cmd = str(payload.get("command", ""))
                # Sandbox-side cwd is /workspace. Map to host: state_dir/<id>/workspace.
                # The command may reference "/workspace/..." paths (from
                # _DaytonaHandle.copy_file_in/out and _snapshot_remote). We
                # rewrite "/workspace" → "<exec_root>/workspace" in the command
                # string and chdir into <exec_root>.
                try:
                    rewritten = cmd.replace("/workspace", str(exec_root / "workspace"))
                    # macOS ships BSD base64, which requires `-i <file>` rather
                    # than a bare positional argument.  _DaytonaHandle.copy_file_out
                    # sends `base64 <path>` (Linux/GNU convention); rewrite it to
                    # the portable `cat <path> | base64` form so the fake server
                    # works on both macOS and Linux.
                    if sys.platform == "darwin":
                        rewritten = re.sub(
                            r"\bbase64 (/[^\s|;&)]+)",
                            r"cat \1 | base64",
                            rewritten,
                        )
                    proc = subprocess.run(
                        ["/bin/sh", "-c", rewritten],
                        cwd=str(exec_root),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self._send_json(
                        200,
                        {
                            "stdout": proc.stdout,
                            "stderr": proc.stderr,
                            "exit_code": proc.returncode,
                        },
                    )
                except subprocess.TimeoutExpired:
                    self._send_json(
                        200,
                        {
                            "stdout": "",
                            "stderr": "timeout",
                            "exit_code": 124,
                        },
                    )
                return
            self._send_json(404, {"error": f"no such route: {self.path}"})

        def do_DELETE(self) -> None:
            if self.path.startswith("/api/sandbox/"):
                sb_id = self.path.rsplit("/", 1)[-1]
                sb_root = sandboxes.pop(sb_id, None)
                if sb_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                shutil.rmtree(sb_root, ignore_errors=True)
                self.send_response(204)
                self.end_headers()
                return
            self._send_json(404, {"error": f"no such route: {self.path}"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("DAYTONA_API_KEY", "test-token")
    monkeypatch.setenv("DAYTONA_API_URL", base_url)

    # Register a finalizer to shut down the server when the test ends.
    def _stop() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    # pytest's monkeypatch doesn't have a teardown-callback API; the server is
    # daemon-threaded, so it dies with the test process. For deterministic
    # cleanup across tests, callers should treat this as a function-scoped
    # fixture and call `_stop()` themselves if they want immediate cleanup.
    server._eden_stop = _stop
    return base_url


__all__ = ["start_fake_daytona"]

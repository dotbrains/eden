"""Fake Vercel REST server for e2e tests.

Spins a ThreadingHTTPServer on localhost:<random-port> registering the three
endpoints _VercelHandle uses. Sandbox state lives in a tmp directory; commands
run via subprocess.run against that dir, so the e2e test exercises the real
snapshot/diff/apply flow without an actual Vercel account.
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


def start_fake_vercel(
    *,
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
) -> str:
    """Start a fake-vercel ThreadingHTTPServer on a random port.

    Routes:
      POST   /v1/sandboxes              → create state_dir/<id>/, return {"id": <id>}
      POST   /v1/sandboxes/<id>/exec    → subprocess.run(cmd, cwd=state_dir/<id>)
      DELETE /v1/sandboxes/<id>         → shutil.rmtree(state_dir/<id>)

    Sets VERCEL_TOKEN=test-token and VERCEL_API_URL=<base_url> via
    monkeypatch.setenv. Returns the base_url string.
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

        def _path_without_query(self) -> str:
            return self.path.split("?", 1)[0]

        def do_POST(self) -> None:
            payload = self._read_json()
            path = self._path_without_query()
            if path == "/v1/sandboxes":
                sb_id = uuid.uuid4().hex[:12]
                sb_root = state_dir / sb_id
                sb_root.mkdir(parents=True, exist_ok=True)
                (sb_root / "workspace").mkdir(parents=True, exist_ok=True)
                sandboxes[sb_id] = sb_root
                self._send_json(200, {"id": sb_id})
                return
            # /v1/sandboxes/<id>/exec
            m = re.match(r"^/v1/sandboxes/([^/]+)/exec$", path)
            if m:
                sb_id = m.group(1)
                exec_root = sandboxes.get(sb_id)
                if exec_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                cmd = str(payload.get("command", ""))
                try:
                    rewritten = cmd.replace("/workspace", str(exec_root / "workspace"))
                    # macOS BSD `base64` doesn't accept positional file argument.
                    # Rewrite `base64 <abs-path>` → `cat <abs-path> | base64`.
                    if sys.platform == "darwin":
                        rewritten = re.sub(
                            r"\bbase64 (/[^\s|>;&]+)",
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
            self._send_json(404, {"error": f"no such route: {path}"})

        def do_DELETE(self) -> None:
            path = self._path_without_query()
            m = re.match(r"^/v1/sandboxes/([^/]+)$", path)
            if m:
                sb_id = m.group(1)
                sb_root = sandboxes.pop(sb_id, None)
                if sb_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                shutil.rmtree(sb_root, ignore_errors=True)
                self.send_response(204)
                self.end_headers()
                return
            self._send_json(404, {"error": f"no such route: {path}"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("VERCEL_TOKEN", "test-token")
    monkeypatch.setenv("VERCEL_API_URL", base_url)

    def _stop() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    server._eden_stop = _stop  # type: ignore[attr-defined]
    return base_url


__all__ = ["start_fake_vercel"]

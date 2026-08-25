"""Fake Vercel REST server for e2e tests."""

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
    """Start a fake-vercel ThreadingHTTPServer on a random port."""
    state_dir.mkdir(parents=True, exist_ok=True)
    sandboxes: dict[str, Path] = {}
    sessions: dict[str, str] = {}

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

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

        def do_GET(self) -> None:
            path = self._path_without_query()
            m = re.match(r"^/v2/sandboxes/sessions/([^/]+)/cmd/([^/]+)$", path)
            if m:
                self._send_json(
                    200,
                    {
                        "stdout": "",
                        "stderr": "",
                        "exitCode": 0,
                        "running": False,
                    },
                )
                return
            self._send_json(404, {"error": f"no such route: {path}"})

        def do_POST(self) -> None:
            payload = self._read_json()
            path = self._path_without_query()
            if path == "/v4/sandboxes":
                name = str(payload.get("name") or uuid.uuid4().hex[:12])
                session_id = uuid.uuid4().hex[:12]
                sb_root = state_dir / name
                sb_root.mkdir(parents=True, exist_ok=True)
                (sb_root / "workspace").mkdir(parents=True, exist_ok=True)
                sandboxes[name] = sb_root
                sessions[session_id] = name
                ports_raw = payload.get("ports")
                ports_list = ports_raw if isinstance(ports_raw, list) else []
                routes = [
                    {"port": port, "url": f"http://127.0.0.1:{30000 + int(port)}"}
                    for port in ports_list
                    if isinstance(port, int)
                ]
                self._send_json(
                    200,
                    {
                        "sandbox": {"name": name},
                        "session": {"id": session_id},
                        "routes": routes,
                    },
                )
                return
            m = re.match(r"^/v2/sandboxes/sessions/([^/]+)/cmd$", path)
            if m:
                cmd_session_id = m.group(1) or ""
                sandbox_name = sessions.get(cmd_session_id)
                exec_root = sandboxes.get(sandbox_name or "") if sandbox_name else None
                if exec_root is None:
                    self._send_json(404, {"error": "no such session"})
                    return
                if payload.get("wait") is False:
                    self._send_json(200, {"cmdId": uuid.uuid4().hex[:12]})
                    return
                cmd = str(payload.get("command", ""))
                try:
                    rewritten = cmd.replace("/workspace", str(exec_root / "workspace"))
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
                            "exitCode": proc.returncode,
                        },
                    )
                except subprocess.TimeoutExpired:
                    self._send_json(
                        200,
                        {"stdout": "", "stderr": "timeout", "exitCode": 124},
                    )
                return
            self._send_json(404, {"error": f"no such route: {path}"})

        def do_DELETE(self) -> None:
            path = self._path_without_query()
            m = re.match(r"^/v2/sandboxes/([^/]+)$", path)
            if m:
                name = m.group(1)
                sb_root = sandboxes.pop(name, None)
                if sb_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                for sid, sname in list(sessions.items()):
                    if sname == name:
                        sessions.pop(sid, None)
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

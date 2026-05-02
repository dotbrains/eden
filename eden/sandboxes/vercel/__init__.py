"""Vercel cloud sandbox provider: REST-driven isolated/finalizing sandbox.

Phase 4c: factory + create flow + handle methods (exec, copy_file_in/out, close)
+ stub finalize. Phase 4c Task 2 fills in the real finalize.

Endpoints (empirically derived from Vercel Sandbox SDK conventions):
  POST   /v1/sandboxes              — create sandbox; payload {runtime, env, name?}
  POST   /v1/sandboxes/{id}/exec    — run command; payload {command, cwd?, env?, timeout?}
  DELETE /v1/sandboxes/{id}         — destroy sandbox

When `team_id` is set, every request carries `?teamId=<id>` as a query parameter.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.errors import RestNotFoundError
from eden.providers._helpers import make_isolated_provider
from eden.providers._impl.http_rest import RestClient
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable

_DEFAULT_BASE_URL = "https://api.vercel.com"
_DEFAULT_RUNTIME = "node24"
_SANDBOX_WORKDIR = Path("/workspace")


def provider(
    *,
    runtime: str = _DEFAULT_RUNTIME,
    access_token: str | None = None,
    team_id: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> SandboxProvider:
    """Vercel Sandbox cloud isolated/finalizing sandbox provider.

    `access_token` falls back to VERCEL_TOKEN env var; `team_id` to
    VERCEL_TEAM_ID; `base_url` to VERCEL_API_URL (default
    https://api.vercel.com). Raises ProviderUnavailable at create() time
    (NOT at factory time) when no access_token is found.
    """
    fixed_runtime = runtime
    fixed_env: dict[str, str] = dict(env) if env else {}
    fixed_timeout = timeout

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        resolved_token = access_token or os.environ.get("VERCEL_TOKEN")
        if not resolved_token:
            raise ProviderUnavailable(
                provider="vercel",
                binary="VERCEL_TOKEN",
            )
        resolved_team = team_id or os.environ.get("VERCEL_TEAM_ID")
        resolved_base = base_url or os.environ.get("VERCEL_API_URL") or _DEFAULT_BASE_URL

        headers: dict[str, str] = {"Authorization": f"Bearer {resolved_token}"}
        params = {"teamId": resolved_team} if resolved_team else None

        client = RestClient(
            base_url=resolved_base,
            headers=headers,
            timeout=fixed_timeout,
        )

        merged_env: dict[str, str] = {**fixed_env, **dict(opts.env)}
        try:
            payload: dict[str, object] = {
                "runtime": fixed_runtime,
                "env": merged_env,
            }
            if opts.name_hint:
                payload["name"] = opts.name_hint[:63]
            response = client.post("/v1/sandboxes", json=payload, params=params)
        except Exception:
            client.close()
            raise

        sandbox_id = str(response.get("id") or response.get("sandbox_id") or "")
        if not sandbox_id:
            client.close()
            raise ProviderUnavailable(
                provider="vercel",
                binary=f"sandbox-id missing in response: {response}",
            )

        try:
            _upload_tree(
                client,
                sandbox_id,
                src=opts.worktree_path,
                dst=_SANDBOX_WORKDIR,
                team_id=resolved_team,
            )
            baseline = _snapshot_remote(
                client,
                sandbox_id,
                root=_SANDBOX_WORKDIR,
                team_id=resolved_team,
            )
        except Exception:
            try:
                client.delete(f"/v1/sandboxes/{sandbox_id}", params=params)
            except Exception:
                pass
            client.close()
            raise

        return _VercelHandle(
            client=client,
            sandbox_id=sandbox_id,
            worktree_path=_SANDBOX_WORKDIR,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
            team_id=resolved_team,
        )

    return make_isolated_provider(name="vercel", create=_create)


@dataclass
class _VercelHandle:
    client: RestClient
    sandbox_id: str
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]
    team_id: str | None

    def _params(self) -> dict[str, str] | None:
        return {"teamId": self.team_id} if self.team_id else None

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        payload: dict[str, object] = {"command": cmd}
        if cwd is not None:
            payload["cwd"] = cwd.as_posix()
        if env:
            payload["env"] = dict(env)
        if timeout is not None:
            payload["timeout"] = timeout
        try:
            resp = self.client.post(
                f"/v1/sandboxes/{self.sandbox_id}/exec",
                json=payload,
                params=self._params(),
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
        data = host.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        result = self.exec(
            f"mkdir -p {sandbox.parent.as_posix()} && "
            f"echo {b64} | base64 -d > {sandbox.as_posix()}",
        )
        if result.exit_code != 0:
            raise ExecFailed(
                result=result,
                argv_or_cmd=f"copy_file_in {host} -> {sandbox}",
            )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        result = self.exec(f"base64 {sandbox.as_posix()}")
        if result.exit_code != 0:
            raise ExecFailed(
                result=result,
                argv_or_cmd=f"copy_file_out {sandbox} -> {host}",
            )
        host.parent.mkdir(parents=True, exist_ok=True)
        host.write_bytes(base64.b64decode(result.stdout))

    def finalize(self, target: Path) -> FinalizeResult:
        # Stub for Task 2.
        return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)

    def close(self) -> None:
        try:
            self.client.delete(
                f"/v1/sandboxes/{self.sandbox_id}",
                params=self._params(),
            )
        except RestNotFoundError:
            pass
        except Exception:
            pass
        finally:
            self.client.close()


def _upload_tree(
    client: RestClient,
    sandbox_id: str,
    *,
    src: Path,
    dst: Path,
    team_id: str | None,
) -> None:
    params = {"teamId": team_id} if team_id else None
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if any(part in (".git", ".eden") for part in rel.parts):
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        target = dst / rel
        cmd = f"mkdir -p {target.parent.as_posix()} && echo {b64} | base64 -d > {target.as_posix()}"
        result = client.post(
            f"/v1/sandboxes/{sandbox_id}/exec",
            json={"command": cmd},
            params=params,
        )
        if int(result.get("exit_code", result.get("exitCode", 0))) != 0:
            raise RuntimeError(f"upload of {rel} failed: {result.get('stderr', '')}")


def _snapshot_remote(
    client: RestClient,
    sandbox_id: str,
    *,
    root: Path,
    team_id: str | None,
) -> dict[Path, str]:
    cmd = (
        f"cd {root.as_posix()} && "
        "find . -type f "
        "-not -path './.git/*' -not -path './.eden/*' "
        "-print0 | xargs -0 sha256sum 2>/dev/null"
    )
    params = {"teamId": team_id} if team_id else None
    response = client.post(
        f"/v1/sandboxes/{sandbox_id}/exec",
        json={"command": cmd},
        params=params,
    )
    out: dict[Path, str] = {}
    for line in str(response.get("stdout", "")).splitlines():
        if not line.strip():
            continue
        try:
            hex_digest, rest = line.split(maxsplit=1)
        except ValueError:
            continue
        rel = rest.strip()
        if rel.startswith("./"):
            rel = rel[2:]
        out[Path(rel)] = hex_digest
    return out


__all__ = ["provider"]

"""Daytona cloud sandbox provider: REST-driven isolated/finalizing sandbox."""

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
from eden.sandboxes._remote_exec import (
    copy_file_in_via_exec,
    copy_file_out_via_exec,
    finalize_from_remote_snapshot,
    snapshot_via_rest_exec,
    upload_tree_via_rest_exec,
)
from eden.sandboxes.errors import ProviderUnavailable

_DEFAULT_BASE_URL = "https://api.daytona.io"
_DEFAULT_IMAGE = "ubuntu:24.04"
_SANDBOX_WORKDIR = Path("/workspace")


def provider(
    *,
    image: str = _DEFAULT_IMAGE,
    api_key: str | None = None,
    organization_id: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> SandboxProvider:
    """Daytona cloud isolated/finalizing sandbox provider.

    `api_key` falls back to DAYTONA_API_KEY env var; `organization_id` to
    DAYTONA_ORGANIZATION_ID; `base_url` to DAYTONA_API_URL (default
    https://api.daytona.io). Raises ProviderUnavailable at create() time
    (NOT at factory time) when no api_key is found.
    """
    fixed_image = image
    fixed_env: dict[str, str] = dict(env) if env else {}
    fixed_timeout = timeout

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        resolved_api_key = api_key or os.environ.get("DAYTONA_API_KEY")
        if not resolved_api_key:
            raise ProviderUnavailable(
                provider="daytona",
                binary="DAYTONA_API_KEY",
            )
        resolved_org = organization_id or os.environ.get("DAYTONA_ORGANIZATION_ID")
        resolved_base = base_url or os.environ.get("DAYTONA_API_URL") or _DEFAULT_BASE_URL

        headers: dict[str, str] = {"Authorization": f"Bearer {resolved_api_key}"}
        if resolved_org:
            headers["X-Daytona-Organization-ID"] = resolved_org

        client = RestClient(
            base_url=resolved_base,
            headers=headers,
            timeout=fixed_timeout,
        )

        merged_env: dict[str, str] = {**fixed_env, **dict(opts.env)}
        try:
            payload: dict[str, object] = {
                "image": fixed_image,
                "env": merged_env,
            }
            if opts.name_hint:
                payload["name"] = opts.name_hint[:63]
            response = client.post("/api/sandbox", json=payload)
        except Exception:
            client.close()
            raise

        sandbox_id = str(response.get("id") or response.get("sandbox_id") or "")
        if not sandbox_id:
            client.close()
            raise ProviderUnavailable(
                provider="daytona",
                binary=f"sandbox-id missing in response: {response}",
            )

        # Upload host worktree contents to /workspace, then snapshot baseline.
        try:
            endpoint = f"/toolbox/{sandbox_id}/process/execute"
            upload_tree_via_rest_exec(
                client,
                endpoint,
                src=opts.worktree_path,
                dst=_SANDBOX_WORKDIR,
            )
            baseline = snapshot_via_rest_exec(client, endpoint, root=_SANDBOX_WORKDIR)
        except Exception:
            try:
                client.delete(f"/api/sandbox/{sandbox_id}")
            except Exception:
                pass
            client.close()
            raise

        return _DaytonaHandle(
            client=client,
            sandbox_id=sandbox_id,
            worktree_path=_SANDBOX_WORKDIR,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
        )

    return make_isolated_provider(name="daytona", create=_create)


@dataclass
class _DaytonaHandle:
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
        # REST shell doesn't natively forward stdin. Encode the payload as
        # base64 and wrap the command so the remote shell decodes and pipes
        # it on our behalf. This survives JSON transport without escaping
        # issues and avoids any extra round-trip for a tempfile.
        if stdin is not None:
            b64 = base64.b64encode(stdin.encode("utf-8")).decode("ascii")
            cmd = f"printf '%s' {b64} | base64 -d | ({cmd})"
        payload: dict[str, object] = {"command": cmd}
        if cwd is not None:
            payload["cwd"] = cwd.as_posix()
        if env:
            payload["env"] = dict(env)
        if timeout is not None:
            payload["timeout"] = timeout
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
            pass  # already gone — idempotent close
        except Exception:
            pass  # don't propagate teardown errors (matches docker/podman)
        finally:
            self.client.close()


__all__ = ["provider"]

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

import os
from collections.abc import Mapping
from pathlib import Path

from eden.providers._helpers import make_isolated_provider
from eden.providers._impl.http_rest import RestClient
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes._remote_exec import (
    snapshot_via_rest_exec,
    upload_tree_via_rest_exec,
)
from eden.sandboxes.errors import ProviderUnavailable
from eden.sandboxes.vercel._handle import VercelHandle as _VercelHandle

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
            endpoint = f"/v1/sandboxes/{sandbox_id}/exec"
            upload_tree_via_rest_exec(
                client,
                endpoint,
                src=opts.worktree_path,
                dst=_SANDBOX_WORKDIR,
                params=params,
            )
            baseline = snapshot_via_rest_exec(
                client,
                endpoint,
                root=_SANDBOX_WORKDIR,
                params=params,
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


__all__ = ["_VercelHandle", "provider"]

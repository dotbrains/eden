"""Vercel cloud sandbox provider: REST-driven isolated/finalizing sandbox."""

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


def _parse_create_response(response: dict[str, object]) -> tuple[str, str, dict[int, str]]:
    sandbox = response.get("sandbox") or {}
    session = response.get("session") or {}
    routes_raw = response.get("routes") or []
    if not isinstance(sandbox, dict):
        sandbox = {}
    if not isinstance(session, dict):
        session = {}
    name = str(sandbox.get("name") or response.get("name") or "")
    session_id = str(session.get("id") or session.get("sessionId") or "")
    routes: dict[int, str] = {}
    if isinstance(routes_raw, list):
        for entry in routes_raw:
            if isinstance(entry, dict) and "port" in entry and "url" in entry:
                routes[int(entry["port"])] = str(entry["url"])
    return name, session_id, routes


def provider(
    *,
    runtime: str = _DEFAULT_RUNTIME,
    access_token: str | None = None,
    team_id: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    ports: tuple[int, ...] | None = None,
    timeout: float = 60.0,
) -> SandboxProvider:
    """Vercel Sandbox cloud isolated/finalizing sandbox provider."""
    fixed_runtime = runtime
    fixed_env: dict[str, str] = dict(env) if env else {}
    fixed_ports: tuple[int, ...] = ports or ()
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
            if fixed_ports:
                payload["ports"] = list(fixed_ports)
            if opts.name_hint:
                payload["name"] = opts.name_hint[:63]
            response = client.post("/v4/sandboxes", json=payload, params=params)
        except Exception:
            client.close()
            raise

        name, session_id, routes = _parse_create_response(response)
        if not session_id or not name:
            client.close()
            raise ProviderUnavailable(
                provider="vercel",
                binary=f"sandbox session/name missing in response: {response}",
            )

        cmd_endpoint = f"/v2/sandboxes/sessions/{session_id}/cmd"
        try:
            upload_tree_via_rest_exec(
                client,
                cmd_endpoint,
                src=opts.worktree_path,
                dst=_SANDBOX_WORKDIR,
                params=params,
            )
            baseline = snapshot_via_rest_exec(
                client,
                cmd_endpoint,
                root=_SANDBOX_WORKDIR,
                params=params,
            )
        except Exception:
            try:
                client.delete(f"/v2/sandboxes/{name}", params=params)
            except Exception:
                pass
            client.close()
            raise

        return _VercelHandle(
            client=client,
            session_id=session_id,
            name=name,
            worktree_path=_SANDBOX_WORKDIR,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
            team_id=resolved_team,
            routes=routes,
        )

    return make_isolated_provider(name="vercel", create=_create)


__all__ = ["_VercelHandle", "provider"]

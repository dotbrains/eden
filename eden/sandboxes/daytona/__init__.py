"""Daytona cloud sandbox provider: REST-driven isolated/finalizing sandbox."""

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
from eden.sandboxes.daytona._handle import DaytonaHandle as _DaytonaHandle
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
    public: bool = False,
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
    fixed_public = public
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
            if fixed_public:
                payload["public"] = True
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


__all__ = ["_DaytonaHandle", "provider"]

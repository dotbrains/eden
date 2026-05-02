# Eden Phase 4c — Vercel Cloud Sandbox Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the `vercel` cloud sandbox provider as an `IsolatedSandboxHandle` over Vercel Sandbox's REST API, mirroring the daytona provider's shape exactly. Reuse Phase 4b's `RestClient`, `RestError` family, `make_isolated_provider`, and `patch_sync`.

**Architecture:** New `vercel/` sub-package with a `provider()` factory and `_VercelHandle` (exec/copy_file_in/copy_file_out/finalize/close). REST endpoints mirror daytona's shape — `POST /v1/sandboxes` (create), `POST /v1/sandboxes/{id}/exec` (run), `DELETE /v1/sandboxes/{id}` (destroy). `team_id` threaded as `?teamId=<id>` query parameter when set. base64-via-shell file I/O. New fake-vercel `ThreadingHTTPServer` for e2e tests.

**Tech Stack:** Python 3.11+, `requests >= 2.32` (already optional dep from Phase 4b's `vercel = ["requests >= 2.32"]`), Phase 4a's `make_isolated_provider`/`patch_sync`/`IsolatedSandboxHandle`/`FinalizeResult`, Phase 4b's `RestClient`/`RestError` family. CI matrix unchanged.

**Reference spec:** `docs/superpowers/specs/2026-05-02-eden-phase4c-vercel-cloud-design.md`

**Phase 4b base:** This plan assumes commit `a501619` is on `main` (Phase 4b complete). Baseline: 385 unit+e2e tests passing, mypy strict clean across 133 source files, ruff clean, coverage 93.73%.

---

## File structure produced by this plan

```
eden/
└── sandboxes/
    └── vercel/                      # NEW directory
        └── __init__.py              # NEW — vercel() factory + _VercelHandle

tests/
├── _fake_vercel/                    # NEW (test infra; underscore prevents pytest collection)
│   └── __init__.py                  # NEW — start_fake_vercel() ThreadingHTTPServer
├── unit/
│   └── test_vercel_provider.py      # NEW — factory + handle method tests + finalize tests
└── e2e/
    └── test_vercel_smoke.py         # NEW — full pipeline via fake server (~2 tests)

README.md                            # MODIFY — bump status to phase 4c complete
```

`pyproject.toml` does NOT change in 4c — `vercel = ["requests >= 2.32"]` was added pre-emptively in 4b's T2.

`eden/__init__.py` does NOT change — no new top-level exports (RestError family already there from 4b).

**File responsibilities:**

- `eden/sandboxes/vercel/__init__.py` — `provider(*, runtime, access_token, team_id, base_url, env, timeout)` factory + `_VercelHandle` dataclass + `_upload_tree` + `_snapshot_remote` helpers. Mirrors daytona's shape with vercel-specific endpoint paths and the `team_id` query-param thread-through.
- `tests/_fake_vercel/__init__.py` — `start_fake_vercel(monkeypatch, state_dir)` mirroring `_fake_daytona`'s shape. Different routes (`/v1/sandboxes` vs `/api/sandbox`) but same path-rewriting and BSD-base64 quirk.

---

## Pre-flight: confirm Phase 4b baseline

- [ ] **Step 1: Confirm working tree clean and on main**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  git status -s && git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expected: empty status, branch `main`, commit `0a2cb5f docs: add phase 4c ...` (or later).

- [ ] **Step 2: Confirm Phase 4b suite passes**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3
```
Expected: `385 passed` (Phase 4b baseline).

No commit at this step — sanity check only.

---

## Task 1: Vercel provider — factory + handle + finalize stub

**Files:**
- Create: `eden/sandboxes/vercel/__init__.py`
- Create: `tests/unit/test_vercel_provider.py`

This task lands the factory, `_VercelHandle` with all five methods (with `finalize` stubbed for Task 2), the `_upload_tree` helper, and the `_snapshot_remote` helper.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_vercel_provider.py`:

```python
"""Verify vercel provider factory + _VercelHandle methods (no finalize yet)."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import BranchStrategy, CreateOptions, ExecResult
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable
from eden.sandboxes.vercel import provider as vercel_provider

pytestmark = pytest.mark.unit


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="test",
    )


def _mock_client(post_returns: dict[str, object] | list[dict[str, object]] | None = None) -> MagicMock:
    """Build a MagicMock(spec=RestClient) whose post() returns canned data."""
    client = MagicMock(spec=RestClient)
    if isinstance(post_returns, list):
        client.post.side_effect = post_returns
    elif post_returns is not None:
        client.post.return_value = post_returns
    return client


def test_provider_kind_and_name() -> None:
    p = vercel_provider(access_token="test-token")
    assert p.kind == "isolated"
    assert p.name == "vercel"


def test_provider_supports_default_strategies() -> None:
    p = vercel_provider(access_token="test-token")
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_raises_when_no_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    p = vercel_provider()  # no access_token arg, no env var
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == "vercel"


def test_create_reads_token_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "env-token")
    captured_headers: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_headers.update(kw["headers"])  # type: ignore[call-overload]
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider()
    p.create(_opts(tmp_path))
    assert captured_headers["Authorization"] == "Bearer env-token"


def test_create_uses_explicit_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    captured_url: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_url["base_url"] = str(kw["base_url"])
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", base_url="https://vercel.local")
    p.create(_opts(tmp_path))
    assert captured_url["base_url"] == "https://vercel.local"


def test_create_posts_sandbox_with_runtime_and_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    captured_payload: dict[str, object] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            self.post = MagicMock(side_effect=self._post)
            self.close = MagicMock()
            self.delete = MagicMock()

        def _post(self, path: str, *, json: object, params: object = None) -> dict[str, object]:
            if path == "/v1/sandboxes":
                captured_payload["payload"] = json
                return {"id": "sb-9"}
            return {"stdout": "", "stderr": "", "exit_code": 0}

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", runtime="python313", env={"FOO": "bar"})
    p.create(_opts(tmp_path))
    payload = captured_payload["payload"]
    assert isinstance(payload, dict)
    assert payload["runtime"] == "python313"
    assert payload["env"] == {"FOO": "bar"}
    assert payload["name"] == "test"


def test_team_id_threaded_as_query_param(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    captured_calls: list[dict[str, object]] = []

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            self.post = MagicMock(side_effect=self._post)
            self.close = MagicMock()
            self.delete = MagicMock(side_effect=self._delete)

        def _post(self, path: str, *, json: object, params: object = None) -> dict[str, object]:
            captured_calls.append({"path": path, "params": params})
            if path == "/v1/sandboxes":
                return {"id": "sb-7"}
            return {"stdout": "", "stderr": "", "exit_code": 0}

        def _delete(self, path: str, *, params: object = None) -> None:
            captured_calls.append({"path": path, "params": params, "method": "DELETE"})

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", team_id="team-42")
    p.create(_opts(tmp_path))
    # Every call should carry teamId=team-42 in params.
    for call in captured_calls:
        assert call["params"] == {"teamId": "team-42"}, f"call {call} missing teamId"


def test_handle_exec_returns_exec_result() -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = _mock_client(
        {"stdout": "hello\n", "stderr": "", "exit_code": 0},
    )
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    result = handle.exec("echo hello")
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    args, kwargs = client.post.call_args
    assert args[0] == "/v1/sandboxes/sb-1/exec"
    assert kwargs["json"]["command"] == "echo hello"


def test_handle_exec_returns_neg_one_on_rest_failure() -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    result = handle.exec("anything")
    assert result.exit_code == -1
    assert "network down" in result.stderr


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    handle.copy_file_in(src, Path("/workspace/dst.bin"))
    _args, kwargs = client.post.call_args
    cmd = kwargs["json"]["command"]
    expected_b64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
    assert expected_b64 in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    client = _mock_client({"stdout": "", "stderr": "boom", "exit_code": 1})
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    with pytest.raises(ExecFailed):
        handle.copy_file_in(src, Path("/workspace/dst"))


def test_handle_close_deletes_sandbox() -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    handle.close()
    client.delete.assert_called_once_with("/v1/sandboxes/sb-1", params=None)
    client.close.assert_called_once()


def test_handle_close_idempotent_on_not_found() -> None:
    from eden.errors import RestNotFoundError
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    client.delete.side_effect = RestNotFoundError(
        message="404", status=404, url="https://x/v1/sandboxes/sb-1",
    )
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    handle.close()  # must not raise
    client.close.assert_called_once()
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_vercel_provider.py -v`
Expected: FAIL — `eden.sandboxes.vercel` not found.

- [ ] **Step 3: Implement the vercel provider**

Create `eden/sandboxes/vercel/__init__.py`:

```python
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

        # Upload host worktree contents to /workspace, then snapshot baseline.
        try:
            _upload_tree(
                client, sandbox_id,
                src=opts.worktree_path, dst=_SANDBOX_WORKDIR,
                team_id=resolved_team,
            )
            baseline = _snapshot_remote(
                client, sandbox_id,
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
        # Stub for Task 2. Returning applied=False so any caller seeing
        # finalize() before Task 2 ships gets a clean no-op.
        return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)

    def close(self) -> None:
        try:
            self.client.delete(
                f"/v1/sandboxes/{self.sandbox_id}",
                params=self._params(),
            )
        except RestNotFoundError:
            pass  # already gone — idempotent close
        except Exception:
            pass  # don't propagate teardown errors (matches docker/podman/daytona)
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
    """Upload every file under `src` (host) to `dst` (sandbox), preserving structure."""
    params = {"teamId": team_id} if team_id else None
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if any(part in (".git", ".eden") for part in rel.parts):
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        target = dst / rel
        cmd = (
            f"mkdir -p {target.parent.as_posix()} && "
            f"echo {b64} | base64 -d > {target.as_posix()}"
        )
        result = client.post(
            f"/v1/sandboxes/{sandbox_id}/exec",
            json={"command": cmd},
            params=params,
        )
        if int(result.get("exit_code", result.get("exitCode", 0))) != 0:
            raise RuntimeError(
                f"upload of {rel} failed: {result.get('stderr', '')}"
            )


def _snapshot_remote(
    client: RestClient,
    sandbox_id: str,
    *,
    root: Path,
    team_id: str | None,
) -> dict[Path, str]:
    """REST-shell `find ... | xargs sha256sum` and parse stdout into the
    `dict[Path, hex]` shape produced by `patch_sync.snapshot()` locally.
    """
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
```

Note: `finalize` is stubbed; Task 2 fills it in. The `_snapshot_remote` and `_upload_tree` helpers are present and used at create time.

Important: `RestClient.post` and `RestClient.delete` from Phase 4b accept `params` as a keyword argument (the underlying `requests.Session.request` threads it as URL query params). Verify this by reading `eden/providers/_impl/http_rest.py`. If the signature is `post(self, path, *, json=None)` only (no `params`), the implementer must extend `RestClient.post`/`delete` to accept `params` first — that's a small change to the existing 4b helper.

If the existing `RestClient.post` already accepts `params=None` (it does — Phase 4b's signature was `post(self, path: str, *, json=None) -> dict`, and `_request` already passes through `params`), the call from vercel needs to thread `params` to `_request`. **Read `eden/providers/_impl/http_rest.py` first** and confirm that `post()` and `delete()` accept and forward `params`. If not, extend them — the implementer should commit that extension as a separate small change BEFORE the vercel commit.

Read the existing `RestClient` first:

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  cat eden/providers/_impl/http_rest.py | head -80
```

If `post()` only accepts `json` and not `params`, **extend it first**:
- Add `params: Mapping[str, Any] | None = None` to `post()` and `delete()` signatures.
- Pass it through to `self._request(method, path, params=params, ...)`.

`_request` already accepts `params`. The methods just need to surface it.

If you do extend `RestClient`, commit that change separately:

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/providers/_impl/http_rest.py && \
git commit -m "feat(http_rest): surface params kwarg on RestClient.post/delete"
```

Then proceed with the vercel commit below.

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_vercel_provider.py -v`
Expected: PASS — 13 tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/sandboxes/vercel tests/unit/test_vercel_provider.py && \
.venv/bin/ruff format eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
.venv/bin/ruff format --check eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
.venv/bin/ruff check --fix eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
.venv/bin/ruff check eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
git commit -m "feat(vercel): add factory + _VercelHandle (exec/copy/close); finalize stub"
```

DO NOT use `git add eden/sandboxes/vercel`.

---

## Task 2: Vercel finalize

**Files:**
- Modify: `eden/sandboxes/vercel/__init__.py` (replace stub + add 2 imports)
- Modify: `tests/unit/test_vercel_provider.py` (append 4 finalize tests)

- [ ] **Step 1: Append finalize tests**

Append to the END of `tests/unit/test_vercel_provider.py`:

```python


def test_finalize_no_changes_returns_applied_true(tmp_path: Path) -> None:
    """When sandbox snapshot equals baseline, finalize is a no-op success."""
    from eden.sandboxes.vercel import _VercelHandle

    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
        team_id=None,
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is True
    assert fr.files_changed == ()
    assert fr.patch_size_bytes == 0


def test_finalize_pulls_added_files_to_target(tmp_path: Path) -> None:
    """Sandbox has a file not in baseline — finalize REST-pulls it to target."""
    from eden.sandboxes.vercel import _VercelHandle

    target = tmp_path / "target"
    target.mkdir()

    base64_payload = "aGVsbG8="  # "hello"
    client = MagicMock(spec=RestClient)
    client.post.side_effect = [
        {"stdout": "abc123  ./new.txt\n", "stderr": "", "exit_code": 0},
        {"stdout": base64_payload, "stderr": "", "exit_code": 0},
    ]
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={},
        team_id=None,
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert (target / "new.txt").read_bytes() == b"hello"
    assert Path("new.txt") in fr.files_changed


def test_finalize_propagates_deletes(tmp_path: Path) -> None:
    """Baseline has a file; sandbox snapshot doesn't — finalize removes it from target."""
    from eden.sandboxes.vercel import _VercelHandle

    target = tmp_path / "target"
    target.mkdir()
    (target / "to_delete.txt").write_text("gone soon", encoding="utf-8")

    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={Path("to_delete.txt"): "old-hash"},
        team_id=None,
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert not (target / "to_delete.txt").exists()


def test_finalize_returns_not_applied_on_snapshot_failure(tmp_path: Path) -> None:
    """REST failure during finalize snapshot → soft-fail."""
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
        team_id=None,
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is False
```

- [ ] **Step 2: Run tests to verify they fail**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_vercel_provider.py -v 2>&1 | tail -10`
Expected: FAIL — the stub returns `applied=False` for everything.

- [ ] **Step 3: Replace the finalize stub**

In `eden/sandboxes/vercel/__init__.py`:

**3a — Add two imports.** At the top of the file, alphabetically:
- Add `import tempfile` after `import os`.
- Add `from eden.providers._impl import patch_sync` (after the existing `from eden.providers._impl.http_rest import RestClient`).

**3b — Replace the finalize stub.** Find:

```python
    def finalize(self, target: Path) -> FinalizeResult:
        # Stub for Task 2. Returning applied=False so any caller seeing
        # finalize() before Task 2 ships gets a clean no-op.
        return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)
```

Replace with:

```python
    def finalize(self, target: Path) -> FinalizeResult:
        try:
            after = _snapshot_remote(
                self.client, self.sandbox_id,
                root=self.worktree_path,
                team_id=self.team_id,
            )
        except Exception:
            return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)

        diff_result = patch_sync.diff(before=self.baseline, after=after)
        if not (diff_result.added or diff_result.changed or diff_result.removed):
            return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

        # Pull each added/changed file to a tmp dir, then patch_sync.apply against target.
        with tempfile.TemporaryDirectory() as tmp_root_str:
            tmp_root = Path(tmp_root_str)
            for rel in sorted(diff_result.added | diff_result.changed):
                self.copy_file_out(self.worktree_path / rel, tmp_root / rel)
            return patch_sync.apply(diff_result, src=tmp_root, dst=target)
```

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_vercel_provider.py -v`
Expected: PASS — 17 tests (13 from T1 + 4 new).

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/sandboxes/vercel tests/unit/test_vercel_provider.py && \
.venv/bin/ruff format eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
.venv/bin/ruff format --check eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
.venv/bin/ruff check --fix eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
.venv/bin/ruff check eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/sandboxes/vercel/__init__.py tests/unit/test_vercel_provider.py && \
git commit -m "feat(vercel): implement finalize via patch_sync.diff/apply over remote snapshot"
```

---

## Task 3: Fake-vercel test infrastructure

**Files:**
- Create: `tests/_fake_vercel/__init__.py`

(No standalone tests; the shim is exercised by Task 4's e2e tests.)

- [ ] **Step 1: Implement the fake server**

Create `tests/_fake_vercel/__init__.py`:

```python
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

        def do_POST(self) -> None:  # noqa: N802 (HTTP-spec name)
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
                    self._send_json(200, {
                        "stdout": proc.stdout,
                        "stderr": proc.stderr,
                        "exit_code": proc.returncode,
                    })
                except subprocess.TimeoutExpired:
                    self._send_json(200, {
                        "stdout": "",
                        "stderr": "timeout",
                        "exit_code": 124,
                    })
                return
            self._send_json(404, {"error": f"no such route: {path}"})

        def do_DELETE(self) -> None:  # noqa: N802
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
```

- [ ] **Step 2: Verify imports**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/python -c "from tests._fake_vercel import start_fake_vercel; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy tests/_fake_vercel && \
.venv/bin/ruff format tests/_fake_vercel/__init__.py && \
.venv/bin/ruff format --check tests/_fake_vercel/__init__.py && \
.venv/bin/ruff check --fix tests/_fake_vercel/__init__.py && \
.venv/bin/ruff check tests/_fake_vercel/__init__.py
```
Expected: All clean.

- [ ] **Step 4: Commit (stage by name — only 1 file)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add tests/_fake_vercel/__init__.py && \
git commit -m "test: add fake-vercel ThreadingHTTPServer for phase 4c e2e tests"
```

DO NOT use `git add tests/_fake_vercel`.

---

## Task 4: E2E smoke test for vercel

**Files:**
- Create: `tests/e2e/test_vercel_smoke.py`

- [ ] **Step 1: Write the e2e test**

Create `tests/e2e/test_vercel_smoke.py`:

```python
"""Smoke E2E: simulated_agent + vercel provider (fake server) + finalize."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes import vercel as vercel_sandbox
from tests._fake_vercel import start_fake_vercel

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-vercel shell-execs use /bin/sh, not available on Windows",
)
def test_vercel_finalize_writes_sandbox_changes_to_host(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: a sandbox hook writes a file inside the fake-vercel sandbox;
    finalize() REST-pulls it via copy_file_out and patch_sync.apply lands it
    on the host worktree, and the orchestrator emits `[eden] finalized:`."""
    state_dir = tmp_path / "fake-vercel-state"
    start_fake_vercel(monkeypatch=monkeypatch, state_dir=state_dir)

    sandbox_hook = eden.Hook(
        cmd='cd /workspace && echo "hello-from-vercel" > new_file.txt',
    )
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="working\n<promise>COMPLETE</promise>\n"),
        sandbox=vercel_sandbox.provider(),  # token from env (set by fake)
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    target_file = e2e_git_repo / "new_file.txt"
    assert target_file.exists(), (
        f"expected {target_file} to exist after finalize; "
        f"log: {result.log_file_path.read_text() if result.log_file_path else '<no log>'}"
    )
    assert target_file.read_text(encoding="utf-8").strip() == "hello-from-vercel"

    assert result.log_file_path is not None
    log_body = result.log_file_path.read_text(encoding="utf-8")
    assert "[eden] finalized:" in log_body
    assert "applied=True" in log_body


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-vercel shell-execs use /bin/sh, not available on Windows",
)
def test_vercel_finalize_propagates_deletes(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a file inside the fake-vercel sandbox propagates to the host."""
    assert (e2e_git_repo / "README.md").exists()
    state_dir = tmp_path / "fake-vercel-state"
    start_fake_vercel(monkeypatch=monkeypatch, state_dir=state_dir)

    sandbox_hook = eden.Hook(cmd="cd /workspace && rm README.md")
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=vercel_sandbox.provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert not (e2e_git_repo / "README.md").exists()
    assert result.log_file_path is not None
    assert "applied=True" in result.log_file_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the e2e tests**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/e2e/test_vercel_smoke.py -v`
Expected: PASS — 2 tests on macOS/Linux.

- [ ] **Step 3: Run combined unit + e2e suite (regression check)**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3`
Expected: All tests pass. Total: 385 (Phase 4b) + 17 unit + 2 e2e + (possibly 1 if RestClient was extended) = ~404 tests.

- [ ] **Step 4: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy tests/e2e/test_vercel_smoke.py && \
.venv/bin/ruff format tests/e2e/test_vercel_smoke.py && \
.venv/bin/ruff format --check tests/e2e/test_vercel_smoke.py && \
.venv/bin/ruff check --fix tests/e2e/test_vercel_smoke.py && \
.venv/bin/ruff check tests/e2e/test_vercel_smoke.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add tests/e2e/test_vercel_smoke.py && \
git commit -m "test(e2e): add vercel smoke run via fake-vercel server"
```

---

## Task 5: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump status line**

Edit `README.md:5`. Replace the existing line with:

```markdown
> **Status:** Pre-alpha. Phases 1–4c complete: package skeleton, provider Protocols, worktree manager, `no_sandbox`/`docker`/`podman` bind-mount providers, local `isolated` patch-sync provider, `daytona` and `vercel` cloud providers, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent` and `claude_code` agents, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, Claude Code session JSONL capture, and post-iteration `finalize()` for isolated/cloud handles. Other agents (5), CLI scaffolder (6), and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add README.md && \
git commit -m "docs: bump README status to phase 4c complete"
```

---

## Final verification (after every task is committed)

- [ ] **Step 1: Full local CI parity check**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/ruff format --check eden tests && \
.venv/bin/ruff check --no-cache eden tests && \
.venv/bin/mypy --strict eden tests && \
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```
Expected: every command Success / PASS. Coverage ≥ 70%.

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

- [ ] **Step 3: Tag the phase**

```bash
git tag -a phase-4c -m "Phase 4c: vercel cloud sandbox provider"
git push origin phase-4c
```

---

## Notes for the implementer

- **`RestClient.post`/`delete` may need a `params` kwarg.** Phase 4b's `RestClient._request` already accepts `params`, but the public `post()`/`delete()` methods may not surface it. If they don't, extend them in a separate small commit BEFORE Task 1's vercel commit. Daytona didn't need it because Daytona auth isn't team-scoped; Vercel needs it.
- **Empty-string check on `RestClient.delete`.** The current `delete()` may not pass `params=None` through. Verify.
- **`_VercelHandle.team_id` carried as a field.** All REST calls thread it as `?teamId=<id>` query parameter when set.
- **REST endpoints are empirically derived.** The fake server defines the canonical contract for 4c; if real Vercel diverges (e.g., different path structure, different response shape), update the handle to match without touching anything else.
- **Soft failure on finalize errors.** Same pattern as Phase 3b session capture, Phase 4a isolated finalize, Phase 4b daytona finalize.
- **REST infrastructure failure → exception; shell exit non-zero → ExecResult.** The orchestrator's existing handling depends on this distinction.
- **macOS BSD-`base64` quirk** in the fake server (test infra only). Real Vercel runs Linux microVMs with GNU coreutils.
- **Sandbox-hook commands MUST start with `cd /workspace &&`** for vercel/daytona — same rule. The cloud sandbox shell defaults to `/`, not `/workspace`.
- **Coverage gate stays at 70%.** Phase 4b baseline 93.73%; 4c adds heavily-tested code, total stays well above gate.
- **Frequent commits.** 5 tasks total — each lands one commit (T1 may also commit a small RestClient extension as a separate commit if needed).

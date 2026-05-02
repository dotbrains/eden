# Eden Phase 4b — Daytona Cloud Sandbox Provider Design

**Status:** Approved design. Implementation to follow via `superpowers:writing-plans`.

**Predecessors:** Phase 2 (sandbox foundations + docker bind-mount). Phase 3a (orchestration). Phase 3b (Claude Code agent). Phase 4a (provider parity local — `IsolatedSandboxHandle` Protocol, `make_isolated_provider`, `patch_sync` module, local `isolated` provider, podman). Latest commit on main: `22286cd`.

**Goal:** Add the `daytona` cloud sandbox provider as an `IsolatedSandboxHandle` over Daytona's REST API, plus a shared `eden/providers/_impl/http_rest.py` REST-client helper that 4c will reuse for Vercel.

**Out of scope (deferred to later phases):**
- `vercel` cloud sandbox provider (Phase 4c — needs either an official Python SDK or a deliberate decision to consume Vercel's undocumented REST surface).
- Real-Daytona credentialed CI tests (Phase 7 polish).
- Daytona snapshot/restore (every iteration is a fresh sandbox in 4b).
- Streaming `exec` output (Daytona's REST `execute` is atomic; `on_line` invoked once after the call completes).
- Direct file-API endpoints for `copy_file_in/out` (4b uses base64-via-exec fallback for Daytona-surface compatibility).
- Other agents (codex/opencode/pi — Phase 5).
- CLI scaffolder (Phase 6).

---

## 1. Public surface added

```python
def eden.sandboxes.daytona.provider(
    *,
    image: str = "ubuntu:24.04",
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
```

`daytona` is accessed via its sub-package (`eden.sandboxes.daytona.provider(...)`) — same pattern as `docker`/`podman`/`isolated`. No top-level re-export of provider factories.

**Re-exported at the top of the `eden` package:**

```python
from eden import RestError, RestAuthError, RestNotFoundError, RestRateLimited
```

These four error classes are 4b's contribution to the top-level error surface.

---

## 2. Architecture

### 2.1 New + modified files

```
eden/
├── providers/
│   └── _impl/
│       └── http_rest.py             # NEW — RestClient + 4 error classes
├── sandboxes/
│   └── daytona/                     # NEW directory
│       └── __init__.py              # NEW — daytona() factory + _DaytonaHandle
├── errors.py                        # MODIFY — add RestError + 3 subclasses
└── __init__.py                      # MODIFY — re-export RestError + subclasses

tests/
├── _fake_daytona/                   # NEW dir (test infra; underscore prevents pytest collection)
│   └── __init__.py                  # NEW — start_fake_daytona() ThreadingHTTPServer
├── unit/
│   ├── test_http_rest.py            # NEW — RestClient tests
│   └── test_daytona_provider.py     # NEW — factory + handle method tests
└── e2e/
    └── test_daytona_smoke.py        # NEW — full pipeline via fake server

pyproject.toml                       # MODIFY — add daytona = ["requests >= 2.32"]
README.md                            # MODIFY — bump status to phase 4b complete
```

Every new file under the project's ~300-LoC budget. Largest expected: `eden/providers/_impl/http_rest.py` (~200 LoC), `eden/sandboxes/daytona/__init__.py` (~250 LoC).

### 2.2 Per-iteration data flow

```
User: eden.run(agent=..., sandbox=daytona.provider(api_key=..., image=...))
        ↓
_run_loop → resolve_setup → create_worktree (Phase 4a worktree manager)
        ↓
sandbox.create(opts):
    rest = RestClient(base_url, headers={"Authorization": "Bearer ..."}, ...)
    response = rest.post("/api/sandbox", json={"image": image, "env": ..., "name": ...})
    sandbox_id = response["id"]
    _upload_tree(rest, sandbox_id, src=opts.worktree_path, dst=/workspace)
    baseline = _snapshot_remote(rest, sandbox_id, root=/workspace)
        # Internally: rest.post("/toolbox/{id}/process/execute",
        #   json={"command": "find /workspace -type f -print0 | xargs -0 sha256sum"})
        # Parse stdout → dict[Path, hex]
    return _DaytonaHandle(rest, sandbox_id, /workspace, host_worktree, baseline)
        ↓
agent runs (via Phase 3a's _AgentRunner).
_DaytonaHandle.exec → REST POST to /toolbox/{id}/process/execute.
        ↓
loop completes (success path)
        ↓
if hasattr(handle, "finalize"):
    finalize_result = handle.finalize(target=wt.host_repo_path)
        # internally:
        #   after = _snapshot_remote(...)
        #   d = patch_sync.diff(before=baseline, after=after)
        #   pull each added|changed file via copy_file_out → tmp_dir
        #   patch_sync.apply(d, src=tmp_dir, dst=target)
        ↓
handle.close():
    rest.delete("/api/sandbox/{id}")  (404 → silent; matches docker/podman)
    rest.close()
```

### 2.3 Boundaries

- `http_rest.py` knows HTTP, retries, auth headers. Doesn't know sandboxes.
- `daytona/__init__.py` knows Daytona's endpoints + sandbox lifecycle. Uses `RestClient` for transport, `patch_sync` for diff math. Doesn't know `_AgentRunner` or orchestrator details.
- `_DaytonaHandle.exec` returns `ExecResult` (Phase 2 type). REST infrastructure failures (auth, 5xx after retry) raise `RestError`-derived exceptions; non-zero shell exits become `ExecResult(exit_code=N)` (NOT exceptions) — same convention as docker/podman.

---

## 3. Component contracts

### 3.1 `RestClient` (`eden/providers/_impl/http_rest.py`)

```python
@dataclass
class RestClient:
    base_url: str
    headers: Mapping[str, str]
    timeout: float = 60.0
    max_retries: int = 3
    _session: requests.Session = field(default_factory=requests.Session)

    def get(self, path: str, *, params=None) -> dict[str, Any]: ...
    def post(self, path: str, *, json=None) -> dict[str, Any]: ...
    def delete(self, path: str) -> None: ...
    def close(self) -> None: ...
```

**Behaviors:**
- **Retry policy:** `5xx` (500/502/503/504) and `429` retried up to `max_retries` with exponential backoffs `[0.5s, 1.0s, 2.0s]`. `4xx` other than 429 raise immediately. `requests.RequestException` (connection/DNS) retried as if 5xx.
- **JSON parsing:** `post()`/`get()` return parsed JSON dict. Non-JSON 2xx body raises `RestError`. `delete()` skips JSON parsing.
- **Headers:** caller-supplied (typically `Authorization: Bearer …`) injected on every request. Client adds nothing else.
- **Connection pooling:** `requests.Session` reuses TCP connections; important when the orchestrator does dozens of `exec` calls per iteration.
- **`_url(path)`:** accepts both relative paths and absolute URLs. Robust to trailing slashes in `base_url`.
- **Close:** `RestClient.close()` calls `session.close()`; provider's handle `close()` calls it as part of cleanup.

**Error mapping:**

| HTTP status | Raised exception |
|---|---|
| 200-299 | (success — return parsed JSON) |
| 401, 403 | `RestAuthError` |
| 404 | `RestNotFoundError` |
| 429 (after retries) | `RestRateLimited` |
| Other 4xx | `RestError` |
| 5xx (after retries) | `RestError` |
| Connection error (after retries) | `RestError(status=0)` |

### 3.2 `RestError` hierarchy (`eden/errors.py`)

Four new classes appended to existing 14:

```python
class RestError(EdenError):
    """Non-2xx response from a REST API. Carries status, body, url for debugging."""
    code: str = "rest.error"
    # carries status: int, body: str, url: str fields

class RestAuthError(RestError):
    code: str = "rest.auth"           # 401/403

class RestNotFoundError(RestError):
    code: str = "rest.not_found"      # 404

class RestRateLimited(RestError):
    code: str = "rest.rate_limited"   # 429
```

Same `code/message/hint/cause` constructor as Phase 3a runtime errors, plus three new fields (`status: int`, `body: str`, `url: str`) for debugging. `status=0` indicates a connection-level failure with no HTTP response.

### 3.3 `daytona.provider()` factory

| Param | Default | Effect |
|---|---|---|
| `image` | `"ubuntu:24.04"` | OS image Daytona provisions |
| `api_key` | `None` → `os.environ["DAYTONA_API_KEY"]` | Bearer token |
| `organization_id` | `None` → `os.environ["DAYTONA_ORGANIZATION_ID"]` | Optional `X-Daytona-Organization-ID` header |
| `base_url` | `None` → `os.environ["DAYTONA_API_URL"]` → `"https://api.daytona.io"` | Daytona API root |
| `env` | `None` | Per-provider env merged with caller env |
| `timeout` | `60.0` | Per-REST-call timeout (seconds) |

**Factory is cheap and side-effect-free:** no env-var reads at factory time. All resolution happens inside `_create()` so `api_key` is read just-in-time. `ProviderUnavailable(provider="daytona", binary="DAYTONA_API_KEY")` raised at `create()` time when no key is available.

### 3.4 `_DaytonaHandle` dataclass

```python
@dataclass
class _DaytonaHandle:
    client: RestClient
    sandbox_id: str
    worktree_path: Path                # /workspace (sandbox-side)
    host_worktree_path: Path           # the original host worktree
    baseline: dict[Path, str]          # snapshot at create-time

    def exec(self, cmd, *, on_line=None, cwd=None, env=None, timeout=None) -> ExecResult: ...
    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def finalize(self, target: Path) -> FinalizeResult: ...
    def close(self) -> None: ...
```

**`exec`:** POSTs `{command, cwd, env, timeout}` to `/toolbox/{id}/process/execute`. Returns `ExecResult(stdout, stderr, exit_code)` from the response. `RestError` exceptions are caught and surfaced as `ExecResult(exit_code=-1, stderr=str(exc))` so the orchestrator's loop doesn't see exceptions for ordinary REST errors. Non-zero shell exits become `ExecResult(exit_code=N)` (NOT exceptions) — same convention as docker/podman.

**`copy_file_in/out`:** base64-encode-and-shell via `exec`. Always works against Daytona's documented surface. If the implementer discovers a clean file API in pre-flight research, they swap these methods for direct REST calls (the public method signatures stay the same).

**`finalize`:** snapshots remote dir via `_snapshot_remote`, diffs against baseline using `patch_sync.diff`, pulls each `added | changed` file via `copy_file_out` into a `tempfile.TemporaryDirectory`, then `patch_sync.apply(diff, src=tmp_dir, dst=target)`. Reuses Phase 4a's diff/apply logic verbatim — only `snapshot` source differs.

**`close`:** DELETE the sandbox; ignore `RestNotFoundError` (already gone). Other exceptions silently swallowed (matches docker/podman teardown). Always calls `client.close()` to release the connection pool.

### 3.5 `_upload_tree(client, sandbox_id, *, src, dst)`

Uploads every file under `src` (host) to `dst` (sandbox), preserving structure. Uses base64-shell-via-exec; ignores `.git` and `.eden`. Called at create time so the agent has the same starting state as bind-mount providers. Raises if any individual upload fails (so `_create` can DELETE the sandbox + close the client).

### 3.6 `_snapshot_remote(client, sandbox_id, *, root)`

REST-shells `find <root> -type f -print0 | xargs -0 sha256sum`, parses stdout into Phase 4a's `dict[Path, hex]` snapshot shape. The returned dict has the same structure `patch_sync.snapshot()` produces locally — both `patch_sync.diff` and `patch_sync.apply` operate on this shape.

The shell command excludes `.git` and `.eden` to match `patch_sync.snapshot`'s default ignore list.

### 3.7 `pyproject.toml`

Adds to `[project.optional-dependencies]`:

```toml
daytona = ["requests >= 2.32"]
vercel = ["requests >= 2.32"]
```

Base install (`pip install eden`) stays slim. Daytona users `pip install eden[daytona]`. Pre-emptively listing `vercel` so Phase 4c doesn't re-touch this.

### 3.8 `eden/__init__.py`

Adds top-level re-exports of the four REST error classes:

```python
from eden.errors import RestAuthError, RestError, RestNotFoundError, RestRateLimited
```

Plus `__all__` entries for each. The `daytona.provider` factory itself is NOT re-exported (same pattern as docker/podman/isolated).

---

## 4. Error handling matrix

| Failure | Behavior | Surfaced as |
|---|---|---|
| `DAYTONA_API_KEY` not set + no kwarg | `ProviderUnavailable(provider="daytona", binary="DAYTONA_API_KEY")` raised at `create()` | Propagates out of `eden.run()` |
| Daytona REST 401/403 on create | `RestAuthError` from `RestClient.post` | Propagates (auth error is fatal — no retry) |
| Daytona REST 5xx on create | Retried 3× with backoff; if exhausted → `RestError` | Propagates |
| Connection refused / DNS failure | Retried as 5xx; if exhausted → `RestError(status=0)` | Propagates |
| Sandbox response missing `id` field | `ProviderUnavailable(...)` (treats Daytona-surface change as unavailability) + `client.close()` | Propagates |
| `_upload_tree` fails mid-upload | Sandbox is DELETE'd, `client.close()`'d, exception propagates | Caller sees error; no orphan sandbox |
| `exec` REST returns 5xx after retries | `ExecResult(stdout="", stderr=str(exc), exit_code=-1)` (NOT raised) | Orchestrator sees `exit_code=-1`, loop continues |
| `exec` shell exit non-zero | `ExecResult(stdout, stderr, exit_code=N)` — NOT exception | Same as docker/podman |
| `copy_file_in/out` shell exit non-zero | `ExecFailed(result, argv_or_cmd)` raised | Propagates (this IS an Eden-API failure) |
| `finalize` snapshot fails | `FinalizeResult(applied=False, ...)` | Orchestrator's existing soft-fail wrapper writes `[eden] finalize failed` |
| `finalize` per-file copy_file_out fails | `ExecFailed` propagates → orchestrator catches → soft-fail | Same as above |
| `close()` DELETE returns 404 | Silently swallowed (idempotent) | None |
| `close()` DELETE returns other error | Silently swallowed (matches docker/podman teardown) | None |

The "REST infrastructure failure → exception" vs "shell command failure → ExecResult" split is deliberate. The orchestrator's existing handling already understands `ExecResult` semantics from docker/podman; exceptions from `_DaytonaHandle.exec` would break that contract.

---

## 5. Concurrency

**No new threads in production code.** `RestClient` is sync; `_DaytonaHandle.exec` blocks the calling thread for the duration of the REST call (subject to `timeout`). The orchestrator's stdout-pump thread (Phase 3a) calls into `_DaytonaHandle.exec` synchronously, just as it does for `_DockerHandle.exec` today.

The fake server in tests runs on a `ThreadingHTTPServer` daemon thread — that's test infra only.

---

## 6. Testing strategy

### 6.1 `tests/_fake_daytona/__init__.py` test infrastructure

```python
def start_fake_daytona(
    *,
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
) -> str:
    """Spin up a ThreadingHTTPServer on localhost:<random-port>.

    Returns the base_url. Routes:
      POST /api/sandbox                              → create state_dir/<id>/, return {"id": <id>}
      POST /toolbox/<id>/process/execute             → subprocess.run(cmd, cwd=state_dir/<id>)
      DELETE /api/sandbox/<id>                       → shutil.rmtree(state_dir/<id>)

    Sets DAYTONA_API_KEY=test-token and DAYTONA_API_URL=<base_url> via
    monkeypatch.setenv so the provider doesn't fail unavailability check.
    Server runs on a daemon thread; teardown via fixture finalizer.
    """
```

Underscore-prefixed dir avoids pytest collection. Pattern proven by Phase 3b's `tests/_fake_claude/`.

### 6.2 Unit tests

**`tests/unit/test_http_rest.py` (~12 tests):**
- `RestClient.post` happy path — verifies headers + JSON body sent, response parsed.
- `RestClient.get` happy path — params threaded.
- `RestClient.delete` doesn't expect JSON.
- `_url` joins relative paths correctly; absolute URLs pass through.
- `5xx` retried up to `max_retries`; succeeds on third try.
- `5xx` after `max_retries` raises `RestError`.
- `429` retried, then raises `RestRateLimited` after exhaustion.
- `401` raises `RestAuthError` immediately (no retry).
- `403` raises `RestAuthError`.
- `404` raises `RestNotFoundError`.
- `500` non-JSON body raises `RestError` (not `ValueError`).
- `requests.RequestException` retried; final attempt raises `RestError(status=0)`.

All tests patch `RestClient._session.request`. No real network, no fake server.

**`tests/unit/test_daytona_provider.py` (~10 tests):**
- `provider()` returns `kind="isolated"`, `name="daytona"`.
- `create()` raises `ProviderUnavailable` when no api_key + no env var.
- `create()` reads `DAYTONA_API_KEY` from env when factory arg is `None`.
- `create()` reads `DAYTONA_ORGANIZATION_ID` from env; threaded into `X-Daytona-Organization-ID` header.
- `create()` reads `DAYTONA_API_URL` from env; threaded into `RestClient.base_url`.
- `create()` POSTs to `/api/sandbox` with `image`, `env`, `name`.
- `_DaytonaHandle.exec` POSTs to `/toolbox/{id}/process/execute` and returns `ExecResult` populated from response.
- `_DaytonaHandle.exec` returns `exit_code=-1` on REST failure (no exception).
- `_DaytonaHandle.copy_file_in` base64-encodes and shells via `exec`.
- `_DaytonaHandle.close` DELETEs `/api/sandbox/{id}`; idempotent on `RestNotFoundError`.

All tests use mocked `RestClient` (constructed via `MagicMock(spec=RestClient)`).

### 6.3 E2E tests

**`tests/e2e/test_daytona_smoke.py` (~2 tests):**
- `test_daytona_finalize_writes_sandbox_changes_to_host`: sandbox-hook (`echo "hi" > new_file.txt`) writes a file inside the fake-daytona sandbox state dir; `eden.run(...)` completes; `finalize` REST-pulls the file via `copy_file_out`; `patch_sync.apply` lands it on the host worktree. Asserts the synthetic `[eden] finalized: applied=True files=N bytes=M` appears in the log.
- `test_daytona_finalize_propagates_deletes`: sandbox-hook removes README.md; finalize propagates the delete to the host.

Both gated `@pytest.mark.skipif(sys.platform == "win32", ...)` because the fake server's shell-exec uses `/bin/sh`.

### 6.4 Coverage

Existing 70% gate retained. Phase 4a baseline 94.21%; 4b adds heavily-tested code so total stays above 90%.

### 6.5 Real-Daytona tests (deferred)

Not added in 4b. If they happen later, they'd be a separately-marked `daytona_real` test set, gated by env var. Phase 7 polish at earliest.

---

## 7. Backwards compatibility

- All Phase 2 / 3a / 3b / 4a tests pass unchanged.
- The orchestrator's existing finalize block (Phase 4a) handles `_DaytonaHandle.finalize` via the same `hasattr(handle, "finalize")` duck-check. No new orchestrator code.
- `_AgentRunner.cwd` (Phase 4a) correctly falls through to `None` for Daytona because `handle.worktree_path == /workspace` doesn't exist on the host filesystem — same logic as docker/podman.

---

## 8. Drop-in promise

Replacing `isolated.provider()` with `daytona.provider(api_key=..., image=...)` in any Phase 4a `eden.run(...)` call works without other changes. The orchestrator's `hasattr(handle, "finalize")` check fires the same patch-sync path for both. The agent's `build_command(ctx)` argv is identical — only the underlying `handle.exec` transport differs (subprocess vs REST).

---

## 9. Phase boundary

**Lands in 4b:** `RestClient` + 4 error classes, `daytona` provider, fake-daytona test infra, `pyproject.toml` optional dep, `eden/__init__.py` re-exports.

**Deferred to 4c:** `vercel` cloud provider (uses the same `RestClient`).

**Deferred to 5:** other agents (`codex`, `opencode`, `pi`).

**Deferred to 6:** CLI scaffolder.

**Deferred to 7:** docs + real-cloud credentialed CI tests.

---

**Estimated effort:** ~1 week, matching the original Phase 4 split.

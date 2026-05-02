# Eden Phase 4c — Vercel Cloud Sandbox Provider Design

**Status:** Approved design. Implementation to follow via `superpowers:writing-plans`.

**Predecessors:** Phase 4a (`IsolatedSandboxHandle`, `make_isolated_provider`, `patch_sync`). Phase 4b (`RestClient`, `RestError` family, `daytona` provider, fake-daytona test infra). Latest commit on main: `a501619`.

**Goal:** Add the `vercel` cloud sandbox provider as an `IsolatedSandboxHandle` over Vercel Sandbox's REST API. Reuse Phase 4b's `RestClient` for transport and `patch_sync` for finalize math.

**Out of scope (deferred to later phases):**
- Real-Vercel credentialed CI tests (Phase 7 polish).
- Vercel snapshot/restore lifecycle (every iteration is a fresh sandbox in 4c).
- Streaming `exec` output (Vercel REST `runCommand` is atomic; `on_line` callback invoked once after the call completes).
- Direct file-API endpoints for `copy_file_in/out` (4c uses base64-via-exec fallback for simplicity and parity with daytona).
- Other agents (codex/opencode/pi — Phase 5).
- CLI scaffolder (Phase 6).

---

## 1. Public surface added

```python
def eden.sandboxes.vercel.provider(
    *,
    runtime: str = "node24",
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
```

`vercel` is accessed via its sub-package (`eden.sandboxes.vercel.provider(...)`) — same pattern as `docker`/`podman`/`isolated`/`daytona`. No top-level re-export of provider factories.

**No new error classes.** Phase 4b's `RestError`/`RestAuthError`/`RestNotFoundError`/`RestRateLimited` are reused.

**No new top-level exports.** All required types are already on `eden.*` from 4a/4b.

---

## 2. Architecture

### 2.1 New + modified files

```
eden/
└── sandboxes/
    └── vercel/                      # NEW directory
        └── __init__.py              # NEW — vercel() factory + _VercelHandle

tests/
├── _fake_vercel/                    # NEW (test infra; underscore prevents pytest collection)
│   └── __init__.py                  # NEW — start_fake_vercel() ThreadingHTTPServer
├── unit/
│   └── test_vercel_provider.py      # NEW — factory + handle method tests (~13 tests)
└── e2e/
    └── test_vercel_smoke.py         # NEW — full pipeline via fake server (~2 tests)

pyproject.toml                       # already has vercel = ["requests >= 2.32"] (added in 4b)
README.md                            # MODIFY — bump status to phase 4c complete
```

Every new file under the project's ~300-LoC budget. Largest expected: `eden/sandboxes/vercel/__init__.py` (~250 LoC), `tests/_fake_vercel/__init__.py` (~150 LoC).

### 2.2 Per-iteration data flow (mirrors daytona almost exactly)

```
User: eden.run(agent=..., sandbox=vercel.provider(access_token=..., runtime=...))
        ↓
_run_loop → resolve_setup → create_worktree
        ↓
sandbox.create(opts):
    rest = RestClient(base_url, headers={"Authorization": "Bearer <token>"}, ...)
    response = rest.post("/v1/sandboxes", json={"runtime": runtime, "env": ..., "name": ...})
    sandbox_id = response["id"]
    _upload_tree(rest, sandbox_id, src=opts.worktree_path, dst=/workspace)
    baseline = _snapshot_remote(rest, sandbox_id, root=/workspace)
        # Internally: rest.post("/v1/sandboxes/{id}/exec",
        #   json={"command": "find /workspace -type f -print0 | xargs -0 sha256sum"})
    return _VercelHandle(rest, sandbox_id, /workspace, host_worktree, baseline)
        ↓
agent runs (via Phase 3a's _AgentRunner).
_VercelHandle.exec → REST POST to /v1/sandboxes/{id}/exec.
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
    rest.delete("/v1/sandboxes/{id}")
    rest.close()
```

### 2.3 Boundaries

- `RestClient` (Phase 4b) handles all HTTP transport — Vercel reuses it unchanged.
- `vercel/__init__.py` knows Vercel's endpoints + sandbox lifecycle. Uses `patch_sync` for diff math.
- `_VercelHandle.exec` returns `ExecResult` (Phase 2 type). REST infrastructure failures raise `RestError`-derived exceptions; non-zero shell exits become `ExecResult(exit_code=N)`. Same convention as docker/podman/daytona.

---

## 3. Component contracts

### 3.1 `vercel.provider()` factory

| Param | Default | Effect |
|---|---|---|
| `runtime` | `"node24"` | Vercel runtime identifier (e.g., `"node24"`, `"node22"`, `"python313"`) |
| `access_token` | `None` → `os.environ["VERCEL_TOKEN"]` | Bearer token |
| `team_id` | `None` → `os.environ["VERCEL_TEAM_ID"]` | Optional `?teamId=<id>` query parameter on every request |
| `base_url` | `None` → `os.environ["VERCEL_API_URL"]` → `"https://api.vercel.com"` | Vercel API root |
| `env` | `None` | Per-provider env merged with caller env |
| `timeout` | `60.0` | Per-REST-call timeout (seconds) |

Factory is cheap and side-effect-free. `ProviderUnavailable(provider="vercel", binary="VERCEL_TOKEN")` raised at `create()` time when no token is available.

`team_id` is threaded into the URL as a `?teamId=<id>` query parameter on all requests (Vercel convention for team-scoped resources). The `RestClient.get/post/delete` methods accept `params=`; the vercel handle passes `{"teamId": team_id}` if set.

### 3.2 `_VercelHandle` dataclass

```python
@dataclass
class _VercelHandle:
    client: RestClient
    sandbox_id: str
    worktree_path: Path                # /workspace (sandbox-side)
    host_worktree_path: Path
    baseline: dict[Path, str]
    team_id: str | None                # for query-param threading

    def exec(self, cmd, *, on_line=None, cwd=None, env=None, timeout=None) -> ExecResult: ...
    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def finalize(self, target: Path) -> FinalizeResult: ...
    def close(self) -> None: ...
```

**`exec`:** POSTs to `/v1/sandboxes/{id}/exec` with `{command, cwd, env, timeout}` and (if `team_id` set) `?teamId=<id>` query. Returns `ExecResult` from response. REST failures → `ExecResult(exit_code=-1, stderr=str(exc))`. Non-zero shell exits → `ExecResult(exit_code=N)`.

**`copy_file_in/out`:** base64-via-shell, identical to daytona. Raises `ExecFailed` on non-zero shell exit (because copy failures are Eden API failures, not user-script failures).

**`finalize`:** snapshots remote dir, diffs against baseline, pulls `added|changed` files via `copy_file_out` to a `tempfile.TemporaryDirectory`, then `patch_sync.apply(diff, src=tmp_dir, dst=target)`. Soft-fails to `FinalizeResult(applied=False, ...)` on any REST exception.

**`close`:** `DELETE /v1/sandboxes/{id}` (with optional `?teamId=`). Ignores `RestNotFoundError` (idempotent). Other exceptions silently swallowed (matches docker/podman/daytona teardown). Always calls `client.close()`.

### 3.3 `_upload_tree` and `_snapshot_remote`

Identical shape to daytona's helpers, but use the Vercel exec endpoint (`/v1/sandboxes/{id}/exec`). The snapshot shell command is identical (`find ... | xargs sha256sum`); the upload is identical (base64-via-shell mkdir+echo). The `team_id` is threaded into every REST call.

### 3.4 Vercel REST endpoints (empirically derived)

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/sandboxes` | POST | Create sandbox; payload `{runtime, env, name?}`; returns `{id}` |
| `/v1/sandboxes/{id}/exec` | POST | Run command; payload `{command, cwd?, env?, timeout?}`; returns `{stdout, stderr, exit_code}` |
| `/v1/sandboxes/{id}` | DELETE | Destroy sandbox |

These paths are derived from observation of Vercel Sandbox SDK conventions; they may shift in real Vercel deployments. Phase 7 polish should validate against the official API. The fake-vercel server in tests is the canonical contract for 4c — if real Vercel differs, adjust the handle to match without touching the rest of Eden.

---

## 4. Error handling matrix

| Failure | Behavior |
|---|---|
| `VERCEL_TOKEN` not set + no kwarg | `ProviderUnavailable(provider="vercel", binary="VERCEL_TOKEN")` at `create()` |
| Vercel REST 401/403 on create | `RestAuthError` propagates |
| Vercel REST 5xx on create | Retried 3× with backoff; `RestError` if exhausted |
| Connection refused / DNS failure | Retried as 5xx; `RestError(status=0)` if exhausted |
| Sandbox response missing `id` | `ProviderUnavailable(...)` + `client.close()` |
| `_upload_tree` fails mid-upload | DELETE sandbox + `client.close()`, exception propagates |
| `exec` REST failure after retries | `ExecResult(exit_code=-1, stderr=...)` (NOT raised) |
| `exec` shell exit non-zero | `ExecResult(exit_code=N)` (NOT exception) |
| `copy_file_in/out` shell exit non-zero | `ExecFailed` raised |
| `finalize` snapshot fails | `FinalizeResult(applied=False, ...)` |
| `finalize` per-file copy_file_out fails | `ExecFailed` propagates → orchestrator soft-fails |
| `close()` DELETE 404 | Silently swallowed (idempotent) |
| `close()` DELETE other error | Silently swallowed |

Identical error contract to daytona. The "REST infrastructure failure → exception; shell exit non-zero → ExecResult" split is preserved — orchestrator handling unchanged.

---

## 5. Concurrency

No new threads in production code. `RestClient` is sync; `_VercelHandle.exec` blocks the calling thread for the REST call duration. Fake server runs threaded only in tests.

---

## 6. Testing strategy

### 6.1 `tests/_fake_vercel/__init__.py` test infrastructure

```python
def start_fake_vercel(
    *,
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
) -> str:
    """Spin up a ThreadingHTTPServer on localhost:<random-port>.

    Routes:
      POST /v1/sandboxes              → create state_dir/<id>/, return {"id": <id>}
      POST /v1/sandboxes/<id>/exec    → subprocess.run(cmd, cwd=state_dir/<id>)
      DELETE /v1/sandboxes/<id>       → shutil.rmtree(state_dir/<id>)

    Sets VERCEL_TOKEN=test-token and VERCEL_API_URL=<base_url>. Returns base_url.
    """
```

Same shape as `_fake_daytona`, different routes. Path-rewriting (`/workspace` → `<sb_root>/workspace`) and macOS BSD-`base64` quirk (cat-piped fallback) are inherited from the fake-daytona pattern. The two fake servers SHARE no code; we accept the duplication for now (a future cleanup phase could extract a `_fake_cloud_server` base class if a third cloud provider materializes).

### 6.2 Unit tests (`tests/unit/test_vercel_provider.py`, ~13 tests)

Mirror daytona's test set:
- `provider()` returns `kind="isolated"`, `name="vercel"`.
- Default strategies supported.
- `create()` raises `ProviderUnavailable` when no token + no env var.
- `create()` reads `VERCEL_TOKEN`, `VERCEL_TEAM_ID`, `VERCEL_API_URL` from env.
- `create()` POSTs to `/v1/sandboxes` with `runtime`, `env`, `name`.
- `_VercelHandle.exec` POSTs to `/v1/sandboxes/{id}/exec` and returns `ExecResult`.
- `_VercelHandle.exec` returns `exit_code=-1` on REST failure (no exception).
- `_VercelHandle.copy_file_in` base64-shells via `exec`.
- `_VercelHandle.close` DELETEs `/v1/sandboxes/{id}`; idempotent on `RestNotFoundError`.
- `team_id` threaded into `?teamId=<id>` query parameter on every request.

Plus 4 finalize-specific tests (no-op success, added-file pull, deletion propagation, snapshot-failure soft-fail) — same as daytona.

### 6.3 E2E tests (`tests/e2e/test_vercel_smoke.py`, ~2 tests)

Mirror daytona's e2e:
- `test_vercel_finalize_writes_sandbox_changes_to_host` — sandbox-hook (`cd /workspace && echo > new_file.txt`) writes a file; finalize REST-pulls and `patch_sync.apply` lands it on host. Asserts `[eden] finalized: applied=True files=N bytes=M` in log.
- `test_vercel_finalize_propagates_deletes` — sandbox-hook removes README.md; finalize propagates the delete.

Both gated `@pytest.mark.skipif(sys.platform == "win32", ...)` because the fake server's shell-exec uses `/bin/sh`.

### 6.4 Coverage

Existing 70% gate retained. Phase 4b baseline 93.73%; 4c adds heavily-tested code so total stays above 90%.

---

## 7. Backwards compatibility

- All Phase 2 / 3a / 3b / 4a / 4b tests pass unchanged.
- The orchestrator's existing finalize block (Phase 4a) handles `_VercelHandle.finalize` via `hasattr(handle, "finalize")`. No new orchestrator code.
- `_AgentRunner.cwd` (Phase 4a) correctly falls through to `None` for vercel because `Path("/workspace").exists()` is `False` on the host.

---

## 8. Drop-in promise

Replacing `daytona.provider()` with `vercel.provider(access_token=..., runtime=...)` in any Phase 4b `eden.run(...)` call works without other changes. Only the underlying REST endpoint and auth header differ.

---

## 9. Phase boundary

**Lands in 4c:** `vercel` provider, fake-vercel test infra, e2e smoke, README bump.

**Deferred to 5:** other agents (`codex`, `opencode`, `pi`).

**Deferred to 6:** CLI scaffolder.

**Deferred to 7:** docs + real-cloud credentialed CI tests + Vercel REST endpoint validation against official API.

---

**Estimated effort:** ~3-4 days (smaller than 4b because the foundation work is done — RestClient, errors, patch_sync, finalize wiring all exist).

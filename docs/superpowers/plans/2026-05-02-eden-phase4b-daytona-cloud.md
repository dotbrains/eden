# Eden Phase 4b — Daytona Cloud Sandbox Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the `daytona` cloud sandbox provider as an `IsolatedSandboxHandle` over Daytona's REST API, plus a shared `eden/providers/_impl/http_rest.py` REST-client helper that 4c will reuse for Vercel.

**Architecture:** New `RestClient` + 4 typed error classes for shared HTTP plumbing. New `daytona/` package with a `provider()` factory and `_DaytonaHandle` that satisfies `IsolatedSandboxHandle` by REST-driving create/exec/file/destroy plus `patch_sync`-compatible snapshot/diff/apply for finalize. Cloud-shell-based file I/O via base64 (always works on Daytona's documented surface).

**Tech Stack:** Python 3.11+, new optional dep `requests >= 2.32`, Phase 4a's `make_isolated_provider`, `patch_sync` module, `IsolatedSandboxHandle` Protocol, `FinalizeResult`. Phase 4a's `_AgentRunner.cwd` and `_run_loop` finalize wiring already handle Daytona's "in-cloud workspace path" via the `path.exists()` fallback. CI matrix unchanged: 3 OS × 3 Python versions.

**Reference spec:** `docs/superpowers/specs/2026-05-02-eden-phase4b-daytona-cloud-design.md`

**Phase 4a base:** This plan assumes commit `22286cd` is on `main` (Phase 4a complete). Baseline: 343 unit+e2e tests passing, mypy strict clean across 126 source files, ruff clean, coverage 94.21%.

---

## File structure produced by this plan

```
eden/
├── providers/
│   └── _impl/
│       └── http_rest.py             # NEW — RestClient + retry logic
├── sandboxes/
│   └── daytona/                     # NEW directory
│       └── __init__.py              # NEW — daytona() factory + _DaytonaHandle
├── errors.py                        # MODIFY — add RestError + 3 subclasses
└── __init__.py                      # MODIFY — re-export RestError + subclasses

tests/
├── _fake_daytona/                   # NEW (test infra; underscore prevents pytest collection)
│   └── __init__.py                  # NEW — start_fake_daytona() ThreadingHTTPServer fixture
├── unit/
│   ├── test_http_rest.py            # NEW — RestClient unit tests (~12 tests)
│   └── test_daytona_provider.py     # NEW — provider factory + handle method tests (~10 tests)
└── e2e/
    └── test_daytona_smoke.py        # NEW — full pipeline via fake server (~2 tests)

pyproject.toml                       # MODIFY — add daytona/vercel optional deps
README.md                            # MODIFY — bump status to phase 4b complete
```

**File responsibilities:**

- `eden/providers/_impl/http_rest.py` — `RestClient` dataclass + auth-injection + retry-on-5xx/429 + error mapping. Reusable in 4c for Vercel.
- `eden/errors.py` — 4 new exception classes (`RestError`, `RestAuthError`, `RestNotFoundError`, `RestRateLimited`) appended to the existing 14.
- `eden/sandboxes/daytona/__init__.py` — `provider(*, image, api_key, organization_id, base_url, env, timeout)` factory + `_DaytonaHandle` dataclass + `_upload_tree` + `_snapshot_remote` helpers.
- `eden/__init__.py` — top-level re-exports of the 4 REST error classes.
- `tests/_fake_daytona/__init__.py` — `start_fake_daytona(monkeypatch, state_dir)` spins a `ThreadingHTTPServer` registering the 3 daytona routes; routes shell-exec to local subprocesses against `state_dir`.
- `pyproject.toml` — adds `daytona = ["requests >= 2.32"]` and `vercel = ["requests >= 2.32"]` to `[project.optional-dependencies]`.

---

## Pre-flight: confirm Phase 4a baseline + install requests

- [ ] **Step 1: Confirm working tree clean and on main**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  git status -s && git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expected: empty status, branch `main`, commit `2fc561a docs: add phase 4b ...` (or later).

- [ ] **Step 2: Confirm Phase 4a suite passes**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3
```
Expected: `343 passed` (Phase 4a baseline). If lower, stop and investigate.

- [ ] **Step 3: Verify `requests` is available locally for testing**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  .venv/bin/python -c "import requests; print(requests.__version__)" 2>&1
```
Expected: prints a version >= 2.32. If `ModuleNotFoundError`, the implementer can `pip install 'requests>=2.32'` into the venv now (the formal `pyproject.toml` change is in Task 2).

No commit at this step — sanity check only.

---

## Task 1: Add RestError + 3 subclasses

**Files:**
- Modify: `eden/errors.py` (append; do not replace existing content)
- Create: `tests/unit/test_errors_phase4b.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_errors_phase4b.py`:

```python
"""Verify Phase 4b additions to the exception hierarchy."""

from __future__ import annotations

import pytest

from eden.errors import (
    EdenError,
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
)

pytestmark = pytest.mark.unit


def test_rest_error_inherits_eden_error() -> None:
    assert issubclass(RestError, EdenError)


def test_rest_auth_error_inherits_rest_error() -> None:
    assert issubclass(RestAuthError, RestError)


def test_rest_not_found_inherits_rest_error() -> None:
    assert issubclass(RestNotFoundError, RestError)


def test_rest_rate_limited_inherits_rest_error() -> None:
    assert issubclass(RestRateLimited, RestError)


def test_rest_error_default_code_and_fields() -> None:
    err = RestError(message="boom", status=500, body="oops", url="https://x.test/y")
    assert err.code == "rest.error"
    assert err.message == "boom"
    assert err.hint is None
    assert err.cause is None
    assert err.status == 500
    assert err.body == "oops"
    assert err.url == "https://x.test/y"
    assert "[rest.error]" in str(err)


def test_rest_auth_error_default_code() -> None:
    err = RestAuthError(message="401 unauthorized", status=401, body="", url="https://x.test")
    assert err.code == "rest.auth"
    assert err.status == 401


def test_rest_not_found_default_code() -> None:
    err = RestNotFoundError(message="404", status=404, body="", url="https://x.test")
    assert err.code == "rest.not_found"


def test_rest_rate_limited_default_code() -> None:
    err = RestRateLimited(message="429", status=429, body="", url="https://x.test")
    assert err.code == "rest.rate_limited"


def test_rest_error_with_zero_status_for_connection_error() -> None:
    """status=0 indicates connection-level failure (no HTTP response at all)."""
    err = RestError(message="connection refused", status=0, url="https://x.test")
    assert err.status == 0


def test_rest_error_carries_cause() -> None:
    inner = ValueError("inner")
    err = RestError(message="x", cause=inner)
    assert err.cause is inner
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_errors_phase4b.py -v`
Expected: FAIL — `RestError` and subclasses not importable.

- [ ] **Step 3: Append the 4 new error classes to `eden/errors.py`**

Append (do NOT replace existing content) at the END of `eden/errors.py`:

```python


class RestError(EdenError):
    """Non-2xx response from a REST API. Carries status, body, url for debugging.

    `status=0` indicates a connection-level failure (no HTTP response).
    Catch this at the orchestrator boundary; never let it leak into user
    code as a generic `RequestException`.
    """

    def __init__(
        self,
        *,
        code: str = "rest.error",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        self.status = status
        self.body = body
        self.url = url
        super().__init__(_format(code, message, hint))


class RestAuthError(RestError):
    """401/403 — Bearer token rejected or insufficient permissions."""

    def __init__(
        self,
        *,
        code: str = "rest.auth",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(
            code=code, message=message, hint=hint, cause=cause,
            status=status, body=body, url=url,
        )


class RestNotFoundError(RestError):
    """404 — resource (sandbox/file) not found."""

    def __init__(
        self,
        *,
        code: str = "rest.not_found",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(
            code=code, message=message, hint=hint, cause=cause,
            status=status, body=body, url=url,
        )


class RestRateLimited(RestError):
    """429 — server-side rate-limit; retry already exhausted."""

    def __init__(
        self,
        *,
        code: str = "rest.rate_limited",
        message: str,
        hint: str | None = None,
        cause: Exception | None = None,
        status: int = 0,
        body: str = "",
        url: str = "",
    ) -> None:
        super().__init__(
            code=code, message=message, hint=hint, cause=cause,
            status=status, body=body, url=url,
        )
```

The `_format` helper and `EdenError` base class already exist in `eden/errors.py` from Phase 2 — reuse them by name. Each subclass has its OWN `__init__` (rather than relying on cooperative multiple-inheritance) so default `code` values work cleanly without `super().__init__(**kw)` type-issue gymnastics.

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_errors_phase4b.py -v`
Expected: PASS — 10 tests.

- [ ] **Step 5: Pre-existing errors tests still pass**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_errors.py tests/unit/test_errors_phase3a.py tests/unit/test_errors_phase3b.py -v`
Expected: PASS (no regression — Phase 2 + 3a + 3b errors untouched).

- [ ] **Step 6: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/errors.py tests/unit/test_errors_phase4b.py && \
.venv/bin/ruff format eden/errors.py tests/unit/test_errors_phase4b.py && \
.venv/bin/ruff format --check eden/errors.py tests/unit/test_errors_phase4b.py && \
.venv/bin/ruff check --fix eden/errors.py tests/unit/test_errors_phase4b.py && \
.venv/bin/ruff check eden/errors.py tests/unit/test_errors_phase4b.py
```
Expected: All clean.

- [ ] **Step 7: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/errors.py tests/unit/test_errors_phase4b.py && \
git commit -m "feat(errors): add RestError + RestAuthError/RestNotFoundError/RestRateLimited"
```

---

## Task 2: Add requests dep + RestClient

**Files:**
- Modify: `pyproject.toml` (add daytona + vercel optional deps)
- Create: `eden/providers/_impl/http_rest.py`
- Create: `tests/unit/test_http_rest.py`

- [ ] **Step 1: Add optional deps to `pyproject.toml`**

In `pyproject.toml`, find `[project.optional-dependencies]`. If the section doesn't exist yet, add it (likely below `[project.dependencies]`). If it exists, append:

```toml
[project.optional-dependencies]
# ... existing entries (e.g., dev = [...]) stay unchanged
daytona = ["requests >= 2.32"]
vercel = ["requests >= 2.32"]
```

(Pre-emptively listing `vercel` so Phase 4c doesn't have to re-touch this. Base install stays slim.)

- [ ] **Step 2: Install the new dep into the venv**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  .venv/bin/pip install -e '.[daytona,dev]' 2>&1 | tail -5
```
Expected: succeeds; `requests` and its deps installed.

If `'.[dev]'` doesn't exist as an extras spec, drop it: `.venv/bin/pip install -e '.[daytona]'`. Adjust based on what's in `pyproject.toml`.

- [ ] **Step 3: Verify install**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
  .venv/bin/python -c "import requests; print(requests.__version__)"
```
Expected: prints version >= 2.32.

- [ ] **Step 4: Write the failing test for RestClient**

Create `tests/unit/test_http_rest.py`:

```python
"""Verify RestClient — auth, retry, error mapping, JSON serialization."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from eden.errors import RestAuthError, RestError, RestNotFoundError, RestRateLimited
from eden.providers._impl.http_rest import RestClient

pytestmark = pytest.mark.unit


def _resp(*, status: int, json_body: dict[str, Any] | None = None, text: str = "") -> MagicMock:
    m = MagicMock(spec=requests.Response)
    m.status_code = status
    m.text = text or (str(json_body) if json_body else "")
    if json_body is not None:
        m.json.return_value = json_body
    else:
        m.json.side_effect = ValueError("no json")
    return m


def _client(headers: dict[str, str] | None = None, max_retries: int = 0) -> RestClient:
    return RestClient(
        base_url="https://api.test/",
        headers=headers or {"Authorization": "Bearer test-token"},
        timeout=5.0,
        max_retries=max_retries,
    )


def test_post_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kw: Any) -> Any:
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = kw.get("headers")
        captured["json"] = kw.get("json")
        return _resp(status=200, json_body={"id": "abc"})

    monkeypatch.setattr(client._session, "request", fake_request)
    out = client.post("/api/sandbox", json={"image": "ubuntu"})
    assert out == {"id": "abc"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.test/api/sandbox"
    assert captured["headers"] == {"Authorization": "Bearer test-token"}
    assert captured["json"] == {"image": "ubuntu"}


def test_get_threads_params(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kw: Any) -> Any:
        captured["params"] = kw.get("params")
        return _resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.get("/api/list", params={"limit": 10})
    assert captured["params"] == {"limit": 10}


def test_delete_does_not_expect_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: _resp(status=204, text=""),
    )
    # Should NOT raise even though there's no JSON body.
    client.delete("/api/sandbox/abc")


def test_url_joins_relative_paths() -> None:
    client = RestClient(
        base_url="https://api.test/",
        headers={},
    )
    assert client._url("/api/sandbox") == "https://api.test/api/sandbox"
    assert client._url("api/sandbox") == "https://api.test/api/sandbox"


def test_url_passes_absolute_through() -> None:
    client = RestClient(base_url="https://api.test", headers={})
    assert client._url("https://other.test/path") == "https://other.test/path"


def test_5xx_retried_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(max_retries=3)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    calls: list[int] = []

    def fake_request(method: str, url: str, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 3:
            return _resp(status=503, text="Service Unavailable")
        return _resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    out = client.post("/api/x", json={})
    assert out == {"ok": True}
    assert len(calls) == 3


def test_5xx_after_max_retries_raises_rest_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(max_retries=2)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: _resp(status=502, text="bad gateway"),
    )
    with pytest.raises(RestError) as excinfo:
        client.post("/api/x", json={})
    assert excinfo.value.status == 502
    assert "bad gateway" in excinfo.value.body


def test_429_retried_then_raises_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(max_retries=1)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: _resp(status=429, text="rate limit"),
    )
    with pytest.raises(RestRateLimited):
        client.post("/api/x", json={})


def test_401_raises_auth_error_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(max_retries=3)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        return _resp(status=401, text="bad token")

    monkeypatch.setattr(client._session, "request", fake_request)
    with pytest.raises(RestAuthError):
        client.post("/api/x", json={})
    assert len(calls) == 1  # NOT retried


def test_403_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: _resp(status=403, text="forbidden"),
    )
    with pytest.raises(RestAuthError):
        client.post("/api/x", json={})


def test_404_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: _resp(status=404, text="not found"),
    )
    with pytest.raises(RestNotFoundError):
        client.post("/api/x", json={})


def test_2xx_non_json_raises_rest_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: _resp(status=200, text="not json"),
    )
    with pytest.raises(RestError) as excinfo:
        client.post("/api/x", json={})
    assert "non-JSON" in excinfo.value.message


def test_request_exception_retried_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(max_retries=2)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        raise requests.ConnectionError("DNS fail")

    monkeypatch.setattr(client._session, "request", fake_request)
    with pytest.raises(RestError) as excinfo:
        client.post("/api/x", json={})
    assert excinfo.value.status == 0
    assert len(calls) == 3  # initial + 2 retries
```

- [ ] **Step 5: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_http_rest.py -v`
Expected: FAIL — `eden.providers._impl.http_rest` not found.

- [ ] **Step 6: Implement RestClient**

Create `eden/providers/_impl/http_rest.py`:

```python
"""Shared REST client for cloud sandbox providers."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import requests

from eden.errors import (
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
)

_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BACKOFFS = (0.5, 1.0, 2.0)


@dataclass
class RestClient:
    """Sync REST client with auth-header injection + retry-on-5xx/429.

    Caller supplies `headers` at construction (e.g.,
    `{"Authorization": f"Bearer {key}"}`). Errors map to typed exceptions:
    401/403 → RestAuthError, 404 → RestNotFoundError,
    429 → RestRateLimited (after retries exhausted), other 4xx/5xx → RestError.
    """

    base_url: str
    headers: Mapping[str, str]
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = _DEFAULT_MAX_RETRIES
    _session: requests.Session = field(default_factory=requests.Session)

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", path, json=json)

    def delete(self, path: str) -> None:
        self._request("DELETE", path, expect_json=False)

    def close(self) -> None:
        self._session.close()

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        url = self._url(path)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=dict(self.headers),
                    params=dict(params) if params else None,
                    json=dict(json) if json else None,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(_RETRY_BACKOFFS[min(attempt, len(_RETRY_BACKOFFS) - 1)])
                    continue
                raise RestError(
                    message=f"connection error to {url}: {exc}",
                    cause=exc,
                    url=url,
                ) from exc

            if 200 <= resp.status_code < 300:
                if not expect_json:
                    return {}
                try:
                    parsed: dict[str, Any] = resp.json()
                    return parsed
                except ValueError as exc:
                    raise RestError(
                        message=f"non-JSON response from {url}: {resp.text[:200]}",
                        cause=exc,
                        status=resp.status_code,
                        body=resp.text,
                        url=url,
                    ) from exc

            if resp.status_code in (500, 502, 503, 504, 429) and attempt < self.max_retries:
                time.sleep(_RETRY_BACKOFFS[min(attempt, len(_RETRY_BACKOFFS) - 1)])
                continue

            self._raise_status(resp, url)

        # Unreachable in practice (loop either returns or raises),
        # but mypy needs a fallthrough.
        raise RestError(message="exhausted retries", cause=last_exc, url=url)

    @staticmethod
    def _raise_status(resp: requests.Response, url: str) -> None:
        body = resp.text
        status = resp.status_code
        msg = f"HTTP {status} from {url}: {body[:200]}"
        if status in (401, 403):
            raise RestAuthError(message=msg, status=status, body=body, url=url)
        if status == 404:
            raise RestNotFoundError(message=msg, status=status, body=body, url=url)
        if status == 429:
            raise RestRateLimited(message=msg, status=status, body=body, url=url)
        raise RestError(message=msg, status=status, body=body, url=url)


__all__ = ["RestClient"]
```

- [ ] **Step 7: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_http_rest.py -v`
Expected: PASS — 13 tests.

- [ ] **Step 8: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/providers/_impl/http_rest.py tests/unit/test_http_rest.py && \
.venv/bin/ruff format eden/providers/_impl/http_rest.py tests/unit/test_http_rest.py && \
.venv/bin/ruff format --check eden/providers/_impl/http_rest.py tests/unit/test_http_rest.py && \
.venv/bin/ruff check --fix eden/providers/_impl/http_rest.py tests/unit/test_http_rest.py && \
.venv/bin/ruff check eden/providers/_impl/http_rest.py tests/unit/test_http_rest.py
```
Expected: All clean.

- [ ] **Step 9: Commit (stage by name — only 3 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add pyproject.toml eden/providers/_impl/http_rest.py tests/unit/test_http_rest.py && \
git commit -m "feat(http_rest): add RestClient with retry + auth + error mapping"
```

DO NOT use `git add eden/providers/_impl`.

---

## Task 3: Daytona provider — factory + handle (no finalize yet)

**Files:**
- Create: `eden/sandboxes/daytona/__init__.py`
- Create: `tests/unit/test_daytona_provider.py`

This task lands the factory, `_DaytonaHandle` with `exec`/`copy_file_in`/`copy_file_out`/`close` (no `finalize`), the `_upload_tree` helper, and the `_snapshot_remote` helper. Task 4 adds `finalize` (which uses `_snapshot_remote`).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_daytona_provider.py`:

```python
"""Verify daytona provider factory + _DaytonaHandle methods (no finalize yet)."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import BranchStrategy, CreateOptions, ExecResult
from eden.sandboxes.daytona import provider as daytona_provider
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable

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


def _mock_client(post_returns: dict | list[dict] | None = None) -> MagicMock:
    """Build a MagicMock(spec=RestClient) whose post() returns canned data."""
    client = MagicMock(spec=RestClient)
    if isinstance(post_returns, list):
        client.post.side_effect = post_returns
    elif post_returns is not None:
        client.post.return_value = post_returns
    return client


def test_provider_kind_and_name() -> None:
    p = daytona_provider(api_key="test-key")
    assert p.kind == "isolated"
    assert p.name == "daytona"


def test_provider_supports_default_strategies() -> None:
    p = daytona_provider(api_key="test-key")
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_raises_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    p = daytona_provider()  # no api_key arg, no env var
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == "daytona"


def test_create_reads_api_key_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("DAYTONA_API_KEY", "env-key")
    captured_headers: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_headers.update(kw["headers"])  # type: ignore[arg-type]
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider()
    p.create(_opts(tmp_path))
    assert captured_headers["Authorization"] == "Bearer env-key"


def test_create_threads_organization_id_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    captured_headers: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_headers.update(kw["headers"])  # type: ignore[arg-type]
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider(api_key="k", organization_id="org-7")
    p.create(_opts(tmp_path))
    assert captured_headers["X-Daytona-Organization-ID"] == "org-7"


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

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider(api_key="k", base_url="https://daytona.local")
    p.create(_opts(tmp_path))
    assert captured_url["base_url"] == "https://daytona.local"


def test_create_posts_sandbox_with_image_and_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    captured_payload: dict[str, object] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            self.post = MagicMock(side_effect=self._post)
            self.close = MagicMock()
            self.delete = MagicMock()

        def _post(self, path: str, *, json: object) -> dict[str, str]:
            if path == "/api/sandbox":
                captured_payload["payload"] = json  # type: ignore[assignment]
                return {"id": "sb-9"}
            # Any subsequent _upload_tree / _snapshot_remote calls return success.
            return {"stdout": "", "stderr": "", "exit_code": 0}

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider(api_key="k", image="ubuntu:22.04", env={"FOO": "bar"})
    p.create(_opts(tmp_path))
    payload = captured_payload["payload"]
    assert isinstance(payload, dict)
    assert payload["image"] == "ubuntu:22.04"
    assert payload["env"] == {"FOO": "bar"}
    assert payload["name"] == "test"  # name_hint


def test_handle_exec_returns_exec_result() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = _mock_client(
        {"stdout": "hello\n", "stderr": "", "exit_code": 0},
    )
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    result = handle.exec("echo hello")
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert args[0] == "/toolbox/sb-1/process/execute"
    assert kwargs["json"]["command"] == "echo hello"


def test_handle_exec_returns_neg_one_on_rest_failure() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    result = handle.exec("anything")
    assert result.exit_code == -1
    assert "network down" in result.stderr


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.copy_file_in(src, Path("/workspace/dst.bin"))
    args, kwargs = client.post.call_args
    cmd = kwargs["json"]["command"]
    expected_b64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
    assert expected_b64 in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    client = _mock_client({"stdout": "", "stderr": "boom", "exit_code": 1})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    with pytest.raises(ExecFailed):
        handle.copy_file_in(src, Path("/workspace/dst"))


def test_handle_close_deletes_sandbox() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.close()
    client.delete.assert_called_once_with("/api/sandbox/sb-1")
    client.close.assert_called_once()


def test_handle_close_idempotent_on_not_found() -> None:
    from eden.errors import RestNotFoundError
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.delete.side_effect = RestNotFoundError(
        message="404", status=404, url="https://x/api/sandbox/sb-1",
    )
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.close()  # must not raise
    client.close.assert_called_once()
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_daytona_provider.py -v`
Expected: FAIL — `eden.sandboxes.daytona` not found.

- [ ] **Step 3: Implement the daytona provider (without finalize)**

Create `eden/sandboxes/daytona/__init__.py`:

```python
"""Daytona cloud sandbox provider: REST-driven isolated/finalizing sandbox.

Phase 4b: factory + create flow + handle methods (exec, copy_file_in/out, close).
Phase 4b Task 4 adds: finalize (using patch_sync.diff/apply over snapshot dicts
produced via _snapshot_remote — same shape as patch_sync.snapshot).
"""

from __future__ import annotations

import base64
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._helpers import make_isolated_provider
from eden.providers._impl.http_rest import RestClient
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.errors import RestNotFoundError
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable

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
            _upload_tree(client, sandbox_id, src=opts.worktree_path, dst=_SANDBOX_WORKDIR)
            baseline = _snapshot_remote(client, sandbox_id, root=_SANDBOX_WORKDIR)
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
        # Stub for Task 4. Returning applied=False so any caller calling
        # finalize() before Task 4 ships sees a clean "no-op" rather than
        # a confusing missing-method error.
        return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)

    def close(self) -> None:
        try:
            self.client.delete(f"/api/sandbox/{self.sandbox_id}")
        except RestNotFoundError:
            pass  # already gone — idempotent close
        except Exception:
            pass  # don't propagate teardown errors (matches docker/podman)
        finally:
            self.client.close()


def _upload_tree(client: RestClient, sandbox_id: str, *, src: Path, dst: Path) -> None:
    """Upload every file under `src` (host) to `dst` (sandbox), preserving structure."""
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
            f"/toolbox/{sandbox_id}/process/execute",
            json={"command": cmd},
        )
        if int(result.get("exit_code", result.get("exitCode", 0))) != 0:
            raise RuntimeError(
                f"upload of {rel} failed: {result.get('stderr', '')}"
            )


def _snapshot_remote(client: RestClient, sandbox_id: str, *, root: Path) -> dict[Path, str]:
    """REST-shell `find ... | xargs sha256sum` and parse stdout into the
    `dict[Path, hex]` shape produced by `patch_sync.snapshot()` locally.
    """
    cmd = (
        f"cd {root.as_posix()} && "
        "find . -type f "
        "-not -path './.git/*' -not -path './.eden/*' "
        "-print0 | xargs -0 sha256sum 2>/dev/null"
    )
    response = client.post(
        f"/toolbox/{sandbox_id}/process/execute",
        json={"command": cmd},
    )
    out: dict[Path, str] = {}
    for line in str(response.get("stdout", "")).splitlines():
        if not line.strip():
            continue
        # `sha256sum` format: "<hex>  ./relative/path"
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

Note: `finalize` is a stub returning `FinalizeResult(applied=False, ...)` for now. Task 4 replaces the stub with the real implementation. This keeps the dataclass complete (satisfies `IsolatedSandboxHandle` Protocol) and lets the orchestrator's existing `hasattr(handle, "finalize")` duck-check work end-to-end through Task 3.

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_daytona_provider.py -v`
Expected: PASS — 13 tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/sandboxes/daytona tests/unit/test_daytona_provider.py && \
.venv/bin/ruff format eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
.venv/bin/ruff format --check eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
.venv/bin/ruff check --fix eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
.venv/bin/ruff check eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
git commit -m "feat(daytona): add factory + _DaytonaHandle (exec/copy/close); finalize stub"
```

DO NOT use `git add eden/sandboxes/daytona`.

---

## Task 4: Daytona finalize

**Files:**
- Modify: `eden/sandboxes/daytona/__init__.py` (replace the `finalize` stub)
- Modify: `tests/unit/test_daytona_provider.py` (append finalize tests)

- [ ] **Step 1: Append finalize tests**

Append to the END of `tests/unit/test_daytona_provider.py`:

```python


def test_finalize_no_changes_returns_applied_true(tmp_path: Path) -> None:
    """When sandbox snapshot equals baseline, finalize is a no-op success."""
    from eden.sandboxes.daytona import _DaytonaHandle

    # The shell command in _snapshot_remote returns empty stdout when no files.
    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is True
    assert fr.files_changed == ()
    assert fr.patch_size_bytes == 0


def test_finalize_pulls_added_files_to_target(tmp_path: Path) -> None:
    """Sandbox has a file not in baseline — finalize REST-pulls it to target."""
    from eden.sandboxes.daytona import _DaytonaHandle

    target = tmp_path / "target"
    target.mkdir()

    # Mock REST responses:
    # - First post (snapshot): stdout lists one file with its sha256.
    # - Second post (copy_file_out via exec): base64 of the file's contents.
    base64_payload = "aGVsbG8="  # "hello"
    client = MagicMock(spec=RestClient)
    client.post.side_effect = [
        {"stdout": "abc123  ./new.txt\n", "stderr": "", "exit_code": 0},
        {"stdout": base64_payload, "stderr": "", "exit_code": 0},
    ]
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={},  # nothing in baseline → new.txt counts as added
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert (target / "new.txt").read_bytes() == b"hello"
    assert Path("new.txt") in fr.files_changed


def test_finalize_propagates_deletes(tmp_path: Path) -> None:
    """Baseline has a file; sandbox snapshot doesn't — finalize removes it from target."""
    from eden.sandboxes.daytona import _DaytonaHandle

    target = tmp_path / "target"
    target.mkdir()
    (target / "to_delete.txt").write_text("gone soon", encoding="utf-8")

    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={Path("to_delete.txt"): "old-hash"},
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert not (target / "to_delete.txt").exists()


def test_finalize_returns_not_applied_on_snapshot_failure(tmp_path: Path) -> None:
    """REST failure during finalize snapshot → soft-fail."""
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is False
```

- [ ] **Step 2: Run tests to verify they fail (because finalize is stubbed)**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_daytona_provider.py -v 2>&1 | tail -10`
Expected: FAIL — the new tests want real finalize behavior; the stub returns `applied=False` for everything.

- [ ] **Step 3: Replace the finalize stub with the real implementation**

In `eden/sandboxes/daytona/__init__.py`, locate the `finalize` method on `_DaytonaHandle`:

```python
    def finalize(self, target: Path) -> FinalizeResult:
        # Stub for Task 4. Returning applied=False so any caller calling
        # finalize() before Task 4 ships sees a clean "no-op" rather than
        # a confusing missing-method error.
        return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)
```

Replace the entire method body with:

```python
    def finalize(self, target: Path) -> FinalizeResult:
        try:
            after = _snapshot_remote(self.client, self.sandbox_id, root=self.worktree_path)
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

Also add the new imports at the top of `eden/sandboxes/daytona/__init__.py` (after the existing imports, alphabetically):

```python
import tempfile
```

And:

```python
from eden.providers._impl import patch_sync
```

(`patch_sync` was added in Phase 4a; it lives at `eden/providers/_impl/patch_sync.py`.)

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/unit/test_daytona_provider.py -v`
Expected: PASS — 17 tests (13 from Task 3 + 4 new).

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden/sandboxes/daytona tests/unit/test_daytona_provider.py && \
.venv/bin/ruff format eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
.venv/bin/ruff format --check eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
.venv/bin/ruff check --fix eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
.venv/bin/ruff check eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/sandboxes/daytona/__init__.py tests/unit/test_daytona_provider.py && \
git commit -m "feat(daytona): implement finalize via patch_sync.diff/apply over remote snapshot"
```

---

## Task 5: Top-level public re-exports

**Files:**
- Modify: `eden/__init__.py`

- [ ] **Step 1: Add the 4 REST error classes to top-level imports**

Edit `eden/__init__.py`. Find the existing `from eden.errors import (...)` block. Add `RestAuthError`, `RestError`, `RestNotFoundError`, `RestRateLimited` (alphabetical position — likely between `PromptError` and `SessionCaptureFailed`):

```python
from eden.errors import (
    ConfigError,
    CwdError,
    EdenError,
    EdenTimeoutError,
    EnvMergeError,
    HookError,
    HookFailed,
    HookTimeout,
    IdleTimeout,
    InvalidOptions,
    PromptError,
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
    SessionCaptureFailed,
    StepTimeout,
)
```

- [ ] **Step 2: Add 4 names to `__all__`**

Add `"RestAuthError"`, `"RestError"`, `"RestNotFoundError"`, `"RestRateLimited"` to `__all__`. Use ruff RUF022 with `--unsafe-fixes` to sort if needed (Phase 3a/3b/4a accepted this fix).

- [ ] **Step 3: Verify imports**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/python -c "import eden; assert eden.RestError is not None; assert eden.RestAuthError is not None; assert eden.RestNotFoundError is not None; assert eden.RestRateLimited is not None; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Run full unit + e2e suite (regression check)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/pytest -m "unit or e2e" --no-cov -q
```
Expected: All tests pass. Total: 343 (Phase 4a baseline) + new tests through Task 4. Specifically:
- T1: +10
- T2: +13
- T3: +13
- T4: +4
- Grand total: 343 + 40 = **383 tests** passing.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy eden && \
.venv/bin/ruff format eden/__init__.py && \
.venv/bin/ruff format --check eden/__init__.py && \
.venv/bin/ruff check --fix eden/__init__.py && \
.venv/bin/ruff check eden/__init__.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 1 file)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add eden/__init__.py && \
git commit -m "feat(eden): re-export RestError + RestAuthError/RestNotFoundError/RestRateLimited"
```

---

## Task 6: Fake-daytona test infrastructure

**Files:**
- Create: `tests/_fake_daytona/__init__.py`

(No standalone tests; the shim is exercised by Task 7's e2e tests.)

- [ ] **Step 1: Implement the fake server**

Create `tests/_fake_daytona/__init__.py`:

```python
"""Fake Daytona REST server for e2e tests.

Spins a ThreadingHTTPServer on localhost:<random-port> registering the three
endpoints _DaytonaHandle uses. Sandbox state lives in a tmp directory; commands
run via subprocess.run against that dir, so the e2e test exercises the real
snapshot/diff/apply flow without an actual Daytona account.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


def start_fake_daytona(
    *,
    monkeypatch: pytest.MonkeyPatch,
    state_dir: Path,
) -> str:
    """Start a fake-daytona ThreadingHTTPServer on a random port.

    Routes:
      POST /api/sandbox                   → create state_dir/<id>/, return {"id": <id>}
      POST /toolbox/<id>/process/execute  → subprocess.run(cmd, cwd=state_dir/<id>)
      DELETE /api/sandbox/<id>            → shutil.rmtree(state_dir/<id>)

    Sets DAYTONA_API_KEY=test-token and DAYTONA_API_URL=<base_url> via
    monkeypatch.setenv. Returns the base_url string.

    Server runs on a daemon thread; pytest fixture finalizer should call
    server.shutdown() to clean up.
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

        def do_POST(self) -> None:  # noqa: N802 (HTTP-spec name)
            payload = self._read_json()
            if self.path == "/api/sandbox":
                sb_id = uuid.uuid4().hex[:12]
                sb_root = state_dir / sb_id
                sb_root.mkdir(parents=True, exist_ok=True)
                # Create the workspace dir up-front; commands run in there.
                (sb_root / "workspace").mkdir(parents=True, exist_ok=True)
                sandboxes[sb_id] = sb_root
                self._send_json(200, {"id": sb_id})
                return
            if self.path.startswith("/toolbox/") and self.path.endswith("/process/execute"):
                sb_id = self.path.split("/")[2]
                sb_root = sandboxes.get(sb_id)
                if sb_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                cmd = str(payload.get("command", ""))
                # Sandbox-side cwd is /workspace. Map to host: state_dir/<id>/workspace.
                # If the command has `cd /workspace && ...`, that "/workspace" is a
                # path the shell on the host won't have. We rewrite by changing the
                # subprocess.run cwd to <sb_root>/workspace and stripping "/workspace"
                # path prefixes in the command. To keep this simple and robust,
                # we just chdir into <sb_root> and let the script use relative paths.
                try:
                    rewritten = cmd.replace("/workspace", str(sb_root / "workspace"))
                    proc = subprocess.run(
                        ["/bin/sh", "-c", rewritten],
                        cwd=str(sb_root),
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
            self._send_json(404, {"error": f"no such route: {self.path}"})

        def do_DELETE(self) -> None:  # noqa: N802
            if self.path.startswith("/api/sandbox/"):
                sb_id = self.path.rsplit("/", 1)[-1]
                sb_root = sandboxes.pop(sb_id, None)
                if sb_root is None:
                    self._send_json(404, {"error": "no such sandbox"})
                    return
                shutil.rmtree(sb_root, ignore_errors=True)
                self.send_response(204)
                self.end_headers()
                return
            self._send_json(404, {"error": f"no such route: {self.path}"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("DAYTONA_API_KEY", "test-token")
    monkeypatch.setenv("DAYTONA_API_URL", base_url)

    # Register a finalizer to shut down the server when the test ends.
    def _stop() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    # pytest's monkeypatch doesn't have a teardown-callback API; the server is
    # daemon-threaded, so it dies with the test process. For deterministic
    # cleanup across tests, callers should treat this as a function-scoped
    # fixture and call `_stop()` themselves if they want immediate cleanup.
    setattr(server, "_eden_stop", _stop)
    return base_url


__all__ = ["start_fake_daytona"]
```

- [ ] **Step 2: Verify imports**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/python -c "from tests._fake_daytona import start_fake_daytona; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy tests/_fake_daytona && \
.venv/bin/ruff format tests/_fake_daytona/__init__.py && \
.venv/bin/ruff format --check tests/_fake_daytona/__init__.py && \
.venv/bin/ruff check --fix tests/_fake_daytona/__init__.py && \
.venv/bin/ruff check tests/_fake_daytona/__init__.py
```
Expected: All clean.

- [ ] **Step 4: Commit (stage by name — only 1 file)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add tests/_fake_daytona/__init__.py && \
git commit -m "test: add fake-daytona ThreadingHTTPServer for phase 4b e2e tests"
```

DO NOT use `git add tests/_fake_daytona`.

---

## Task 7: E2E smoke test for daytona

**Files:**
- Create: `tests/e2e/test_daytona_smoke.py`

- [ ] **Step 1: Write the e2e test**

Create `tests/e2e/test_daytona_smoke.py`:

```python
"""Smoke E2E: simulated_agent + daytona provider (fake server) + finalize."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes import daytona as daytona_sandbox
from tests._fake_daytona import start_fake_daytona

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-daytona shell-execs use /bin/sh, not available on Windows",
)
def test_daytona_finalize_writes_sandbox_changes_to_host(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: a sandbox hook writes a file inside the fake-daytona sandbox;
    finalize() REST-pulls it via copy_file_out and patch_sync.apply lands it
    on the host worktree, and the orchestrator emits `[eden] finalized:`."""
    state_dir = tmp_path / "fake-daytona-state"
    start_fake_daytona(monkeypatch=monkeypatch, state_dir=state_dir)

    sandbox_hook = eden.Hook(
        cmd='echo "hello-from-cloud" > new_file.txt',
    )
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="working\n<promise>COMPLETE</promise>\n"),
        sandbox=daytona_sandbox.provider(),  # api_key from env (set by fake)
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
    assert target_file.read_text(encoding="utf-8").strip() == "hello-from-cloud"

    assert result.log_file_path is not None
    log_body = result.log_file_path.read_text(encoding="utf-8")
    assert "[eden] finalized:" in log_body
    assert "applied=True" in log_body


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-daytona shell-execs use /bin/sh, not available on Windows",
)
def test_daytona_finalize_propagates_deletes(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a file inside the fake-daytona sandbox propagates to the host."""
    assert (e2e_git_repo / "README.md").exists()
    state_dir = tmp_path / "fake-daytona-state"
    start_fake_daytona(monkeypatch=monkeypatch, state_dir=state_dir)

    sandbox_hook = eden.Hook(cmd="rm README.md")
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=daytona_sandbox.provider(),
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

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest tests/e2e/test_daytona_smoke.py -v`
Expected: PASS — 2 tests on macOS/Linux. (Skipped on Windows.)

If a test fails, the most likely causes:
1. The fake server's path-rewriting (`replace("/workspace", str(sb_root / "workspace"))`) is too naive — the sandbox-hook's `echo > new_file.txt` runs in `cwd=sb_root`, but `_upload_tree`/`_snapshot_remote` and `copy_file_out` use sandbox path `/workspace/...` which gets rewritten. Verify by inserting `print(rewritten)` in the fake's `do_POST`.
2. The orchestrator's `agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None` correctly produces `None` for daytona because `/workspace` doesn't exist on the host (verify with `print(handle.worktree_path.exists())` in `_run_loop`).
3. The fake server's `_snapshot_remote` shell command (`find ... | xargs sha256sum`) requires `sha256sum` and `find` to be available. macOS has them; Linux does too. If not, `which sha256sum` to confirm.

If the test asserts the fake server's port is bound but the real `eden.run(...)` connects to the wrong URL, the issue is `monkeypatch.setenv` not taking effect — verify by inserting `print(os.environ.get("DAYTONA_API_URL"))` in the test.

- [ ] **Step 3: Run combined unit + e2e (regression check)**

`cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && .venv/bin/pytest -m "unit or e2e" --no-cov -q`
Expected: All tests pass. Total: 383 (after T5) + 2 = **385 tests**.

- [ ] **Step 4: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
.venv/bin/mypy tests/e2e/test_daytona_smoke.py && \
.venv/bin/ruff format tests/e2e/test_daytona_smoke.py && \
.venv/bin/ruff format --check tests/e2e/test_daytona_smoke.py && \
.venv/bin/ruff check --fix tests/e2e/test_daytona_smoke.py && \
.venv/bin/ruff check tests/e2e/test_daytona_smoke.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add tests/e2e/test_daytona_smoke.py && \
git commit -m "test(e2e): add daytona smoke run via fake-daytona server"
```

---

## Task 8: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump status line**

Edit `README.md:5` (the `> **Status:** ...` blockquote). Replace the existing line with:

```markdown
> **Status:** Pre-alpha. Phases 1–4b complete: package skeleton, provider Protocols, worktree manager, `no_sandbox`/`docker`/`podman` bind-mount providers, local `isolated` patch-sync provider, `daytona` cloud provider, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent` and `claude_code` agents, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, Claude Code session JSONL capture, and post-iteration `finalize()` for isolated/cloud handles. Other agents (5), CLI scaffolder (6), and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/dotbrains/eden && \
git add README.md && \
git commit -m "docs: bump README status to phase 4b complete"
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
Expected: every command Success / PASS. Coverage stays ≥ 70%.

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

Then check GitHub CI — all 9 matrix jobs (Linux/macOS/Windows × py3.11/3.12/3.13) green for unit+e2e. The e2e daytona tests skip on Windows; unit tests run on all platforms.

- [ ] **Step 3: Tag the phase**

Wait for CI green before tagging.

```bash
git tag -a phase-4b -m "Phase 4b: daytona cloud sandbox provider + RestClient"
git push origin phase-4b
```

---

## Notes for the implementer

- **No new threads in production code.** `RestClient` is sync; `_DaytonaHandle.exec` blocks the calling thread for the duration of the REST call (subject to `timeout`). The fake-daytona server is daemon-threaded (test infra only).
- **`ProviderUnavailable` at create-time, not factory-time.** The factory is cheap and side-effect-free; env-var resolution happens inside `_create()`. This lets users define the provider at module scope without secrets-at-import-time concerns.
- **Soft failure on finalize errors.** Same pattern as Phase 3b session capture and Phase 4a isolated finalize — `FinalizeResult(applied=False, ...)` returned, orchestrator logs `[eden] finalize failed: ...`, run completes.
- **REST infrastructure failure → exception; shell exit non-zero → ExecResult.** The `_DaytonaHandle.exec` method MUST return `ExecResult(exit_code=N)` for shell failures (matching docker/podman) and ONLY raise for REST infrastructure issues. Don't conflate these — the orchestrator's existing handling depends on the distinction.
- **Base64-via-exec for file I/O.** Always works on Daytona's documented surface. If the implementer discovers a clean file API in Daytona docs during execution, swap `copy_file_in/out` to use it directly (the public method signatures stay the same). Document any such change in the commit message.
- **Mount handling.** `_DaytonaHandle` IGNORES `opts.mounts` — same as the local `isolated` provider. Documented limitation; users who need extra files must `copy_file_in` them after creation.
- **`_AgentRunner.cwd` for daytona.** `handle.worktree_path == /workspace`; on the host, `Path("/workspace").exists()` is `False`, so the orchestrator's existing `agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None` correctly falls back to `None`. No new orchestrator code needed.
- **Coverage gate stays at 70%.** Phase 4a baseline 94.21%; 4b adds heavily-tested code so total stays well above gate.
- **Frequent commits.** Each task lands one commit. Atomicity is preserved per-task (T3 lands a stub finalize so the file is import-clean; T4 fills in real finalize behavior).

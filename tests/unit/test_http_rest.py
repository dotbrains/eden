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

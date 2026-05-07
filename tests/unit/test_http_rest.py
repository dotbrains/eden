"""Verify RestClient — auth, retry, error mapping, JSON serialization."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from eden.errors import RestAuthError, RestError, RestNotFoundError, RestRateLimited
from eden.providers._impl.http_rest import RestClient

pytestmark = pytest.mark.unit


def _resp(
    *,
    status: int,
    json_body: dict[str, Any] | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    m = MagicMock(spec=requests.Response)
    m.status_code = status
    m.text = text or (str(json_body) if json_body else "")
    m.headers = dict(headers) if headers is not None else {}
    if json_body is not None:
        m.json.return_value = json_body
    else:
        m.json.side_effect = ValueError("no json")
    return m


def _client(
    headers: dict[str, str] | None = None,
    max_retries: int = 0,
    *,
    sleeps: list[float] | None = None,
    rand_value: float = 1.0,
    max_retry_after_seconds: float = 60.0,
) -> RestClient:
    """Build a RestClient with deterministic sleep+jitter for tests.

    ``sleeps`` (when provided) collects the seconds passed to each sleep call
    so tests can assert on backoff sequences without timing.
    """

    def _record_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return RestClient(
        base_url="https://api.test/",
        headers=headers or {"Authorization": "Bearer test-token"},
        timeout=5.0,
        max_retries=max_retries,
        max_retry_after_seconds=max_retry_after_seconds,
        sleep=_record_sleep,
        rand=lambda: rand_value,
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


# Tests for the smart-retry behaviour from ADR 0011-onwards.


def test_retry_after_seconds_form_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    client = _client(max_retries=2, sleeps=sleeps)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 3:
            return _resp(status=429, text="slow down", headers={"Retry-After": "5"})
        return _resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    out = client.post("/api/x", json={})
    assert out == {"ok": True}
    # Two retries → two sleeps, each honouring Retry-After=5s exactly.
    assert sleeps == [5.0, 5.0]


def test_retry_after_http_date_form_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry-After can be an HTTP-date; eden parses it relative to now."""
    from datetime import UTC, datetime, timedelta

    sleeps: list[float] = []
    client = _client(max_retries=1, sleeps=sleeps)
    future = datetime.now(UTC) + timedelta(seconds=10)
    # RFC 9110 §10.2.3 / RFC 5322 date format
    http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            return _resp(status=429, headers={"Retry-After": http_date})
        return _resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.post("/api/x", json={})
    assert len(sleeps) == 1
    # ~10s give-or-take a second of test-execution slop.
    assert 8.0 <= sleeps[0] <= 12.0


def test_retry_after_exceeding_cap_raises_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server asking for longer than max_retry_after_seconds short-circuits."""
    sleeps: list[float] = []
    client = _client(
        max_retries=3,
        sleeps=sleeps,
        max_retry_after_seconds=10.0,
    )

    def fake_request(*a: Any, **kw: Any) -> Any:
        return _resp(status=429, headers={"Retry-After": "300"})  # 5 minutes

    monkeypatch.setattr(client._session, "request", fake_request)
    with pytest.raises(RestRateLimited) as excinfo:
        client.post("/api/x", json={})
    assert "exceeds max_retry_after_seconds" in excinfo.value.message
    assert sleeps == []  # no sleep — short-circuited


def test_429_without_retry_after_falls_back_to_jitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing/unparseable Retry-After uses the same backoff as 5xx."""
    sleeps: list[float] = []
    client = _client(max_retries=2, sleeps=sleeps, rand_value=1.0)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 3:
            return _resp(status=429, headers={})  # no Retry-After
        return _resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.post("/api/x", json={})
    # rand_value=1.0 + base=0.5: attempt 0 -> 0.5, attempt 1 -> 1.0.
    assert sleeps == [0.5, 1.0]


def test_5xx_uses_jittered_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    client = _client(max_retries=3, sleeps=sleeps, rand_value=0.5)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 4:
            return _resp(status=503, text="overloaded")
        return _resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.post("/api/x", json={})
    # rand=0.5: 0.5 * 0.5 * 2^attempt → 0.25, 0.5, 1.0
    assert sleeps == pytest.approx([0.25, 0.5, 1.0])


def test_jitter_caps_at_30_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backoff schedule never exceeds the cap regardless of attempt index."""
    from eden.providers._impl.http_rest import _full_jitter_backoff

    # rand=1.0 produces the upper end of the jitter window.
    for attempt in range(0, 50):
        delay = _full_jitter_backoff(attempt, rand=lambda: 1.0)
        assert delay <= 30.0


def test_parse_retry_after_negative_clamped_to_zero() -> None:
    """A past HTTP-date (or negative seconds) returns 0, not a negative wait."""
    from datetime import UTC, datetime, timedelta

    from eden.providers._impl.http_rest import _parse_retry_after

    past = datetime.now(UTC) - timedelta(seconds=120)
    http_date = past.strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert _parse_retry_after(http_date) == 0.0
    assert _parse_retry_after("-5") == 0.0


def test_parse_retry_after_unparseable_returns_none() -> None:
    from eden.providers._impl.http_rest import _parse_retry_after

    assert _parse_retry_after(None) is None
    assert _parse_retry_after("") is None
    assert _parse_retry_after("not a number or date") is None

"""Verify RestClient retry behavior and error mapping."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from eden.errors import RestAuthError, RestError, RestNotFoundError, RestRateLimited
from tests.unit.providers_impl.http_rest_helpers import client as make_client
from tests.unit.providers_impl.http_rest_helpers import resp

pytestmark = pytest.mark.unit


def test_5xx_retried_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(max_retries=3)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    calls: list[int] = []

    def fake_request(method: str, url: str, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 3:
            return resp(status=503, text="Service Unavailable")
        return resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    out = client.post("/api/x", json={})
    assert out == {"ok": True}
    assert len(calls) == 3


def test_5xx_after_max_retries_raises_rest_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(max_retries=2)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: resp(status=502, text="bad gateway"),
    )
    with pytest.raises(RestError) as excinfo:
        client.post("/api/x", json={})
    assert excinfo.value.status == 502
    assert "bad gateway" in excinfo.value.body


def test_429_retried_then_raises_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(max_retries=1)
    monkeypatch.setattr("eden.providers._impl.http_rest.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: resp(status=429, text="rate limit"),
    )
    with pytest.raises(RestRateLimited):
        client.post("/api/x", json={})


def test_401_raises_auth_error_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(max_retries=3)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        return resp(status=401, text="bad token")

    monkeypatch.setattr(client._session, "request", fake_request)
    with pytest.raises(RestAuthError):
        client.post("/api/x", json={})
    assert len(calls) == 1  # NOT retried


def test_403_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: resp(status=403, text="forbidden"),
    )
    with pytest.raises(RestAuthError):
        client.post("/api/x", json={})


def test_404_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: resp(status=404, text="not found"),
    )
    with pytest.raises(RestNotFoundError):
        client.post("/api/x", json={})


def test_2xx_non_json_raises_rest_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: resp(status=200, text="not json"),
    )
    with pytest.raises(RestError) as excinfo:
        client.post("/api/x", json={})
    assert "non-JSON" in excinfo.value.message


def test_request_exception_retried_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(max_retries=2)
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

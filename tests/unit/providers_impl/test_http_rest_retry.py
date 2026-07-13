"""Verify RestClient retry and backoff behaviour."""

from __future__ import annotations

from typing import Any

import pytest

from eden.errors import RestRateLimited
from tests.unit.providers_impl.http_rest_helpers import client as make_client
from tests.unit.providers_impl.http_rest_helpers import resp

pytestmark = pytest.mark.unit


def test_retry_after_seconds_form_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    client = make_client(max_retries=2, sleeps=sleeps)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 3:
            return resp(status=429, text="slow down", headers={"Retry-After": "5"})
        return resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    out = client.post("/api/x", json={})
    assert out == {"ok": True}
    # Two retries: two sleeps, each honouring Retry-After=5s exactly.
    assert sleeps == [5.0, 5.0]


def test_retry_after_http_date_form_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry-After can be an HTTP-date; eden parses it relative to now."""
    from datetime import UTC, datetime, timedelta

    sleeps: list[float] = []
    client = make_client(max_retries=1, sleeps=sleeps)
    future = datetime.now(UTC) + timedelta(seconds=10)
    # RFC 9110 section 10.2.3 / RFC 5322 date format.
    http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            return resp(status=429, headers={"Retry-After": http_date})
        return resp(status=200, json_body={"ok": True})

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
    client = make_client(
        max_retries=3,
        sleeps=sleeps,
        max_retry_after_seconds=10.0,
    )

    def fake_request(*a: Any, **kw: Any) -> Any:
        return resp(status=429, headers={"Retry-After": "300"})  # 5 minutes

    monkeypatch.setattr(client._session, "request", fake_request)
    with pytest.raises(RestRateLimited) as excinfo:
        client.post("/api/x", json={})
    assert "exceeds max_retry_after_seconds" in excinfo.value.message
    assert sleeps == []  # no sleep: short-circuited


def test_429_without_retry_after_falls_back_to_jitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing/unparseable Retry-After uses the same backoff as 5xx."""
    sleeps: list[float] = []
    client = make_client(max_retries=2, sleeps=sleeps, rand_value=1.0)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 3:
            return resp(status=429, headers={})  # no Retry-After
        return resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.post("/api/x", json={})
    # rand_value=1.0 + base=0.5: attempt 0 -> 0.5, attempt 1 -> 1.0.
    assert sleeps == [0.5, 1.0]


def test_5xx_uses_jittered_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    client = make_client(max_retries=3, sleeps=sleeps, rand_value=0.5)
    calls: list[int] = []

    def fake_request(*a: Any, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) < 4:
            return resp(status=503, text="overloaded")
        return resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.post("/api/x", json={})
    # rand=0.5: 0.5 * 0.5 * 2^attempt -> 0.25, 0.5, 1.0.
    assert sleeps == pytest.approx([0.25, 0.5, 1.0])


def test_jitter_caps_at_30_seconds() -> None:
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

"""Verify RestClient request shape, URL handling, and JSON serialization."""

from __future__ import annotations

from typing import Any

import pytest

from eden.providers._impl.http_rest import RestClient
from tests.unit.providers_impl.http_rest_helpers import client as make_client
from tests.unit.providers_impl.http_rest_helpers import resp

pytestmark = pytest.mark.unit


def test_post_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kw: Any) -> Any:
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = kw.get("headers")
        captured["json"] = kw.get("json")
        return resp(status=200, json_body={"id": "abc"})

    monkeypatch.setattr(client._session, "request", fake_request)
    out = client.post("/api/sandbox", json={"image": "ubuntu"})
    assert out == {"id": "abc"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.test/api/sandbox"
    assert captured["headers"] == {"Authorization": "Bearer test-token"}
    assert captured["json"] == {"image": "ubuntu"}


def test_get_threads_params(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kw: Any) -> Any:
        captured["params"] = kw.get("params")
        return resp(status=200, json_body={"ok": True})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.get("/api/list", params={"limit": 10})
    assert captured["params"] == {"limit": 10}


def test_delete_does_not_expect_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client._session,
        "request",
        lambda *a, **kw: resp(status=204, text=""),
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

"""E2E: OpenTelemetry tracing for the REST client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from eden.providers._impl.http_rest import RestClient

pytestmark = pytest.mark.e2e


def test_rest_client_emits_request_span(
    captured_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = RestClient(
        base_url="https://api.test/",
        headers={"Authorization": "Bearer test"},
        timeout=5.0,
        max_retries=0,
    )

    def fake_request(*a: object, **kw: object) -> MagicMock:
        m = MagicMock(spec=requests.Response)
        m.status_code = 200
        m.headers = {}
        m.text = '{"ok": true}'
        m.json.return_value = {"ok": True}
        return m

    monkeypatch.setattr(client._session, "request", fake_request)
    client.get("/api/x")

    rest_spans = [s for s in captured_spans.get_finished_spans() if s.name == "eden.rest.request"]
    assert rest_spans, "no eden.rest.request span captured"
    attrs = dict(rest_spans[0].attributes or {})
    assert attrs["http.method"] == "GET"
    assert attrs["http.url"] == "https://api.test/api/x"
    assert attrs["http.status_code"] == 200
    assert attrs["http.retry_count"] == 0

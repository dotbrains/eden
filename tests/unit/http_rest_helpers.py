"""Shared helpers for REST client tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import requests

from eden.providers._impl.http_rest import RestClient


def resp(
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


def client(
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

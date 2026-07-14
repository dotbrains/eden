from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import requests

from eden.errors import RestError
from eden.providers._impl.http_retry import (
    full_jitter_backoff as _full_jitter_backoff,
)
from eden.providers._impl.http_retry import (
    parse_retry_after as _parse_retry_after,
)
from eden.providers._impl.http_retry import raise_status, retry_delay
from eden.tracing import set_attributes, span

_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_MAX_RETRY_AFTER = 60.0


@dataclass
class RestClient:
    """Sync REST client with auth-header injection + smart retries.

    Errors map to typed exceptions; injected ``sleep`` and ``rand`` keep retry
    tests deterministic.
    """

    base_url: str
    headers: Mapping[str, str]
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = _DEFAULT_MAX_RETRIES
    max_retry_after_seconds: float = _DEFAULT_MAX_RETRY_AFTER
    sleep: Callable[[float], None] = time.sleep
    rand: Callable[[], float] = field(default=random.random)
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
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", path, json=json, params=params)

    def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        self._request("DELETE", path, expect_json=False, params=params)

    def close(self) -> None:
        self._session.close()

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _backoff(self, attempt: int) -> float:
        return _full_jitter_backoff(attempt, rand=self.rand)

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
        with span(
            "eden.rest.request",
            attributes={"http.method": method, "http.url": url},
        ) as request_span:
            return self._request_impl(
                method=method,
                url=url,
                params=params,
                json=json,
                expect_json=expect_json,
                request_span=request_span,
            )

    def _request_impl(
        self,
        *,
        method: str,
        url: str,
        params: Mapping[str, Any] | None,
        json: Mapping[str, Any] | None,
        expect_json: bool,
        request_span: Any,
    ) -> dict[str, Any]:
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
                    self.sleep(self._backoff(attempt))
                    continue
                raise RestError(
                    message=f"connection error to {url}: {exc}",
                    cause=exc,
                    url=url,
                ) from exc

            if 200 <= resp.status_code < 300:
                set_attributes(
                    request_span,
                    {"http.status_code": resp.status_code, "http.retry_count": attempt},
                )
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

            delay = retry_delay(
                resp,
                attempt=attempt,
                max_retries=self.max_retries,
                max_retry_after_seconds=self.max_retry_after_seconds,
                backoff=self._backoff,
                url=url,
            )
            if delay is not None:
                self.sleep(delay)
                continue

            raise_status(resp, url)

        # Unreachable in practice (loop either returns or raises),
        # but mypy needs a fallthrough.
        raise RestError(message="exhausted retries", cause=last_exc, url=url)


__all__ = ["RestClient", "_full_jitter_backoff", "_parse_retry_after"]

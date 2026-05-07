"""Shared REST client for cloud sandbox providers."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from eden.errors import (
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
)
from eden.tracing import set_attributes, span

_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_RETRIES = 3
# Exponential-backoff base + cap (seconds). Each retry sleeps for a random
# duration in [0, min(cap, base * 2**attempt)] — full-jitter strategy from
# https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
_BACKOFF_BASE = 0.5
_BACKOFF_CAP = 30.0
# Hard ceiling on Retry-After honour. Servers occasionally return values like
# 7200s (two hours); waiting that long would hang any orchestrated run with
# nothing useful to show. Surface a typed RestRateLimited at this cap instead.
_DEFAULT_MAX_RETRY_AFTER = 60.0


def _parse_retry_after(header: str | None, *, now: datetime | None = None) -> float | None:
    """Return Retry-After's seconds-from-now per RFC 9110.

    Accepts either the seconds form (``120``) or the HTTP-date form
    (``Wed, 21 Oct 2026 07:28:00 GMT``). Returns ``None`` for missing or
    unparseable values; clamps negative deltas to 0.
    """
    if header is None:
        return None
    raw = header.strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    ref = now if now is not None else datetime.now(UTC)
    return max(0.0, (dt - ref).total_seconds())


def _full_jitter_backoff(
    attempt: int,
    *,
    base: float = _BACKOFF_BASE,
    cap: float = _BACKOFF_CAP,
    rand: Callable[[], float] | None = None,
) -> float:
    """Full-jitter exponential backoff: ``random() * min(cap, base * 2**attempt)``."""
    rng = rand if rand is not None else random.random
    raw_cap: float = base * float(2**attempt)
    bounded = min(cap, raw_cap)
    return float(rng()) * bounded


@dataclass
class RestClient:
    """Sync REST client with auth-header injection + smart retries.

    Caller supplies ``headers`` at construction (e.g.
    ``{"Authorization": f"Bearer {key}"}``). Errors map to typed exceptions:
    401/403 → :class:`RestAuthError`, 404 → :class:`RestNotFoundError`,
    429 (after retries exhausted or after Retry-After exceeds
    ``max_retry_after_seconds``) → :class:`RestRateLimited`,
    other 4xx/5xx → :class:`RestError`.

    Retry policy:

    - **5xx (500/502/503/504)** — full-jitter exponential backoff with base
      0.5s and cap 30s. Each attempt picks a fresh random delay in
      ``[0, min(cap, base * 2**attempt)]``.
    - **429** — honours the ``Retry-After`` response header (seconds or
      HTTP-date per RFC 9110). When the header is absent or unparseable,
      falls back to the same full-jitter schedule used for 5xx. When the
      header asks for longer than ``max_retry_after_seconds`` (default 60),
      raises :class:`RestRateLimited` immediately rather than blocking the
      run.
    - **Connection errors** — retried with the same schedule as 5xx.

    All sleeps go through the injected ``sleep`` callable so tests can stub
    them out without timing-sensitive assertions.
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

            # Retry envelope: 429 honours Retry-After; 5xx uses jittered backoff.
            retryable = resp.status_code in (500, 502, 503, 504, 429)
            if retryable and attempt < self.max_retries:
                if resp.status_code == 429:
                    delay = _parse_retry_after(resp.headers.get("Retry-After"))
                    if delay is None:
                        delay = self._backoff(attempt)
                    elif delay > self.max_retry_after_seconds:
                        # Server's ask exceeds our budget — raise now rather
                        # than blocking the orchestrator for minutes/hours.
                        raise RestRateLimited(
                            message=(
                                f"HTTP 429 from {url}: Retry-After={delay:.0f}s "
                                f"exceeds max_retry_after_seconds="
                                f"{self.max_retry_after_seconds:.0f}s"
                            ),
                            status=resp.status_code,
                            body=resp.text,
                            url=url,
                        )
                else:
                    delay = self._backoff(attempt)
                self.sleep(delay)
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

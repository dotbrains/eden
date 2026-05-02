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

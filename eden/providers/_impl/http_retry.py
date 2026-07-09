"""Retry and status helpers for REST clients."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from eden.errors import RestAuthError, RestError, RestNotFoundError, RestRateLimited

# Exponential-backoff base + cap (seconds). Each retry sleeps for a random
# duration in [0, min(cap, base * 2**attempt)].
_BACKOFF_BASE = 0.5
_BACKOFF_CAP = 30.0
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def parse_retry_after(header: str | None, *, now: datetime | None = None) -> float | None:
    """Return Retry-After's seconds-from-now per RFC 9110."""
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


def full_jitter_backoff(
    attempt: int,
    *,
    base: float = _BACKOFF_BASE,
    cap: float = _BACKOFF_CAP,
    rand: Callable[[], float] | None = None,
) -> float:
    """Full-jitter exponential backoff."""
    rng = rand if rand is not None else random.random
    raw_cap: float = base * float(2**attempt)
    bounded = min(cap, raw_cap)
    return float(rng()) * bounded


def retry_delay(
    resp: requests.Response,
    *,
    attempt: int,
    max_retries: int,
    max_retry_after_seconds: float,
    backoff: Callable[[int], float],
    url: str,
) -> float | None:
    """Return a retry delay for a response, or None when it should not retry."""
    if resp.status_code not in _RETRYABLE_STATUSES or attempt >= max_retries:
        return None
    if resp.status_code != 429:
        return backoff(attempt)

    delay = parse_retry_after(resp.headers.get("Retry-After"))
    if delay is None:
        return backoff(attempt)
    if delay > max_retry_after_seconds:
        raise RestRateLimited(
            message=(
                f"HTTP 429 from {url}: Retry-After={delay:.0f}s "
                f"exceeds max_retry_after_seconds={max_retry_after_seconds:.0f}s"
            ),
            status=resp.status_code,
            body=resp.text,
            url=url,
        )
    return delay


def raise_status(resp: requests.Response, url: str) -> None:
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


__all__ = [
    "full_jitter_backoff",
    "parse_retry_after",
    "raise_status",
    "retry_delay",
]

"""Shared helpers for Vercel provider tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from eden.providers._impl.http_rest import RestClient


def mock_client(
    post_returns: dict[str, object] | list[dict[str, object]] | None = None,
) -> MagicMock:
    """Build a MagicMock(spec=RestClient) whose post() returns canned data."""
    client = MagicMock(spec=RestClient)
    if isinstance(post_returns, list):
        client.post.side_effect = post_returns
    elif post_returns is not None:
        client.post.return_value = post_returns
    return client

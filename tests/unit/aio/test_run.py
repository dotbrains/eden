"""Verify ``eden.aio.run`` forwards sync ``run`` options."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from eden import aio

pytestmark = pytest.mark.unit


def test_aio_run_forwards_fork_session(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_sync_run(**kwargs: Any) -> object:
        seen.update(kwargs)
        return object()

    monkeypatch.setattr("eden.aio._run._sync_run", fake_sync_run)

    result = asyncio.run(
        aio.run(
            agent=object(),  # type: ignore[arg-type]
            sandbox=object(),  # type: ignore[arg-type]
            prompt="continue",
            resume_session="parent-session",
            fork_session=True,
        )
    )

    assert result is not None
    assert seen["resume_session"] == "parent-session"
    assert seen["fork_session"] is True

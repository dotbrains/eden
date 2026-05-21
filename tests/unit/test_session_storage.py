"""Tests for the ADR-0012-style per-agent ``SessionStorage`` Protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from eden import ClaudeSessionStorage, SessionStorage, claude_code
from eden.providers._types import Mount
from eden.session._claude import ClaudeSessionStorage as _ClaudeSessionStorageImpl

pytestmark = pytest.mark.unit


def test_claude_session_storage_satisfies_protocol() -> None:
    """The default Claude impl is runtime-checkable as ``SessionStorage``."""
    storage = ClaudeSessionStorage()
    assert isinstance(storage, SessionStorage)


def test_claude_session_storage_extra_mounts_when_dir_exists(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    projects = fake_home / ".claude" / "projects"
    projects.mkdir(parents=True)
    storage = ClaudeSessionStorage(home=fake_home)
    mounts = storage.extra_mounts()
    assert len(mounts) == 1
    assert mounts[0].host == projects
    assert mounts[0].sandbox == Path("/root/.claude/projects")


def test_claude_session_storage_extra_mounts_when_dir_absent(tmp_path: Path) -> None:
    storage = ClaudeSessionStorage(home=tmp_path)
    # No ~/.claude/projects in tmp_path → empty tuple.
    assert storage.extra_mounts() == ()


def test_claude_session_storage_sandbox_transfer_is_noop() -> None:
    """Claude reads sessions from its own mount; transfer is a no-op."""
    storage = ClaudeSessionStorage()

    class _FakeHandle:
        worktree_path = Path("/workspace")

    # should not raise
    storage.sandbox_transfer(
        handle=_FakeHandle(),  # type: ignore[arg-type]
        host_session_file=Path("/tmp/does-not-exist.jsonl"),
        session_id="x",
    )


def test_claude_session_storage_host_capture_locates_jsonl(tmp_path: Path) -> None:
    """End-to-end: write a fake transcript and ``host_capture`` finds it."""
    fake_home = tmp_path / "home"
    # Build the slug the way capture_session expects.
    from eden.session._slug import claude_projects_slug

    host_repo = tmp_path / "repo"
    host_repo.mkdir()
    slug = claude_projects_slug(host_repo)
    project_dir = fake_home / ".claude" / "projects" / slug
    project_dir.mkdir(parents=True)
    session_id = "abc-123"
    src = project_dir / f"{session_id}.jsonl"
    src.write_text('{"role":"user","content":"hi","cwd":"' + str(host_repo) + '"}\n')

    class _FakeHandle:
        worktree_path = host_repo  # no_sandbox style: WT inside repo

    storage = ClaudeSessionStorage(home=fake_home)
    captured = storage.host_capture(
        handle=_FakeHandle(),  # type: ignore[arg-type]
        session_id=session_id,
        host_repo_path=host_repo,
        branch="eden/abc",
        iteration=0,
    )
    assert captured is not None
    assert captured.exists()
    assert captured.is_file()


def test_claude_code_factory_attaches_session_storage_by_default() -> None:
    agent = claude_code(model="claude-opus-4-7")
    assert agent.session_storage is not None
    assert isinstance(agent.session_storage, _ClaudeSessionStorageImpl)


def test_claude_code_factory_no_session_storage_when_disabled() -> None:
    agent = claude_code(model="claude-opus-4-7", capture_sessions=False)
    assert agent.session_storage is None


def test_resolve_session_storage_prefers_attribute() -> None:
    """The orchestrator's resolver should use ``agent.session_storage``."""
    from eden.orchestrator._loop import _resolve_session_storage

    class _CustomStorage:
        def extra_mounts(self) -> tuple[Mount, ...]:
            return ()

        def host_capture(self, **_: Any) -> Path | None:
            return None

        def sandbox_transfer(self, **_: Any) -> None:
            return None

    custom = _CustomStorage()

    class _Agent:
        name = "x"
        model = "m"
        session_storage = custom

    storage = _resolve_session_storage(_Agent())  # type: ignore[arg-type]
    assert storage is custom


def test_resolve_session_storage_falls_back_to_legacy_bool() -> None:
    """Agents that only ship ``captures_sessions=True`` get the default."""
    from eden.orchestrator._loop import _resolve_session_storage

    @dataclass
    class _LegacyAgent:
        name: str = "x"
        model: str = "m"
        captures_sessions: bool = True

    storage = _resolve_session_storage(_LegacyAgent())  # type: ignore[arg-type]
    assert isinstance(storage, _ClaudeSessionStorageImpl)


def test_resolve_session_storage_returns_none_when_disabled() -> None:
    from eden.orchestrator._loop import _resolve_session_storage

    @dataclass
    class _DisabledAgent:
        name: str = "x"
        model: str = "m"
        captures_sessions: bool = False

    assert _resolve_session_storage(_DisabledAgent()) is None  # type: ignore[arg-type]


def test_resolve_session_storage_explicit_none_attr_falls_back_to_bool() -> None:
    """If ``session_storage is None`` and ``captures_sessions=True``, use default."""
    from eden.orchestrator._loop import _resolve_session_storage

    @dataclass
    class _Agent:
        name: str = "x"
        model: str = "m"
        session_storage: None = None
        captures_sessions: bool = True

    storage = _resolve_session_storage(_Agent())  # type: ignore[arg-type]
    assert isinstance(storage, _ClaudeSessionStorageImpl)


def test_third_party_session_storage_satisfies_protocol() -> None:
    """A bare-bones third-party impl is recognised as ``SessionStorage``."""

    class _CodexLikeStorage:
        def extra_mounts(self) -> tuple[Mount, ...]:
            return ()

        def host_capture(self, **_: Any) -> Path | None:
            return None

        def sandbox_transfer(self, **_: Any) -> None:
            return None

    assert isinstance(_CodexLikeStorage(), SessionStorage)

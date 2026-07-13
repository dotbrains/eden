"""Verify host-side ``resume_session=`` precheck and per-storage locators."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from eden import SessionNotFound, run
from eden._types import RunResult
from eden.agents import claude_code, codex
from eden.providers._types import ExecResult
from eden.session._claude import ClaudeSessionStorage
from eden.session._codex import CodexSessionStorage

pytestmark = pytest.mark.unit


# ---- Locator-method unit tests --------------------------------------------


def _seed_claude(home: Path, *, slug_cwd: Path, session_id: str) -> Path:
    from eden.session._slug import claude_projects_slug

    slug = claude_projects_slug(slug_cwd)
    f = home / ".claude" / "projects" / slug / f"{session_id}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"x": 1}) + "\n", encoding="utf-8")
    return f


def test_claude_locator_returns_path_when_present(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cwd = Path("/workspace")
    src = _seed_claude(home, slug_cwd=cwd, session_id="sess-x")
    s = ClaudeSessionStorage(home=home)
    assert s.locate_session_on_host(session_id="sess-x", sandbox_cwd=cwd) == src


def test_claude_locator_returns_none_when_missing(tmp_path: Path) -> None:
    s = ClaudeSessionStorage(home=tmp_path)
    assert s.locate_session_on_host(session_id="missing", sandbox_cwd=Path("/workspace")) is None


def test_claude_locator_uses_sandbox_cwd_slug(tmp_path: Path) -> None:
    # Same session id seeded under one cwd; lookup with a different cwd must miss.
    home = tmp_path / "home"
    _seed_claude(home, slug_cwd=Path("/workspace"), session_id="sess-y")
    s = ClaudeSessionStorage(home=home)
    assert s.locate_session_on_host(session_id="sess-y", sandbox_cwd=Path("/elsewhere")) is None


def test_codex_locator_walks_dated_tree(tmp_path: Path) -> None:
    home = tmp_path / "home"
    target_dir = home / ".codex" / "sessions" / "2026" / "05" / "26"
    target_dir.mkdir(parents=True)
    f = target_dir / "rollout-20260526T100000-abc.jsonl"
    f.write_text("{}\n", encoding="utf-8")
    s = CodexSessionStorage(home=home)
    # sandbox_cwd ignored for codex
    assert s.locate_session_on_host(session_id="abc", sandbox_cwd=Path("/x")) == f


def test_codex_locator_returns_none_when_missing(tmp_path: Path) -> None:
    s = CodexSessionStorage(home=tmp_path)
    assert s.locate_session_on_host(session_id="missing", sandbox_cwd=Path("/x")) is None


# ---- End-to-end precheck via run() ----------------------------------------


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ran(*args: Any, **kwargs: Any) -> RunResult:  # pragma: no cover — assertion proxy
    raise AssertionError("orchestrator should have raised BEFORE calling _run_loop")


def test_run_raises_session_not_found_for_missing_codex_resume(
    tmp_git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("eden.orchestrator._run_loop", _ran)
    # Point codex at an empty home so locate_session_on_host returns None.
    empty_home = tmp_git_repo / "empty-home"
    empty_home.mkdir()
    agent = codex(
        capture_sessions=True,
    )
    # Inject a CodexSessionStorage pointing at the empty home via attribute
    # assignment isn't possible (frozen dataclass); instead monkeypatch the
    # default sessions dir.
    monkeypatch.setattr(
        "eden.session._codex.find_codex_session_path",
        lambda root, sid: None,
    )
    from eden.sandboxes.no_sandbox import provider as no_sandbox

    with pytest.raises(SessionNotFound) as exc:
        run(
            agent=agent,
            sandbox=no_sandbox(),
            prompt="continue",
            cwd=tmp_git_repo,
            resume_session="absent-id",
            max_iterations=1,
        )
    assert exc.value.session_id == "absent-id"
    assert exc.value.agent_name == "codex"


def test_run_skips_precheck_when_agent_has_no_locator(
    tmp_git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Back-compat: agents whose session_storage doesn't implement
    locate_session_on_host must NOT trigger the precheck (or any error)."""
    captured: dict[str, Any] = {"called": False}

    def _fake_run(**kwargs: Any) -> RunResult:
        captured["called"] = True
        captured.update(kwargs)
        return RunResult(
            iterations=[],
            completion_signal=None,
            branch="HEAD",
            stdout="",
            commits=[],
            worktree_path=tmp_git_repo,
            preserved_worktree_path=None,
            merged_to_target_branch=None,
            cwd=tmp_git_repo,
            prompt="continue",
            env={},
            log_file_path=None,
            session_id=None,
            session_file_path=None,
            usage=None,
        )

    monkeypatch.setattr("eden.orchestrator._run_loop", _fake_run)

    agent = claude_code(capture_sessions=False)
    # capture_sessions=False → session_storage is None → precheck skipped.
    from eden.sandboxes.no_sandbox import provider as no_sandbox

    run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="continue",
        cwd=tmp_git_repo,
        resume_session="any-id",
        max_iterations=1,
    )
    assert captured["called"] is True

"""Verify create_sandbox runtime wrapper behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.lifecycle import Hook, Hooks, HostHooks, SandboxHooks
from eden.providers._types import ExecResult
from eden.sandboxes import Sandbox, create_sandbox
from tests.unit.create_sandbox.create_sandbox_helpers import StubHandle, StubProvider

pytestmark = pytest.mark.unit


def _write_text_hook(path: str | Path, text: str) -> Hook:
    code = f"from pathlib import Path; Path({str(path)!r}).write_text({text!r})"
    return Hook(f'{sys.executable} -c "{code}"')


def test_sandbox_exec_supports_sudo(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    s = create_sandbox(sandbox=StubProvider())
    try:
        result = s.exec("echo $K", env={"K": "V"}, sudo=True)
        assert result.ok
        handle = s.handle
        assert isinstance(handle, StubHandle)
        assert handle.exec_calls[-1]["cmd"] == "sudo -E -- sh -c 'echo $K'"
        assert handle.exec_calls[-1]["env"] == {"K": "V"}
    finally:
        s.close()


def test_close_closes_handle_then_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p)
    handle = s.handle
    s.close()
    assert handle.closed[0] is True  # type: ignore[attr-defined]


def test_sandbox_is_context_manager(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    with create_sandbox(sandbox=p) as s:
        assert isinstance(s, Sandbox)


def test_cwd_stored_on_sandbox(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p, cwd=Path("/some/cwd"))
    try:
        assert s.cwd == Path("/some/cwd")
    finally:
        s.close()


def test_sandbox_exec_delegates_to_handle_with_default_cwd(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p)
    try:
        handle = s.handle
        assert isinstance(handle, StubHandle)
        result = s.exec("pwd")
        assert result == ExecResult(stdout="ok", stderr="", exit_code=0)
        assert handle.exec_calls[-1] == {
            "cmd": "pwd",
            "on_line": None,
            "cwd": s.worktree.worktree_path,
            "env": None,
            "timeout": None,
            "stdin": None,
        }
    finally:
        s.close()


def test_sandbox_exec_forwards_options(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    seen_lines: list[str] = []
    on_line = seen_lines.append
    s = create_sandbox(sandbox=p, cwd=Path("/repo/subdir"))
    try:
        handle = s.handle
        assert isinstance(handle, StubHandle)
        s.exec(
            "cat",
            on_line=on_line,
            env={"A": "B"},
            timeout=2.5,
            stdin="input",
        )
        assert seen_lines == ["line"]
        call = handle.exec_calls[-1]
        assert call["cmd"] == "cat"
        assert call["on_line"] is on_line
        assert call["cwd"] == Path("/repo/subdir")
        assert call["env"] == {"A": "B"}
        assert call["timeout"] == 2.5
        assert call["stdin"] == "input"
    finally:
        s.close()


def test_sandbox_exec_explicit_cwd_overrides_sandbox_cwd(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p, cwd=Path("/repo/subdir"))
    try:
        handle = s.handle
        assert isinstance(handle, StubHandle)
        s.exec("pwd", cwd=Path("/tmp"))
        assert handle.exec_calls[-1]["cwd"] == Path("/tmp")
    finally:
        s.close()


def test_create_sandbox_runs_creation_and_close_hooks(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    close_marker = tmp_git_repo / "host-closed.txt"
    hooks = Hooks(
        host=HostHooks(
            on_worktree_ready=(_write_text_hook("host-ready.txt", "ready"),),
            on_close=(_write_text_hook(close_marker, "closed"),),
        ),
        sandbox=SandboxHooks(
            on_sandbox_ready=(Hook("sandbox-ready"),),
            on_close=(Hook("sandbox-close"),),
        ),
    )
    s = create_sandbox(sandbox=p, hooks=hooks)
    handle = s.handle
    assert isinstance(handle, StubHandle)
    assert (s.worktree.worktree_path / "host-ready.txt").read_text() == "ready"
    assert [call["cmd"] for call in handle.exec_calls[:5]] == [
        "git config --global --get-all safe.directory || true",
        f"git config --global --add safe.directory {s.worktree.worktree_path.as_posix()}",
        "git config --global user.name Test",
        "git config --global user.email test@example.com",
        "sandbox-ready",
    ]

    s.close()

    assert handle.exec_calls[-1]["cmd"] == "sandbox-close"
    assert close_marker.read_text() == "closed"

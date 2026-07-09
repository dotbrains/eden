"""Verify the top-level create_sandbox factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

from eden.lifecycle import Hook, Hooks, HostHooks, SandboxHooks
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    Mount,
)
from eden.sandboxes import Sandbox, create_sandbox
from eden.sandboxes.errors import UnsupportedStrategy

pytestmark = pytest.mark.unit


@dataclass
class _StubHandle:
    worktree_path: Path
    closed: list[bool] = field(default_factory=lambda: [False])
    exec_calls: list[dict[str, object]] = field(default_factory=list)

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
        self.exec_calls.append(
            {
                "cmd": cmd,
                "on_line": on_line,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
                "stdin": stdin,
            }
        )
        if on_line is not None:
            on_line("line")
        return ExecResult(stdout="ok", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        return None

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        return None

    def close(self) -> None:
        self.closed[0] = True


@dataclass
class _StubProvider:
    name: str = "stub"
    kind: Literal["bind_mount", "isolated", "none"] = "bind_mount"
    supported: frozenset[str] = field(
        default_factory=lambda: frozenset({"head", "merge_to_head", "named"})
    )
    seen_opts: list[CreateOptions] = field(default_factory=list)

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return strategy.tag in self.supported

    def create(self, opts: CreateOptions) -> Any:
        self.seen_opts.append(opts)
        return _StubHandle(worktree_path=opts.worktree_path)


def test_branch_and_branch_strategy_are_mutually_exclusive(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    with pytest.raises(ValueError):
        create_sandbox(
            sandbox=p,
            branch="x",
            branch_strategy=BranchStrategy.head(),
        )


def test_branch_arg_translates_to_named_strategy(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p, branch="feat/x")
    try:
        assert s.worktree.branch == "feat/x"
    finally:
        s.close()


def test_default_strategy_for_bind_mount_is_merge_to_head(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider(kind="bind_mount")
    s = create_sandbox(sandbox=p)
    try:
        assert s.worktree.branch.startswith("eden/")
        assert s.worktree.managed is True
    finally:
        s.close()


def test_default_strategy_for_none_is_head(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider(kind="none")
    s = create_sandbox(sandbox=p)
    try:
        assert s.worktree.branch == "HEAD"
        assert s.worktree.managed is False
    finally:
        s.close()


def test_sandbox_exec_supports_sudo(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    s = create_sandbox(sandbox=_StubProvider())
    try:
        result = s.exec("echo $K", env={"K": "V"}, sudo=True)
        assert result.ok
        handle = s.handle
        assert isinstance(handle, _StubHandle)
        assert handle.exec_calls[-1]["cmd"] == "sudo -E -- sh -c 'echo $K'"
        assert handle.exec_calls[-1]["env"] == {"K": "V"}
    finally:
        s.close()


def test_unsupported_strategy_raises(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider(supported=frozenset({"merge_to_head"}))
    with pytest.raises(UnsupportedStrategy):
        create_sandbox(sandbox=p, branch_strategy=BranchStrategy.head())


def test_passes_env_and_mounts_to_provider(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    mount = Mount(host=tmp_git_repo, sandbox=Path("/data"))
    s = create_sandbox(
        sandbox=p,
        env={"K": "V"},
        mounts=(mount,),
        name="my-feature",
    )
    try:
        opts = p.seen_opts[0]
        assert opts.env == {"K": "V"}
        assert opts.mounts == (mount,)
        assert opts.name_hint == "my-feature"
    finally:
        s.close()


def test_create_sandbox_loads_dot_eden_env(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("FROM_FILE=value\n")
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p, env={"EXPLICIT": "override"})
    try:
        opts = p.seen_opts[0]
        assert opts.env == {"FROM_FILE": "value", "EXPLICIT": "override"}
    finally:
        s.close()


def test_create_sandbox_explicit_env_overrides_dot_env(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("KEY=from_file\n")
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p, env={"KEY": "from_caller"})
    try:
        assert p.seen_opts[0].env == {"KEY": "from_caller"}
    finally:
        s.close()


def test_close_closes_handle_then_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p)
    handle = s.handle
    s.close()
    assert handle.closed[0] is True  # type: ignore[attr-defined]


def test_sandbox_is_context_manager(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    with create_sandbox(sandbox=p) as s:
        assert isinstance(s, Sandbox)


def test_cwd_stored_on_sandbox(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p, cwd=Path("/some/cwd"))
    try:
        assert s.cwd == Path("/some/cwd")
    finally:
        s.close()


def test_sandbox_exec_delegates_to_handle_with_default_cwd(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p)
    try:
        handle = s.handle
        assert isinstance(handle, _StubHandle)
        result = s.exec("pwd")
        assert result == ExecResult(stdout="ok", stderr="", exit_code=0)
        assert handle.exec_calls == [
            {
                "cmd": "pwd",
                "on_line": None,
                "cwd": s.worktree.worktree_path,
                "env": None,
                "timeout": None,
                "stdin": None,
            }
        ]
    finally:
        s.close()


def test_sandbox_exec_forwards_options(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    seen_lines: list[str] = []
    on_line = seen_lines.append
    s = create_sandbox(sandbox=p, cwd=Path("/repo/subdir"))
    try:
        handle = s.handle
        assert isinstance(handle, _StubHandle)
        s.exec(
            "cat",
            on_line=on_line,
            env={"A": "B"},
            timeout=2.5,
            stdin="input",
        )
        assert seen_lines == ["line"]
        call = handle.exec_calls[0]
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
    p = _StubProvider()
    s = create_sandbox(sandbox=p, cwd=Path("/repo/subdir"))
    try:
        handle = s.handle
        assert isinstance(handle, _StubHandle)
        s.exec("pwd", cwd=Path("/tmp"))
        assert handle.exec_calls[0]["cwd"] == Path("/tmp")
    finally:
        s.close()


def test_worktree_mutually_exclusive_with_branch_args(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eden.orchestrator import create_worktree

    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    with create_worktree() as wt:
        with pytest.raises(ValueError):
            create_sandbox(sandbox=p, worktree=wt, branch="x")
        with pytest.raises(ValueError):
            create_sandbox(sandbox=p, worktree=wt, branch_strategy=BranchStrategy.head())
        with pytest.raises(ValueError):
            create_sandbox(sandbox=p, worktree=wt, base_branch="main")


def test_caller_worktree_survives_sandbox_close(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Split ownership: Sandbox.close() tears down the container only."""
    from eden.orchestrator import create_worktree

    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    wt = create_worktree()
    try:
        s = create_sandbox(sandbox=p, worktree=wt)
        assert s.owns_worktree is False
        assert s.worktree is wt
        handle = s.handle
        s.close()
        assert handle.closed[0] is True  # type: ignore[attr-defined]
        # Worktree is still on disk and still open — the caller owns it.
        assert wt.worktree_path.exists()
    finally:
        result = wt.close()
    # close() above is the FIRST close of the handle: a clean worktree is
    # removed, not reported as already-closed.
    assert result.action == "removed"


def test_one_worktree_hosts_sequential_sandboxes(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eden.orchestrator import create_worktree

    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    with create_worktree() as wt:
        with create_sandbox(sandbox=p, worktree=wt) as first:
            assert first.worktree.branch == wt.branch
        with create_sandbox(sandbox=p, worktree=wt) as second:
            assert second.worktree.branch == wt.branch
        assert len(p.seen_opts) == 2
        assert all(o.worktree_path == wt.worktree_path for o in p.seen_opts)


def test_provider_failure_leaves_caller_worktree_open(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eden.orchestrator import create_worktree

    @dataclass
    class _ExplodingProvider(_StubProvider):
        def create(self, opts: CreateOptions) -> Any:
            raise RuntimeError("boom")

    monkeypatch.chdir(tmp_git_repo)
    with create_worktree() as wt:
        with pytest.raises(RuntimeError):
            create_sandbox(sandbox=_ExplodingProvider(), worktree=wt)
        # The factory must not close a worktree it does not own.
        assert wt.worktree_path.exists()
        # Reusable after the failure.
        with create_sandbox(sandbox=_StubProvider(), worktree=wt):
            pass


def test_copy_to_worktree_rejected_for_head_style_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eden.errors import InvalidOptions
    from eden.providers._types import BranchStrategy as _BS
    from eden.worktree._create import create_worktree as _carve

    monkeypatch.chdir(tmp_git_repo)
    # The head-style check fires before any copy happens, so the source file
    # need not exist (and the host tree must stay clean for the head carve).
    wt = _carve(host_repo_path=tmp_git_repo, strategy=_BS.head())
    try:
        with pytest.raises(InvalidOptions):
            create_sandbox(
                sandbox=_StubProvider(),
                worktree=wt,
                copy_to_worktree=["seed.txt"],
            )
    finally:
        wt.close()


def test_close_propagates_handle_error_over_worktree_error(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing worktree.close() must not replace the handle's exception."""
    from eden.worktree._create import WorktreeHandle

    monkeypatch.chdir(tmp_git_repo)
    s = create_sandbox(sandbox=_StubProvider())

    def _handle_boom() -> None:
        raise RuntimeError("handle boom")

    def _wt_boom(self: WorktreeHandle) -> None:
        raise OSError("worktree boom")

    monkeypatch.setattr(s.handle, "close", _handle_boom)
    monkeypatch.setattr(WorktreeHandle, "close", _wt_boom)
    try:
        with pytest.raises(RuntimeError, match="handle boom"):
            s.close()
    finally:
        monkeypatch.undo()
        s.worktree.close()


def test_create_failure_propagates_over_worktree_cleanup_error(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing cleanup close() must not replace the provider's create error."""
    from eden.worktree._create import WorktreeHandle

    @dataclass
    class _ExplodingProvider(_StubProvider):
        def create(self, opts: CreateOptions) -> Any:
            raise RuntimeError("create boom")

    monkeypatch.chdir(tmp_git_repo)
    real_close = WorktreeHandle.close
    carved: list[WorktreeHandle] = []

    def _capture_and_boom(self: WorktreeHandle) -> None:
        carved.append(self)
        raise OSError("worktree boom")

    monkeypatch.setattr(WorktreeHandle, "close", _capture_and_boom)
    try:
        with pytest.raises(RuntimeError, match="create boom"):
            create_sandbox(sandbox=_ExplodingProvider())
    finally:
        monkeypatch.undo()
        for wt in carved:
            real_close(wt)


def test_git_setup_timeout_threads_to_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eden._types import Timeouts

    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p, timeouts=Timeouts(git_setup=3.5))
    try:
        assert s.worktree._git_timeout == 3.5
    finally:
        s.close()


def test_git_setup_timeout_defaults_to_60s(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p)
    try:
        assert s.worktree._git_timeout == 60.0
    finally:
        s.close()


def test_create_sandbox_runs_creation_and_close_hooks(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    close_marker = tmp_git_repo / "host-closed.txt"
    hooks = Hooks(
        host=HostHooks(
            on_worktree_ready=(Hook("printf ready > host-ready.txt"),),
            on_close=(Hook(f"printf closed > {str(close_marker)!r}"),),
        ),
        sandbox=SandboxHooks(
            on_sandbox_ready=(Hook("sandbox-ready"),),
            on_close=(Hook("sandbox-close"),),
        ),
    )
    s = create_sandbox(sandbox=p, hooks=hooks)
    handle = s.handle
    assert isinstance(handle, _StubHandle)
    assert (s.worktree.worktree_path / "host-ready.txt").read_text() == "ready"
    assert handle.exec_calls[0]["cmd"] == "sandbox-ready"

    s.close()

    assert handle.exec_calls[1]["cmd"] == "sandbox-close"
    assert close_marker.read_text() == "closed"

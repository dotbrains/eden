"""Verify the forkd provider factory + _ForkdHandle methods.

forkd is Linux + KVM only and the SDK is imported lazily, so these unit tests
never import the real ``forkd`` package: they inject a fake E2B-compatible
sandbox via ``sandbox_factory=`` and run anywhere.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy, CreateOptions, ExecResult
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable
from eden.sandboxes.forkd import provider as forkd_provider

pytestmark = pytest.mark.unit


@dataclass
class _FakeResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass
class _FakeCommands:
    """Records run() calls and replays canned results in order."""

    results: list[_FakeResult]
    calls: list[dict[str, object]] = field(default_factory=list)
    _idx: int = 0

    def run(
        self,
        cmd: str,
        *,
        cwd: str | None = None,
        envs: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> _FakeResult:
        self.calls.append({"cmd": cmd, "cwd": cwd, "envs": envs, "timeout": timeout})
        if self._idx < len(self.results):
            result = self.results[self._idx]
            self._idx += 1
            return result
        return _FakeResult()


@dataclass
class _FakeSandbox:
    commands: _FakeCommands
    killed: bool = False

    def kill(self) -> None:
        self.killed = True


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="test",
    )


def _handle(
    sandbox: _FakeSandbox,
    *,
    host: Path,
    env: dict[str, str] | None = None,
    baseline: dict[Path, str] | None = None,
) -> object:
    from eden.sandboxes.forkd import _ForkdHandle

    return _ForkdHandle(
        sandbox=sandbox,  # type: ignore[arg-type]
        worktree_path=Path("/workspace"),
        host_worktree_path=host,
        env=env or {},
        timeout=60.0,
        baseline=baseline or {},
    )


def test_provider_kind_and_name() -> None:
    p = forkd_provider()
    assert p.kind == "isolated"
    assert p.name == "forkd"


def test_provider_supports_default_strategies() -> None:
    p = forkd_provider()
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_raises_provider_unavailable_without_sdk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _boom(*, snapshot: str | None) -> object:
        raise ProviderUnavailable(provider="forkd", binary="forkd")

    monkeypatch.setattr("eden.sandboxes.forkd._make_sandbox", _boom)
    p = forkd_provider()  # no sandbox_factory → default path imports forkd
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == "forkd"


def test_create_uploads_tree_and_snapshots_baseline(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    # First call: upload of hello.txt. Second call: the find/sha256sum snapshot.
    commands = _FakeCommands(
        results=[
            _FakeResult(exit_code=0),
            _FakeResult(stdout="abc123  ./hello.txt\n", exit_code=0),
        ]
    )
    sandbox = _FakeSandbox(commands=commands)
    p = forkd_provider(sandbox_factory=lambda: sandbox)
    handle = p.create(_opts(tmp_path))
    assert handle.baseline == {Path("hello.txt"): "abc123"}  # type: ignore[attr-defined]
    # Upload command carried the base64 of the file contents.
    upload_cmd = commands.calls[0]["cmd"]
    assert isinstance(upload_cmd, str)
    assert base64.b64encode(b"hi").decode("ascii") in upload_cmd


def test_create_kills_sandbox_on_upload_failure(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    commands = _FakeCommands(results=[_FakeResult(stderr="disk full", exit_code=1)])
    sandbox = _FakeSandbox(commands=commands)
    p = forkd_provider(sandbox_factory=lambda: sandbox)
    with pytest.raises(RuntimeError):
        p.create(_opts(tmp_path))
    assert sandbox.killed is True


def test_handle_exec_returns_exec_result(tmp_path: Path) -> None:
    commands = _FakeCommands(results=[_FakeResult(stdout="hello\n", exit_code=0)])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=tmp_path)
    result = handle.exec("echo hello")  # type: ignore[attr-defined]
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    assert commands.calls[0]["cmd"] == "echo hello"
    assert commands.calls[0]["timeout"] == 60.0


def test_handle_exec_merges_env(tmp_path: Path) -> None:
    commands = _FakeCommands(results=[_FakeResult()])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=tmp_path, env={"BASE": "1"})
    handle.exec("env", env={"EXTRA": "2"})  # type: ignore[attr-defined]
    assert commands.calls[0]["envs"] == {"BASE": "1", "EXTRA": "2"}


def test_handle_exec_wraps_stdin_as_base64(tmp_path: Path) -> None:
    commands = _FakeCommands(results=[_FakeResult()])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=tmp_path)
    handle.exec("cat", stdin="payload")  # type: ignore[attr-defined]
    cmd = commands.calls[0]["cmd"]
    assert isinstance(cmd, str)
    assert base64.b64encode(b"payload").decode("ascii") in cmd
    assert "base64 -d | (cat)" in cmd


def test_handle_exec_recovers_exit_code_from_exception(tmp_path: Path) -> None:
    class _ExitError(Exception):
        exit_code = 7
        stdout = "partial"
        stderr = "boom"

    @dataclass
    class _RaisingCommands:
        def run(self, cmd: str, **_kw: object) -> _FakeResult:
            raise _ExitError()

    sandbox = _FakeSandbox(commands=_RaisingCommands())  # type: ignore[arg-type]
    handle = _handle(sandbox, host=tmp_path)
    result = handle.exec("false")  # type: ignore[attr-defined]
    assert result.exit_code == 7
    assert result.stderr == "boom"


def test_handle_exec_transport_failure_returns_neg_one(tmp_path: Path) -> None:
    @dataclass
    class _RaisingCommands:
        def run(self, cmd: str, **_kw: object) -> _FakeResult:
            raise RuntimeError("vm gone")

    sandbox = _FakeSandbox(commands=_RaisingCommands())  # type: ignore[arg-type]
    handle = _handle(sandbox, host=tmp_path)
    result = handle.exec("anything")  # type: ignore[attr-defined]
    assert result.exit_code == -1
    assert "vm gone" in result.stderr


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    commands = _FakeCommands(results=[_FakeResult(exit_code=0)])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=tmp_path)
    handle.copy_file_in(src, Path("/workspace/dst.bin"))  # type: ignore[attr-defined]
    cmd = commands.calls[0]["cmd"]
    assert isinstance(cmd, str)
    assert base64.b64encode(b"\x00\x01\x02\x03").decode("ascii") in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    commands = _FakeCommands(results=[_FakeResult(stderr="boom", exit_code=1)])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=tmp_path)
    with pytest.raises(ExecFailed):
        handle.copy_file_in(src, Path("/workspace/dst"))  # type: ignore[attr-defined]


def test_handle_close_kills_sandbox(tmp_path: Path) -> None:
    sandbox = _FakeSandbox(commands=_FakeCommands(results=[]))
    handle = _handle(sandbox, host=tmp_path)
    handle.close()  # type: ignore[attr-defined]
    assert sandbox.killed is True


def test_handle_close_never_raises(tmp_path: Path) -> None:
    @dataclass
    class _RaisingSandbox:
        commands: _FakeCommands

        def kill(self) -> None:
            raise RuntimeError("teardown failed")

    sandbox = _RaisingSandbox(commands=_FakeCommands(results=[]))
    handle = _handle(sandbox, host=tmp_path)  # type: ignore[arg-type]
    handle.close()  # type: ignore[attr-defined]  # must not raise


def test_finalize_no_changes_returns_applied_true(tmp_path: Path) -> None:
    # snapshot call returns empty stdout → no files → equals empty baseline.
    commands = _FakeCommands(results=[_FakeResult(stdout="", exit_code=0)])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=tmp_path, baseline={})
    fr = handle.finalize(target=tmp_path)  # type: ignore[attr-defined]
    assert fr.applied is True
    assert fr.files_changed == ()


def test_finalize_pulls_added_files_to_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    # 1st run: snapshot lists new.txt; 2nd run: base64 of its contents.
    commands = _FakeCommands(
        results=[
            _FakeResult(stdout="abc123  ./new.txt\n", exit_code=0),
            _FakeResult(stdout=base64.b64encode(b"hello").decode("ascii"), exit_code=0),
        ]
    )
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=target, baseline={})
    fr = handle.finalize(target=target)  # type: ignore[attr-defined]
    assert fr.applied is True
    assert (target / "new.txt").read_bytes() == b"hello"
    assert Path("new.txt") in fr.files_changed


def test_finalize_propagates_deletes(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "gone.txt").write_text("bye", encoding="utf-8")
    commands = _FakeCommands(results=[_FakeResult(stdout="", exit_code=0)])
    sandbox = _FakeSandbox(commands=commands)
    handle = _handle(sandbox, host=target, baseline={Path("gone.txt"): "old"})
    fr = handle.finalize(target=target)  # type: ignore[attr-defined]
    assert fr.applied is True
    assert not (target / "gone.txt").exists()

"""Verify the forkd provider factory + _ForkdHandle methods.

forkd is Linux + KVM only and the SDK is imported lazily, so these unit tests
never import the real ``forkd`` package: they inject a fake E2B-compatible
sandbox via ``sandbox_factory=`` and run anywhere.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy, ExecResult
from eden.sandboxes.errors import ProviderUnavailable
from eden.sandboxes.forkd import provider as forkd_provider
from tests.unit.forkd_provider_helpers import FakeCommands, FakeResult, FakeSandbox, handle, opts

pytestmark = pytest.mark.unit


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
        p.create(opts(tmp_path))
    assert excinfo.value.provider == "forkd"


def test_create_uploads_tree_and_snapshots_baseline(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    # First call: upload of hello.txt. Second call: the find/sha256sum snapshot.
    commands = FakeCommands(
        results=[
            FakeResult(exit_code=0),
            FakeResult(stdout="abc123  ./hello.txt\n", exit_code=0),
        ]
    )
    sandbox = FakeSandbox(commands=commands)
    p = forkd_provider(sandbox_factory=lambda: sandbox)
    h = p.create(opts(tmp_path))
    assert h.baseline == {Path("hello.txt"): "abc123"}  # type: ignore[attr-defined]
    # Upload command carried the base64 of the file contents.
    upload_cmd = commands.calls[0]["cmd"]
    assert isinstance(upload_cmd, str)
    assert base64.b64encode(b"hi").decode("ascii") in upload_cmd


def test_create_kills_sandbox_on_upload_failure(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    commands = FakeCommands(results=[FakeResult(stderr="disk full", exit_code=1)])
    sandbox = FakeSandbox(commands=commands)
    p = forkd_provider(sandbox_factory=lambda: sandbox)
    with pytest.raises(RuntimeError):
        p.create(opts(tmp_path))
    assert sandbox.killed is True


def test_handle_exec_returns_exec_result(tmp_path: Path) -> None:
    commands = FakeCommands(results=[FakeResult(stdout="hello\n", exit_code=0)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    result = h.exec("echo hello")  # type: ignore[attr-defined]
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    assert commands.calls[0]["cmd"] == "echo hello"
    assert commands.calls[0]["timeout"] == 60.0


def test_handle_exec_merges_env(tmp_path: Path) -> None:
    commands = FakeCommands(results=[FakeResult()])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path, env={"BASE": "1"})
    h.exec("env", env={"EXTRA": "2"})  # type: ignore[attr-defined]
    assert commands.calls[0]["envs"] == {"BASE": "1", "EXTRA": "2"}
    assert commands.calls[0]["cwd"] is None


def test_handle_exec_prefixes_cwd_into_command(tmp_path: Path) -> None:
    commands = FakeCommands(results=[FakeResult()])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    h.exec("pwd", cwd=Path("/workspace/sub"))  # type: ignore[attr-defined]
    cmd = commands.calls[0]["cmd"]
    assert isinstance(cmd, str)
    assert cmd.startswith("cd /workspace/sub && (pwd)")
    assert commands.calls[0]["cwd"] is None


def test_handle_exec_wraps_stdin_as_base64(tmp_path: Path) -> None:
    commands = FakeCommands(results=[FakeResult()])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    h.exec("cat", stdin="payload")  # type: ignore[attr-defined]
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
        def run(self, cmd: str, **_kw: object) -> FakeResult:
            raise _ExitError()

    sandbox = FakeSandbox(commands=_RaisingCommands())  # type: ignore[arg-type]
    h = handle(sandbox, host=tmp_path)
    result = h.exec("false")  # type: ignore[attr-defined]
    assert result.exit_code == 7
    assert result.stderr == "boom"


def test_handle_exec_transport_failure_returns_neg_one(tmp_path: Path) -> None:
    @dataclass
    class _RaisingCommands:
        def run(self, cmd: str, **_kw: object) -> FakeResult:
            raise RuntimeError("vm gone")

    sandbox = FakeSandbox(commands=_RaisingCommands())  # type: ignore[arg-type]
    h = handle(sandbox, host=tmp_path)
    result = h.exec("anything")  # type: ignore[attr-defined]
    assert result.exit_code == -1
    assert "vm gone" in result.stderr

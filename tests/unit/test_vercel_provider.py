"""Verify vercel provider factory + _VercelHandle methods (no finalize yet)."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import BranchStrategy, CreateOptions, ExecResult
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable
from eden.sandboxes.vercel import provider as vercel_provider

pytestmark = pytest.mark.unit


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="test",
    )


def _mock_client(
    post_returns: dict[str, object] | list[dict[str, object]] | None = None,
) -> MagicMock:
    """Build a MagicMock(spec=RestClient) whose post() returns canned data."""
    client = MagicMock(spec=RestClient)
    if isinstance(post_returns, list):
        client.post.side_effect = post_returns
    elif post_returns is not None:
        client.post.return_value = post_returns
    return client


def test_provider_kind_and_name() -> None:
    p = vercel_provider(access_token="test-token")
    assert p.kind == "isolated"
    assert p.name == "vercel"


def test_provider_supports_default_strategies() -> None:
    p = vercel_provider(access_token="test-token")
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_raises_when_no_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    p = vercel_provider()
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == "vercel"


def test_create_reads_token_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VERCEL_TOKEN", "env-token")
    captured_headers: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_headers.update(kw["headers"])  # type: ignore[call-overload]
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider()
    p.create(_opts(tmp_path))
    assert captured_headers["Authorization"] == "Bearer env-token"


def test_create_uses_explicit_base_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_url: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_url["base_url"] = str(kw["base_url"])
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", base_url="https://vercel.local")
    p.create(_opts(tmp_path))
    assert captured_url["base_url"] == "https://vercel.local"


def test_create_posts_sandbox_with_runtime_and_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_payload: dict[str, object] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            self.post = MagicMock(side_effect=self._post)
            self.close = MagicMock()
            self.delete = MagicMock()

        def _post(self, path: str, *, json: object, params: object = None) -> dict[str, object]:
            if path == "/v1/sandboxes":
                captured_payload["payload"] = json
                return {"id": "sb-9"}
            return {"stdout": "", "stderr": "", "exit_code": 0}

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", runtime="python313", env={"FOO": "bar"})
    p.create(_opts(tmp_path))
    payload = captured_payload["payload"]
    assert isinstance(payload, dict)
    assert payload["runtime"] == "python313"
    assert payload["env"] == {"FOO": "bar"}
    assert payload["name"] == "test"


def test_team_id_threaded_as_query_param(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_calls: list[dict[str, object]] = []

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            self.post = MagicMock(side_effect=self._post)
            self.close = MagicMock()
            self.delete = MagicMock(side_effect=self._delete)

        def _post(self, path: str, *, json: object, params: object = None) -> dict[str, object]:
            captured_calls.append({"path": path, "params": params})
            if path == "/v1/sandboxes":
                return {"id": "sb-7"}
            return {"stdout": "", "stderr": "", "exit_code": 0}

        def _delete(self, path: str, *, params: object = None) -> None:
            captured_calls.append({"path": path, "params": params, "method": "DELETE"})

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", team_id="team-42")
    p.create(_opts(tmp_path))
    for call in captured_calls:
        assert call["params"] == {"teamId": "team-42"}, f"call {call} missing teamId"


def test_handle_exec_returns_exec_result() -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = _mock_client(
        {"stdout": "hello\n", "stderr": "", "exit_code": 0},
    )
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    result = handle.exec("echo hello")
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    args, kwargs = client.post.call_args
    assert args[0] == "/v1/sandboxes/sb-1/exec"
    assert kwargs["json"]["command"] == "echo hello"


def test_handle_exec_returns_neg_one_on_rest_failure() -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    result = handle.exec("anything")
    assert result.exit_code == -1
    assert "network down" in result.stderr


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    handle.copy_file_in(src, Path("/workspace/dst.bin"))
    _args, kwargs = client.post.call_args
    cmd = kwargs["json"]["command"]
    expected_b64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
    assert expected_b64 in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    client = _mock_client({"stdout": "", "stderr": "boom", "exit_code": 1})
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    with pytest.raises(ExecFailed):
        handle.copy_file_in(src, Path("/workspace/dst"))


def test_handle_close_deletes_sandbox() -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    handle.close()
    client.delete.assert_called_once_with("/v1/sandboxes/sb-1", params=None)
    client.close.assert_called_once()


def test_handle_close_idempotent_on_not_found() -> None:
    from eden.errors import RestNotFoundError
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    client.delete.side_effect = RestNotFoundError(
        message="404",
        status=404,
        url="https://x/v1/sandboxes/sb-1",
    )
    handle = _VercelHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
        team_id=None,
    )
    handle.close()
    client.close.assert_called_once()

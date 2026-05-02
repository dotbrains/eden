"""Verify daytona provider factory + _DaytonaHandle methods (no finalize yet)."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import BranchStrategy, CreateOptions, ExecResult
from eden.sandboxes.daytona import provider as daytona_provider
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable

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
    p = daytona_provider(api_key="test-key")
    assert p.kind == "isolated"
    assert p.name == "daytona"


def test_provider_supports_default_strategies() -> None:
    p = daytona_provider(api_key="test-key")
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_raises_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    p = daytona_provider()  # no api_key arg, no env var
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == "daytona"


def test_create_reads_api_key_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DAYTONA_API_KEY", "env-key")
    captured_headers: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_headers.update(kw["headers"])  # type: ignore[call-overload]
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider()
    p.create(_opts(tmp_path))
    assert captured_headers["Authorization"] == "Bearer env-key"


def test_create_threads_organization_id_header(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_headers: dict[str, str] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            captured_headers.update(kw["headers"])  # type: ignore[call-overload]
            self.post = MagicMock(return_value={"id": "sb-1"})
            self.close = MagicMock()
            self.delete = MagicMock()

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider(api_key="k", organization_id="org-7")
    p.create(_opts(tmp_path))
    assert captured_headers["X-Daytona-Organization-ID"] == "org-7"


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

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider(api_key="k", base_url="https://daytona.local")
    p.create(_opts(tmp_path))
    assert captured_url["base_url"] == "https://daytona.local"


def test_create_posts_sandbox_with_image_and_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_payload: dict[str, object] = {}

    class _ClientFactory:
        def __init__(self, **kw: object) -> None:
            self.post = MagicMock(side_effect=self._post)
            self.close = MagicMock()
            self.delete = MagicMock()

        def _post(self, path: str, *, json: object) -> dict[str, object]:
            if path == "/api/sandbox":
                captured_payload["payload"] = json
                return {"id": "sb-9"}
            # Any subsequent _upload_tree / _snapshot_remote calls return success.
            return {"stdout": "", "stderr": "", "exit_code": 0}

    monkeypatch.setattr("eden.sandboxes.daytona.RestClient", _ClientFactory)
    p = daytona_provider(api_key="k", image="ubuntu:22.04", env={"FOO": "bar"})
    p.create(_opts(tmp_path))
    payload = captured_payload["payload"]
    assert isinstance(payload, dict)
    assert payload["image"] == "ubuntu:22.04"
    assert payload["env"] == {"FOO": "bar"}
    assert payload["name"] == "test"  # name_hint


def test_handle_exec_returns_exec_result() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = _mock_client(
        {"stdout": "hello\n", "stderr": "", "exit_code": 0},
    )
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    result = handle.exec("echo hello")
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert args[0] == "/toolbox/sb-1/process/execute"
    assert kwargs["json"]["command"] == "echo hello"


def test_handle_exec_returns_neg_one_on_rest_failure() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    result = handle.exec("anything")
    assert result.exit_code == -1
    assert "network down" in result.stderr


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    client = _mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.copy_file_in(src, Path("/workspace/dst.bin"))
    _args, kwargs = client.post.call_args
    cmd = kwargs["json"]["command"]
    expected_b64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
    assert expected_b64 in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    client = _mock_client({"stdout": "", "stderr": "boom", "exit_code": 1})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    with pytest.raises(ExecFailed):
        handle.copy_file_in(src, Path("/workspace/dst"))


def test_handle_close_deletes_sandbox() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.close()
    client.delete.assert_called_once_with("/api/sandbox/sb-1")
    client.close.assert_called_once()


def test_handle_close_idempotent_on_not_found() -> None:
    from eden.errors import RestNotFoundError
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.delete.side_effect = RestNotFoundError(
        message="404",
        status=404,
        url="https://x/api/sandbox/sb-1",
    )
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.close()  # must not raise
    client.close.assert_called_once()

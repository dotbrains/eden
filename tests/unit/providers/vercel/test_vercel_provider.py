"""Verify vercel provider factory behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.errors import ProviderUnavailable
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
            self.post = MagicMock(
                return_value={
                    "sandbox": {"name": "sb-1"},
                    "session": {"id": "sess-1"},
                    "routes": [],
                }
            )
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
            self.post = MagicMock(
                return_value={
                    "sandbox": {"name": "sb-1"},
                    "session": {"id": "sess-1"},
                    "routes": [],
                }
            )
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
            if path == "/v4/sandboxes":
                captured_payload["payload"] = json
                return {
                    "sandbox": {"name": "sb-9"},
                    "session": {"id": "sess-9"},
                    "routes": [],
                }
            return {"stdout": "", "stderr": "", "exitCode": 0}

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
            if path == "/v4/sandboxes":
                return {
                    "sandbox": {"name": "sb-7"},
                    "session": {"id": "sess-7"},
                    "routes": [],
                }
            return {"stdout": "", "stderr": "", "exitCode": 0}

        def _delete(self, path: str, *, params: object = None) -> None:
            captured_calls.append({"path": path, "params": params, "method": "DELETE"})

    monkeypatch.setattr("eden.sandboxes.vercel.RestClient", _ClientFactory)
    p = vercel_provider(access_token="t", team_id="team-42")
    p.create(_opts(tmp_path))
    for call in captured_calls:
        assert call["params"] == {"teamId": "team-42"}, f"call {call} missing teamId"

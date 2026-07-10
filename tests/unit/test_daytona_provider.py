"""Verify daytona provider factory behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.daytona import provider as daytona_provider
from eden.sandboxes.errors import ProviderUnavailable

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

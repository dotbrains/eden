"""Daytona live-API integration test.

Gated on ``DAYTONA_API_KEY``: skipped when the env var is unset, so the
test is safe to include in the default integration suite. When the key
*is* present, hits ``https://api.daytona.io`` (overridable via
``DAYTONA_API_URL``) and exercises the full provider lifecycle:

* create → exec → copy_file_in (file + directory) → copy_file_out →
  finalize → close.
* stdin delivery (verifies the base64 wrap that the REST shell needs).
* idempotent close (second close after sandbox is already gone does
  not raise).

Each sandbox spin-up is real money, so the read/exec/copy tests share a
single session-scoped sandbox via the ``daytona_handle`` fixture. The
lifecycle test (``test_close_is_idempotent``) creates its own short-lived
sandbox so the assertion about post-close state is clean.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes.daytona import provider as daytona_provider
from eden.sandboxes.errors import ProviderUnavailable

pytestmark = pytest.mark.integration


def _require_credentials() -> str:
    """Return the api key from the env, or skip the test cleanly."""
    key = os.environ.get("DAYTONA_API_KEY")
    if not key:
        pytest.skip("DAYTONA_API_KEY not set; skipping Daytona integration tests")
    return key


@pytest.fixture(scope="session")
def daytona_provider_factory() -> SandboxProvider:
    _require_credentials()
    return daytona_provider()


def _opts(*, worktree_path: Path, name_hint: str) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=worktree_path,
        host_repo_path=worktree_path,
        env={},
        mounts=(),
        name_hint=name_hint,
    )


@pytest.fixture(scope="session")
def daytona_handle(
    daytona_provider_factory: SandboxProvider,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[IsolatedSandboxHandle]:
    """Single sandbox shared across the read/exec/copy tests.

    Each spin-up costs real Daytona time. Tests that depend on this
    fixture must namespace any files they write under ``/workspace`` to
    avoid bleeding state into one another.
    """
    seed_dir = tmp_path_factory.mktemp("daytona-seed")
    (seed_dir / "seed.txt").write_text("hello from host\n")
    name_hint = f"eden-it-{uuid.uuid4().hex[:8]}"
    handle = daytona_provider_factory.create(_opts(worktree_path=seed_dir, name_hint=name_hint))
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        yield handle
    finally:
        handle.close()


def test_initial_upload_visible_in_sandbox(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    """Files present in the host worktree at create-time land in /workspace."""
    result = daytona_handle.exec("cat /workspace/seed.txt")
    assert result.exit_code == 0, result.stderr
    assert "hello from host" in result.stdout


def test_exec_returns_stdout_and_exit_code(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    result = daytona_handle.exec("printf hello && exit 0")
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_exec_nonzero_exit_propagates(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    result = daytona_handle.exec("exit 7")
    assert result.exit_code == 7


def test_exec_with_stdin_payload(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    """The base64-wrap path used to feed stdin to a remote shell command."""
    result = daytona_handle.exec("cat", stdin="payload-via-stdin\n")
    assert result.exit_code == 0
    assert "payload-via-stdin" in result.stdout


def test_copy_file_in_round_trip(
    daytona_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    src = tmp_path / "in.txt"
    src.write_text("copy_in worked\n")
    target = Path("/workspace/copies/in.txt")  # parent doesn't exist yet
    daytona_handle.copy_file_in(src, target)

    result = daytona_handle.exec(f"cat {target.as_posix()}")
    assert result.exit_code == 0
    assert "copy_in worked" in result.stdout


def test_copy_file_in_directory(
    daytona_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    """Directory upload uses the tar+base64 helper shared with Vercel."""
    src_dir = tmp_path / "fixtures"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("alpha\n")
    (src_dir / "nested").mkdir()
    (src_dir / "nested" / "b.txt").write_text("beta\n")
    target = Path("/workspace/dir-fixture")
    daytona_handle.copy_file_in(src_dir, target)

    a = daytona_handle.exec(f"cat {target.as_posix()}/a.txt")
    b = daytona_handle.exec(f"cat {target.as_posix()}/nested/b.txt")
    assert "alpha" in a.stdout
    assert "beta" in b.stdout


def test_copy_file_out_round_trip(
    daytona_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    # Create a file in the sandbox, then pull it back to the host.
    sandbox_path = Path(f"/workspace/out-{uuid.uuid4().hex[:6]}.txt")
    write = daytona_handle.exec(
        f"printf 'copy_out worked' > {sandbox_path.as_posix()}",
    )
    assert write.exit_code == 0, write.stderr

    dest = tmp_path / "out.txt"
    daytona_handle.copy_file_out(sandbox_path, dest)
    assert dest.read_text() == "copy_out worked"


def test_finalize_propagates_sandbox_changes(
    daytona_provider_factory: SandboxProvider,
    tmp_path: Path,
) -> None:
    """A fresh sandbox + an added file + finalize → host target sees the file.

    Uses its own sandbox (not the session-scoped one) so the baseline
    snapshot is clean and the diff is unambiguous.
    """
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "preexisting.txt").write_text("base\n")

    target = tmp_path / "target"
    target.mkdir()
    # Pre-seed target with the same baseline so finalize's diff has a
    # clean before/after surface to compare against.
    (target / "preexisting.txt").write_text("base\n")

    handle = daytona_provider_factory.create(
        _opts(worktree_path=seed, name_hint=f"eden-it-fin-{uuid.uuid4().hex[:6]}")
    )
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        write = handle.exec("printf 'added via sandbox' > /workspace/new.txt")
        assert write.exit_code == 0, write.stderr

        result = handle.finalize(target)
        assert result.applied is True
        assert Path("new.txt") in result.files_changed
    finally:
        handle.close()

    landed = target / "new.txt"
    assert landed.read_text() == "added via sandbox"


def test_close_is_idempotent(
    daytona_provider_factory: SandboxProvider,
    tmp_path: Path,
) -> None:
    """Calling close() twice is safe (matches docker/podman semantics)."""
    seed = tmp_path / "seed"
    seed.mkdir()
    handle = daytona_provider_factory.create(
        _opts(worktree_path=seed, name_hint=f"eden-it-cls-{uuid.uuid4().hex[:6]}")
    )
    handle.close()
    # Second close should silently no-op (RestNotFoundError swallowed).
    handle.close()


def test_missing_credentials_raises_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The credential check raises lazily at create() time, not factory time."""
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    # Construct the provider WITHOUT calling _require_credentials — we
    # are exercising the unconfigured path on purpose.
    p = daytona_provider(api_key=None)
    seed = tmp_path / "seed"
    seed.mkdir()
    with pytest.raises(ProviderUnavailable) as exc:
        p.create(_opts(worktree_path=seed, name_hint="eden-it-noauth"))
    assert exc.value.provider == "daytona"

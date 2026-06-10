"""forkd live-SDK integration test.

Double-gated, so it is safe to include in the default integration suite:

* The ``forkd`` SDK must be importable (it is Linux + KVM only, so this skips
  on macOS/Windows and anywhere the optional dependency is not installed).
* ``FORKD_SNAPSHOT`` must name a warm snapshot tag the local forkd controller
  can fork from — the readiness signal, analogous to Daytona's
  ``DAYTONA_API_KEY``. Set it only when a forkd controller is running (default
  ``http://127.0.0.1:8889``) and the snapshot exists.

When both hold, this forks a real microVM and exercises the full provider
lifecycle: create → exec → copy_file_in (file + directory) → copy_file_out →
finalize → close, plus stdin delivery (the base64 wrap) and idempotent close.

Each fork is cheap (that is forkd's whole point), but the read/exec/copy tests
still share one session-scoped sandbox; the finalize and close tests fork their
own short-lived VMs so their baseline/teardown assertions stay unambiguous.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes.forkd import provider as forkd_provider

pytestmark = pytest.mark.integration


def _require_forkd() -> str:
    """Return the snapshot tag from the env, or skip the test cleanly."""
    try:
        import forkd  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        pytest.skip("forkd SDK not importable; skipping forkd integration tests")
    snapshot = os.environ.get("FORKD_SNAPSHOT")
    if not snapshot:
        pytest.skip("FORKD_SNAPSHOT not set; skipping forkd integration tests")
    return snapshot


@pytest.fixture(scope="session")
def forkd_provider_factory() -> SandboxProvider:
    snapshot = _require_forkd()
    return forkd_provider(snapshot=snapshot)


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
def forkd_handle(
    forkd_provider_factory: SandboxProvider,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[IsolatedSandboxHandle]:
    """Single microVM shared across the read/exec/copy tests.

    Tests that depend on this fixture must namespace any files they write
    under ``/workspace`` to avoid bleeding state into one another.
    """
    seed_dir = tmp_path_factory.mktemp("forkd-seed")
    (seed_dir / "seed.txt").write_text("hello from host\n")
    name_hint = f"eden-it-{uuid.uuid4().hex[:8]}"
    handle = forkd_provider_factory.create(_opts(worktree_path=seed_dir, name_hint=name_hint))
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        yield handle
    finally:
        handle.close()


def test_initial_upload_visible_in_sandbox(
    forkd_handle: IsolatedSandboxHandle,
) -> None:
    """Files present in the host worktree at create-time land in /workspace."""
    result = forkd_handle.exec("cat /workspace/seed.txt")
    assert result.exit_code == 0, result.stderr
    assert "hello from host" in result.stdout


def test_exec_returns_stdout_and_exit_code(
    forkd_handle: IsolatedSandboxHandle,
) -> None:
    result = forkd_handle.exec("printf hello && exit 0")
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_exec_nonzero_exit_propagates(
    forkd_handle: IsolatedSandboxHandle,
) -> None:
    result = forkd_handle.exec("exit 7")
    assert result.exit_code == 7


def test_exec_with_stdin_payload(
    forkd_handle: IsolatedSandboxHandle,
) -> None:
    """The base64-wrap path used to feed stdin to an in-guest shell command."""
    result = forkd_handle.exec("cat", stdin="payload-via-stdin\n")
    assert result.exit_code == 0
    assert "payload-via-stdin" in result.stdout


def test_copy_file_in_round_trip(
    forkd_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    src = tmp_path / "in.txt"
    src.write_text("copy_in worked\n")
    target = Path("/workspace/copies/in.txt")  # parent doesn't exist yet
    forkd_handle.copy_file_in(src, target)

    result = forkd_handle.exec(f"cat {target.as_posix()}")
    assert result.exit_code == 0
    assert "copy_in worked" in result.stdout


def test_copy_file_in_directory(
    forkd_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    """Directory upload uses the tar+base64 helper shared with the cloud providers."""
    src_dir = tmp_path / "fixtures"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("alpha\n")
    (src_dir / "nested").mkdir()
    (src_dir / "nested" / "b.txt").write_text("beta\n")
    target = Path("/workspace/dir-fixture")
    forkd_handle.copy_file_in(src_dir, target)

    a = forkd_handle.exec(f"cat {target.as_posix()}/a.txt")
    b = forkd_handle.exec(f"cat {target.as_posix()}/nested/b.txt")
    assert "alpha" in a.stdout
    assert "beta" in b.stdout


def test_copy_file_out_round_trip(
    forkd_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    # Create a file in the sandbox, then pull it back to the host.
    sandbox_path = Path(f"/workspace/out-{uuid.uuid4().hex[:6]}.txt")
    write = forkd_handle.exec(
        f"printf 'copy_out worked' > {sandbox_path.as_posix()}",
    )
    assert write.exit_code == 0, write.stderr

    dest = tmp_path / "out.txt"
    forkd_handle.copy_file_out(sandbox_path, dest)
    assert dest.read_text() == "copy_out worked"


def test_finalize_propagates_sandbox_changes(
    forkd_provider_factory: SandboxProvider,
    tmp_path: Path,
) -> None:
    """A fresh microVM + an added file + finalize → host target sees the file.

    Uses its own sandbox (not the session-scoped one) so the baseline
    snapshot is clean and the diff is unambiguous.
    """
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "preexisting.txt").write_text("base\n")

    target = tmp_path / "target"
    target.mkdir()
    # Pre-seed target with the same baseline so finalize's diff has a clean
    # before/after surface to compare against.
    (target / "preexisting.txt").write_text("base\n")

    handle = forkd_provider_factory.create(
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
    forkd_provider_factory: SandboxProvider,
    tmp_path: Path,
) -> None:
    """Calling close() twice is safe (matches docker/podman/cloud semantics)."""
    seed = tmp_path / "seed"
    seed.mkdir()
    handle = forkd_provider_factory.create(
        _opts(worktree_path=seed, name_hint=f"eden-it-cls-{uuid.uuid4().hex[:6]}")
    )
    handle.close()
    # Second close should silently no-op (kill() failure swallowed).
    handle.close()

# Eden Phase 4a — Provider Parity (Local) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land local sandbox-provider parity: `podman` (sibling of `docker`), local `isolated` (carved-copy + patch-sync) provider, the `IsolatedSandboxHandle` Protocol, the `FinalizeResult` typed result, the `make_isolated_provider` helper, and the shared `make_container_provider` helper that turns docker + podman into 5-line factories.

**Architecture:** Extract Phase 2's docker implementation into a shared `eden/providers/_impl/container.py` module (`make_container_provider`); `docker` and `podman` become thin factories over it. Add `eden/providers/_impl/patch_sync.py` with three pure functions (`snapshot`, `diff`, `apply`) that the new local `isolated` provider uses. Wire `_AgentRunner.cwd` plumbing and a post-iteration `handle.finalize()` call into `_run_loop`. No new threads.

**Tech Stack:** Python 3.11+, stdlib only (`subprocess`, `shutil`, `hashlib`, `pathlib`). Re-uses Phase 2's `make_bind_mount_provider`, Phase 2/3a's `_AgentRunner`, `stream_exec`, error hierarchy. No new pip dependencies. CI matrix unchanged: 3 OS × 3 Python versions; podman integration tests gated to Linux.

**Reference spec:** `docs/superpowers/specs/2026-05-01-eden-phase4a-provider-parity-local-design.md`

**Phase 3b base:** This plan assumes commit `ddffc73` is on `main` (Phase 3a + 3b complete). Baseline: 292 unit+e2e tests passing, mypy strict clean across 113 source files, ruff clean, coverage 94.54%.

---

## File structure produced by this plan

```
eden/
├── providers/
│   ├── _types.py                    # MODIFY — add FinalizeResult
│   ├── _protocols.py                # MODIFY — add IsolatedSandboxHandle Protocol
│   ├── _helpers.py                  # MODIFY — add make_isolated_provider
│   └── _impl/                       # NEW directory
│       ├── __init__.py              # NEW (empty)
│       ├── container.py             # NEW — make_container_provider + _ContainerHandle
│       └── patch_sync.py            # NEW — DiffResult, snapshot, diff, apply
├── sandboxes/
│   ├── docker/__init__.py           # MODIFY — thin factory over make_container_provider
│   ├── podman/                      # NEW directory
│   │   └── __init__.py              # NEW — thin factory over make_container_provider
│   └── isolated/                    # NEW directory
│       └── __init__.py              # NEW — isolated.provider() + _IsolatedHandle
├── orchestrator/
│   ├── _runner.py                   # MODIFY — add optional cwd kwarg to _AgentRunner
│   └── _loop.py                     # MODIFY — pass cwd, call handle.finalize() on success
└── __init__.py                      # MODIFY — re-export FinalizeResult + IsolatedSandboxHandle

tests/
├── unit/
│   ├── test_finalize_result_types.py    # NEW — FinalizeResult/IsolatedSandboxHandle shape
│   ├── test_container_provider.py       # NEW — mocked argv tests, parametrized over binary
│   ├── test_podman_provider.py          # NEW — small podman factory tests
│   ├── test_patch_sync.py               # NEW — snapshot/diff/apply unit tests
│   ├── test_isolated_provider.py        # NEW — isolated factory + handle lifecycle
│   └── test_agent_runner_cwd.py         # NEW — _AgentRunner.cwd kwarg behavior
├── integration/
│   └── test_podman.py                   # NEW — Linux-gated real-podman tests
└── e2e/
    └── test_isolated_smoke.py           # NEW — full simulated_agent + isolated + finalize

README.md                                # MODIFY — bump status to phase 4a complete
```

**File responsibilities:**

- `eden/providers/_types.py` — adds `FinalizeResult(applied: bool, files_changed: tuple[Path, ...], patch_size_bytes: int)` (frozen dataclass).
- `eden/providers/_protocols.py` — adds `IsolatedSandboxHandle(SandboxHandle, Protocol)` declaring `finalize(target: Path) -> FinalizeResult`.
- `eden/providers/_helpers.py` — adds `_IsolatedProvider` dataclass + `make_isolated_provider(name, create, *, supported_strategies=...)` factory mirroring `make_bind_mount_provider`. Wraps a `create` function into a `SandboxProvider` with `kind="isolated"`.
- `eden/providers/_impl/container.py` — `make_container_provider(*, binary, image, mounts, env, network) -> SandboxProvider`. Internal `_ContainerHandle` dataclass carries `binary: str` and dispatches every subprocess call through it. Replaces the body of Phase 2's `eden/sandboxes/docker/__init__.py:106-168`.
- `eden/providers/_impl/patch_sync.py` — `snapshot(root, *, ignore=...) -> dict[Path, str]`, `DiffResult` frozen dataclass, `diff(*, before, after) -> DiffResult`, `apply(diff_result, *, src, dst) -> FinalizeResult`. SHA-256 over file contents; `.git` and `.eden` ignored at top level.
- `eden/sandboxes/docker/__init__.py` — refactored to a 5-line factory that calls `make_container_provider(binary="docker", ...)`.
- `eden/sandboxes/podman/__init__.py` — same shape, `binary="podman"`.
- `eden/sandboxes/isolated/__init__.py` — `provider(*, base_dir=None)` + `_IsolatedHandle` (carries `worktree_path`, `host_worktree_path`, `baseline` snapshot). `finalize(target)` runs the patch_sync apply.
- `eden/orchestrator/_runner.py` — `_AgentRunner.__init__` gains `cwd: Path | None = None`; `__enter__` passes through to `subprocess.Popen`.
- `eden/orchestrator/_loop.py` — computes `agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None` and passes it to `_AgentRunner`. After the iteration loop's success path, calls `handle.finalize(target=wt.host_repo_path)` if `hasattr(handle, "finalize")`; emits a synthetic `text` event with the finalize summary.
- `eden/__init__.py` — adds `FinalizeResult` and `IsolatedSandboxHandle` to the top-level public surface.

---

## Pre-flight: confirm Phase 3b baseline

- [ ] **Step 1: Confirm working tree clean and on main**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
  git status -s && git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expected: empty status, branch `main`, commit `bb23464 docs: add phase 4a ...` (or later).

- [ ] **Step 2: Confirm Phase 3b suite passes**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
  .venv/bin/pytest -m "unit or e2e" --no-cov -q 2>&1 | tail -3
```
Expected: `292 passed` (Phase 3b baseline). If lower, stop and investigate.

No commit at this step — sanity check only.

---

## Task 1: Add FinalizeResult + IsolatedSandboxHandle Protocol + make_isolated_provider

**Files:**
- Modify: `eden/providers/_types.py`
- Modify: `eden/providers/_protocols.py`
- Modify: `eden/providers/_helpers.py`
- Create: `tests/unit/test_finalize_result_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_finalize_result_types.py`:

```python
"""Verify FinalizeResult + IsolatedSandboxHandle Protocol shape."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from eden.providers._helpers import make_isolated_provider
from eden.providers._protocols import IsolatedSandboxHandle, SandboxHandle
from eden.providers._types import BranchStrategy, CreateOptions, FinalizeResult

pytestmark = pytest.mark.unit


def test_finalize_result_is_frozen() -> None:
    fr = FinalizeResult(applied=True, files_changed=(Path("a"),), patch_size_bytes=42)
    with pytest.raises(FrozenInstanceError):
        fr.applied = False  # type: ignore[misc]


def test_finalize_result_field_shape() -> None:
    fr = FinalizeResult(
        applied=True,
        files_changed=(Path("src/x.py"), Path("README.md")),
        patch_size_bytes=128,
    )
    assert fr.applied is True
    assert fr.files_changed == (Path("src/x.py"), Path("README.md"))
    assert fr.patch_size_bytes == 128


def test_isolated_sandbox_handle_is_runtime_checkable() -> None:
    """A class with the right shape passes isinstance(x, IsolatedSandboxHandle)."""

    class _Conforming:
        worktree_path = Path("/tmp/x")

        def exec(self, cmd: str, **_kw: object) -> object: ...
        def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
        def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
        def close(self) -> None: ...
        def finalize(self, target: Path) -> FinalizeResult:
            return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

    assert isinstance(_Conforming(), IsolatedSandboxHandle)
    assert isinstance(_Conforming(), SandboxHandle)


def test_sandbox_handle_without_finalize_is_not_isolated() -> None:
    class _BindMount:
        worktree_path = Path("/tmp/x")
        def exec(self, cmd: str, **_kw: object) -> object: ...
        def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
        def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
        def close(self) -> None: ...

    assert isinstance(_BindMount(), SandboxHandle)
    assert not isinstance(_BindMount(), IsolatedSandboxHandle)


def test_make_isolated_provider_returns_isolated_kind() -> None:
    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        raise NotImplementedError

    p = make_isolated_provider(name="local", create=_create)
    assert p.name == "local"
    assert p.kind == "isolated"


def test_make_isolated_provider_supports_default_strategies() -> None:
    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        raise NotImplementedError

    p = make_isolated_provider(name="local", create=_create)
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_make_isolated_provider_supported_strategies_filter() -> None:
    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        raise NotImplementedError

    p = make_isolated_provider(
        name="local",
        create=_create,
        supported_strategies=frozenset({"head"}),
    )
    assert p.supports_strategy(BranchStrategy.head())
    assert not p.supports_strategy(BranchStrategy.merge_to_head())
```

- [ ] **Step 2: Run test to verify it fails**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_finalize_result_types.py -v`
Expected: FAIL — `FinalizeResult`, `IsolatedSandboxHandle`, `make_isolated_provider` not importable.

- [ ] **Step 3: Add FinalizeResult to `eden/providers/_types.py`**

Append at the end of `eden/providers/_types.py`:

```python


@dataclass(frozen=True)
class FinalizeResult:
    """Summary of what `IsolatedSandboxHandle.finalize()` applied to the target.

    `applied=True` means every detected change was successfully replayed onto
    the target. `False` means at least one file copy or unlink failed —
    failures are logged but ``apply`` continues with remaining files.
    """

    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

- [ ] **Step 4: Add IsolatedSandboxHandle to `eden/providers/_protocols.py`**

Append at the end of `eden/providers/_protocols.py`:

```python


@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    """A SandboxHandle whose state is replicated to the host on close via
    a `finalize(target)` call. Cloud and local "isolated" providers implement
    this; bind-mount providers (docker, podman, no_sandbox) do not.

    The orchestrator detects this Protocol via ``hasattr(handle, "finalize")``;
    the runtime-checkable Protocol exists for type-checker narrowing.
    """

    def finalize(self, target: Path) -> FinalizeResult: ...
```

You will also need to add `FinalizeResult` to the imports at the top of `_protocols.py`:

```python
from eden.providers._types import FinalizeResult
```

(Confirm the import doesn't cause a circular dependency — `_types.py` does not import from `_protocols.py` in Phase 2; if you find a cycle, declare `FinalizeResult` in a forward reference and `from __future__ import annotations` covers it.)

- [ ] **Step 5: Add make_isolated_provider to `eden/providers/_helpers.py`**

Append at the end of `eden/providers/_helpers.py`:

```python


@dataclass
class _IsolatedProvider:
    name: str
    kind: Literal["bind_mount", "isolated", "none"]
    _create_fn: Callable[[CreateOptions], "IsolatedSandboxHandle"]
    _supported: frozenset[StrategyTag]

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return strategy.tag in self._supported

    def create(self, opts: CreateOptions) -> SandboxHandle:
        return self._create_fn(opts)


def make_isolated_provider(
    name: str,
    create: Callable[[CreateOptions], "IsolatedSandboxHandle"],
    *,
    supported_strategies: frozenset[StrategyTag] = _DEFAULT_STRATEGIES,
) -> SandboxProvider:
    """Wrap a `create` function into a `SandboxProvider` with kind=isolated."""
    return _IsolatedProvider(
        name=name,
        kind="isolated",
        _create_fn=create,
        _supported=supported_strategies,
    )
```

You will also need to import `IsolatedSandboxHandle` at the top — but to avoid a circular import (since `_protocols.py` imports `FinalizeResult` from `_types.py`, and `_helpers.py` already imports from `_protocols.py`), use a `TYPE_CHECKING` guard:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eden.providers._protocols import IsolatedSandboxHandle
```

The `Callable[[CreateOptions], "IsolatedSandboxHandle"]` uses a string forward reference under `from __future__ import annotations`, so the runtime doesn't need the import.

- [ ] **Step 6: Run tests to verify pass**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_finalize_result_types.py -v`
Expected: PASS — 7 tests.

- [ ] **Step 7: Pre-existing types/protocols tests pass**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_branch_strategy.py tests/unit/test_no_sandbox.py -v`
Expected: PASS (no regression).

- [ ] **Step 8: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/providers tests/unit/test_finalize_result_types.py && \
.venv/bin/ruff format eden/providers/_types.py eden/providers/_protocols.py eden/providers/_helpers.py tests/unit/test_finalize_result_types.py && \
.venv/bin/ruff format --check eden/providers/_types.py eden/providers/_protocols.py eden/providers/_helpers.py tests/unit/test_finalize_result_types.py && \
.venv/bin/ruff check --fix eden/providers/_types.py eden/providers/_protocols.py eden/providers/_helpers.py tests/unit/test_finalize_result_types.py && \
.venv/bin/ruff check eden/providers/_types.py eden/providers/_protocols.py eden/providers/_helpers.py tests/unit/test_finalize_result_types.py
```
Expected: All clean.

- [ ] **Step 9: Commit (stage by name — only 4 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/providers/_types.py eden/providers/_protocols.py eden/providers/_helpers.py tests/unit/test_finalize_result_types.py && \
git commit -m "feat(providers): add FinalizeResult + IsolatedSandboxHandle + make_isolated_provider"
```

---

## Task 2: Extract make_container_provider; refactor docker

**Files:**
- Create: `eden/providers/_impl/__init__.py`
- Create: `eden/providers/_impl/container.py`
- Modify: `eden/sandboxes/docker/__init__.py` (replace with thin factory)
- Create: `tests/unit/test_container_provider.py`

- [ ] **Step 1: Read current docker provider for reference**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && cat eden/sandboxes/docker/__init__.py`

The existing implementation is the source of truth for argv shape. Task 2 is a pure refactor: every literal `"docker"` becomes `binary`, but the rest stays line-for-line.

- [ ] **Step 2: Write the failing test for make_container_provider**

Create `tests/unit/test_container_provider.py`:

```python
"""Verify make_container_provider — argv shapes for docker + podman.

Tests are parametrized over the binary so one suite covers both providers.
All subprocess calls are mocked; no docker/podman binary required to run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._types import CreateOptions, Mount
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ProviderUnavailable,
)

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


@pytest.fixture
def mock_subprocess(monkeypatch: pytest.MonkeyPatch):
    """Mock subprocess.run + shutil.which to simulate a working binary."""
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _ok(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id-123\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _ok)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_kind_and_name(binary: str) -> None:
    p = make_container_provider(binary=binary, image="alpine:latest")  # type: ignore[arg-type]
    assert p.name == binary
    assert p.kind == "bind_mount"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_create_uses_binary_in_run_argv(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id-123\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    p = make_container_provider(binary=binary, image="alpine:latest")  # type: ignore[arg-type]
    p.create(_opts(tmp_path))

    # Two subprocess calls: image inspect + run
    inspect_cmd = captured[0]
    run_cmd = captured[1]
    assert inspect_cmd[0] == binary
    assert inspect_cmd[1:4] == ["image", "inspect", "alpine:latest"]
    assert run_cmd[0] == binary
    assert "run" in run_cmd
    assert "-d" in run_cmd
    assert "--rm" in run_cmd
    assert "alpine:latest" in run_cmd


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_missing_binary_raises(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: None)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == binary


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_not_found_error(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _inspect_fails(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        m.returncode = 1
        m.stdout = ""
        m.stderr = "Error: No such image"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _inspect_fails)
    p = make_container_provider(binary=binary, image="missing:tag")  # type: ignore[arg-type]
    with pytest.raises(ImageNotFound):
        p.create(_opts(tmp_path))


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_container_start_failed(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    calls: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        calls.append(list(cmd))
        m = MagicMock()
        if "image" in cmd and "inspect" in cmd:
            m.returncode = 0
        else:
            m.returncode = 125
            m.stderr = "boom"
        m.stdout = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ContainerStartFailed) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.exit_code == 125


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_implicit_workspace_mount(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    p.create(_opts(tmp_path))
    run_cmd = captured[1]
    # Implicit mount of opts.worktree_path → /workspace
    assert any(f"{tmp_path}:/workspace" in arg for arg in run_cmd)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_mounts_threaded(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    extra = (Mount(host=tmp_path / "extra", sandbox=Path("/extra"), read_only=True),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(_opts(tmp_path))
    run_cmd = captured[1]
    assert any(f"{tmp_path / 'extra'}:/extra:ro" in arg for arg in run_cmd)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_network_flag_threaded(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine", network="host")  # type: ignore[arg-type]
    p.create(_opts(tmp_path))
    run_cmd = captured[1]
    idx = run_cmd.index("--network")
    assert run_cmd[idx + 1] == "host"
```

- [ ] **Step 3: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_container_provider.py -v`
Expected: FAIL — `eden.providers._impl.container` not found.

- [ ] **Step 4: Create the empty `_impl` package init**

Create `eden/providers/_impl/__init__.py`:

```python
"""Internal provider implementations: shared building blocks."""

from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 5: Create `_impl/container.py` from the existing docker code**

Create `eden/providers/_impl/container.py` with this exact content (this is the existing `eden/sandboxes/docker/__init__.py` lifted nearly verbatim, with `"docker"` literals replaced by the `binary` parameter):

```python
"""Shared container-runtime provider: docker / podman bind-mount sandboxes."""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, ExecResult, Mount
from eden.sandboxes._exec import stream_exec
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ProviderUnavailable,
)

_NAME_RE = re.compile(r"[^a-z0-9-]+")


def _sanitize_container_seed(s: str) -> str:
    out = _NAME_RE.sub("-", s.lower()).strip("-")
    return out or "eden"


@dataclass
class _ContainerHandle:
    binary: str
    container_id: str
    worktree_path: Path
    host_worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        argv: list[str] = [self.binary, "exec", "-i"]
        if cwd is not None:
            argv.extend(["-w", cwd.as_posix()])
        if env:
            for k, v in env.items():
                argv.extend(["-e", f"{k}={v}"])
        argv.extend([self.container_id, "/bin/sh", "-c", cmd])
        return stream_exec(
            argv,
            cmd_for_error=cmd,
            shell=False,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        subprocess.run(
            [self.binary, "cp", str(host), f"{self.container_id}:{sandbox.as_posix()}"],
            check=True,
            capture_output=True,
            text=True,
        )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        subprocess.run(
            [self.binary, "cp", f"{self.container_id}:{sandbox.as_posix()}", str(host)],
            check=True,
            capture_output=True,
            text=True,
        )

    def close(self) -> None:
        proc = subprocess.run(
            [self.binary, "kill", self.container_id],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return None
        if "no such container" in (proc.stderr or "").lower():
            return None
        # Other errors during cleanup: don't propagate; --rm will still
        # GC if the container later exits, and re-raising would mask
        # original errors thrown from the user code path.
        return None


def make_container_provider(
    *,
    binary: Literal["docker", "podman"],
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    """Build a bind-mount SandboxProvider backed by ``<binary> run``.

    Identical argv shape for docker and podman; the binary name is threaded
    through every subprocess call (run, exec, cp, kill).
    """
    provider_mounts: tuple[Mount, ...] = mounts or ()
    provider_env: dict[str, str] = dict(env) if env else {}

    def _create(opts: CreateOptions) -> BindMountSandboxHandle:
        if not shutil.which(binary):
            raise ProviderUnavailable(provider=binary, binary=binary)

        inspect = subprocess.run(
            [binary, "image", "inspect", image],
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            raise ImageNotFound(image=image, stderr=inspect.stderr)

        # Mount precedence: implicit /workspace, then opts.mounts, then
        # provider_mounts (last write wins on sandbox-path collision).
        mount_map: dict[Path, Mount] = {}
        mount_map[Path("/workspace")] = Mount(host=opts.worktree_path, sandbox=Path("/workspace"))
        for m in opts.mounts:
            mount_map[m.sandbox] = m
        for m in provider_mounts:
            mount_map[m.sandbox] = m

        merged_env: dict[str, str] = {**provider_env, **dict(opts.env)}

        suffix = secrets.token_hex(4)
        seed = opts.name_hint or opts.branch
        container_name = f"eden-{_sanitize_container_seed(seed)}-{suffix}"
        container_name = container_name[:63]

        argv: list[str] = [
            binary,
            "run",
            "-d",
            "--rm",
            "-i",
            "--name",
            container_name,
            "--entrypoint",
            "sleep",
        ]
        for m in mount_map.values():
            spec = f"{m.host}:{m.sandbox.as_posix()}"
            if m.read_only:
                spec += ":ro"
            argv.extend(["-v", spec])
        for k, v in merged_env.items():
            argv.extend(["-e", f"{k}={v}"])
        if network:
            argv.extend(["--network", network])
        argv.extend([image, "infinity"])

        run_proc = subprocess.run(argv, capture_output=True, text=True)
        if run_proc.returncode != 0:
            raise ContainerStartFailed(
                image=image,
                exit_code=run_proc.returncode,
                stderr=run_proc.stderr,
            )
        container_id = run_proc.stdout.strip()
        return _ContainerHandle(
            binary=binary,
            container_id=container_id,
            worktree_path=Path("/workspace"),
            host_worktree_path=opts.worktree_path,
        )

    return make_bind_mount_provider(name=binary, create=_create)


__all__ = ["make_container_provider"]
```

- [ ] **Step 6: Replace `eden/sandboxes/docker/__init__.py` with the thin factory**

Replace the entire contents of `eden/sandboxes/docker/__init__.py` with:

```python
"""docker provider: bind-mount sandbox running commands inside a docker container."""

from __future__ import annotations

from collections.abc import Mapping

from eden.providers._impl.container import make_container_provider
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    return make_container_provider(
        binary="docker",
        image=image,
        mounts=mounts,
        env=env,
        network=network,
    )


__all__ = ["provider"]
```

- [ ] **Step 7: Run new container tests + Phase 2 docker regression tests**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/pytest tests/unit/test_container_provider.py -v
```
Expected: PASS — 16 tests (8 cases × 2 binaries).

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/pytest tests/integration/test_docker_*.py -v 2>&1 | tail -10
```
Expected: PASS or skip-on-no-docker (depends on environment). The Phase 2 integration tests are the regression net; if they fail, the extraction broke behavior.

- [ ] **Step 8: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/providers/_impl eden/sandboxes/docker tests/unit/test_container_provider.py && \
.venv/bin/ruff format eden/providers/_impl/__init__.py eden/providers/_impl/container.py eden/sandboxes/docker/__init__.py tests/unit/test_container_provider.py && \
.venv/bin/ruff format --check eden/providers/_impl/__init__.py eden/providers/_impl/container.py eden/sandboxes/docker/__init__.py tests/unit/test_container_provider.py && \
.venv/bin/ruff check --fix eden/providers/_impl/__init__.py eden/providers/_impl/container.py eden/sandboxes/docker/__init__.py tests/unit/test_container_provider.py && \
.venv/bin/ruff check eden/providers/_impl/__init__.py eden/providers/_impl/container.py eden/sandboxes/docker/__init__.py tests/unit/test_container_provider.py
```
Expected: All clean.

- [ ] **Step 9: Commit (stage by name — only 4 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/providers/_impl/__init__.py eden/providers/_impl/container.py eden/sandboxes/docker/__init__.py tests/unit/test_container_provider.py && \
git commit -m "refactor(providers): extract make_container_provider; docker becomes thin factory"
```

DO NOT use `git add eden/providers/_impl` (sweeps pycache).

---

## Task 3: Add podman provider

**Files:**
- Create: `eden/sandboxes/podman/__init__.py`
- Create: `tests/unit/test_podman_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_podman_provider.py`:

```python
"""Verify the podman provider is a thin shim over make_container_provider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._types import BranchStrategy
from eden.sandboxes.podman import provider as podman_provider

pytestmark = pytest.mark.unit


def test_podman_provider_returns_bind_mount_kind() -> None:
    p = podman_provider(image="alpine:latest")
    assert p.kind == "bind_mount"
    assert p.name == "podman"


def test_podman_supports_default_strategies() -> None:
    p = podman_provider(image="alpine:latest")
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_podman_uses_podman_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Confirm the podman factory threads `binary='podman'` through to subprocess argv."""
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    from eden.providers._types import CreateOptions

    opts = CreateOptions(
        branch="HEAD", worktree_path=tmp_path, host_repo_path=tmp_path,
        env={}, mounts=(), name_hint=None,
    )
    p = podman_provider(image="alpine")
    p.create(opts)

    # First call: podman image inspect ...
    # Second call: podman run -d --rm ...
    assert captured[0][0] == "podman"
    assert captured[1][0] == "podman"
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_podman_provider.py -v`
Expected: FAIL — `eden.sandboxes.podman` module not found.

- [ ] **Step 3: Implement podman factory**

Create `eden/sandboxes/podman/__init__.py`:

```python
"""podman provider: bind-mount sandbox running commands inside a podman container."""

from __future__ import annotations

from collections.abc import Mapping

from eden.providers._impl.container import make_container_provider
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    return make_container_provider(
        binary="podman",
        image=image,
        mounts=mounts,
        env=env,
        network=network,
    )


__all__ = ["provider"]
```

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_podman_provider.py -v`
Expected: PASS — 3 tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/sandboxes/podman tests/unit/test_podman_provider.py && \
.venv/bin/ruff format eden/sandboxes/podman/__init__.py tests/unit/test_podman_provider.py && \
.venv/bin/ruff format --check eden/sandboxes/podman/__init__.py tests/unit/test_podman_provider.py && \
.venv/bin/ruff check --fix eden/sandboxes/podman/__init__.py tests/unit/test_podman_provider.py && \
.venv/bin/ruff check eden/sandboxes/podman/__init__.py tests/unit/test_podman_provider.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/sandboxes/podman/__init__.py tests/unit/test_podman_provider.py && \
git commit -m "feat(podman): add bind-mount sandbox provider (sibling of docker)"
```

DO NOT use `git add eden/sandboxes/podman`.

---

## Task 4: patch_sync (snapshot, diff, apply)

**Files:**
- Create: `eden/providers/_impl/patch_sync.py`
- Create: `tests/unit/test_patch_sync.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_patch_sync.py`:

```python
"""Verify snapshot/diff/apply for isolated provider patch-sync."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from eden.providers._impl.patch_sync import DiffResult, apply, diff, snapshot
from eden.providers._types import FinalizeResult

pytestmark = pytest.mark.unit


def _w(p: Path, contents: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contents, encoding="utf-8")


def test_snapshot_hashes_files(tmp_path: Path) -> None:
    _w(tmp_path / "a.txt", "alpha")
    _w(tmp_path / "sub" / "b.txt", "beta")
    snap = snapshot(tmp_path)
    assert set(snap.keys()) == {Path("a.txt"), Path("sub/b.txt")}
    # Same contents → same hash. Different contents → different hash.
    snap2 = snapshot(tmp_path)
    assert snap == snap2


def test_snapshot_ignores_default_dirs(tmp_path: Path) -> None:
    _w(tmp_path / ".git" / "HEAD", "ref: refs/heads/main")
    _w(tmp_path / ".eden" / "logs" / "x.log", "log line")
    _w(tmp_path / "real.py", "import os")
    snap = snapshot(tmp_path)
    assert Path("real.py") in snap
    assert Path(".git/HEAD") not in snap
    assert Path(".eden/logs/x.log") not in snap


def test_snapshot_custom_ignore(tmp_path: Path) -> None:
    _w(tmp_path / "node_modules" / "x.js", "let a = 1")
    _w(tmp_path / "src" / "y.py", "x=2")
    snap = snapshot(tmp_path, ignore=("node_modules",))
    assert Path("src/y.py") in snap
    assert Path("node_modules/x.js") not in snap


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks require admin on Windows")
def test_snapshot_symlink_includes_target(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("real", encoding="utf-8")
    link = tmp_path / "link.txt"
    os.symlink(target, link)
    snap = snapshot(tmp_path)
    assert Path("link.txt") in snap
    assert Path("real.txt") in snap
    # Different target → different hash for same link name.
    other = tmp_path / "other.txt"
    other.write_text("other", encoding="utf-8")
    link.unlink()
    os.symlink(other, link)
    snap2 = snapshot(tmp_path)
    assert snap[Path("link.txt")] != snap2[Path("link.txt")]


def test_diff_classifies_changes() -> None:
    before = {Path("a"): "h1", Path("b"): "h2", Path("c"): "h3"}
    after = {Path("a"): "h1_new", Path("c"): "h3", Path("d"): "h4"}
    d = diff(before=before, after=after)
    assert d.added == frozenset({Path("d")})
    assert d.changed == frozenset({Path("a")})
    assert d.removed == frozenset({Path("b")})


def test_diff_empty_inputs() -> None:
    d = diff(before={}, after={})
    assert d.added == frozenset()
    assert d.changed == frozenset()
    assert d.removed == frozenset()


def test_apply_copies_added_and_changed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _w(src / "a.txt", "alpha-new")
    _w(src / "b.txt", "beta")
    _w(dst / "a.txt", "alpha-old")
    # Note: no b.txt in dst; it's added.

    d = DiffResult(
        added=frozenset({Path("b.txt")}),
        changed=frozenset({Path("a.txt")}),
        removed=frozenset(),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
    assert (dst / "a.txt").read_text() == "alpha-new"
    assert (dst / "b.txt").read_text() == "beta"
    assert set(fr.files_changed) == {Path("a.txt"), Path("b.txt")}
    # patch_size_bytes = sum of added/changed file sizes
    assert fr.patch_size_bytes == len("alpha-new") + len("beta")


def test_apply_unlinks_removed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    _w(dst / "gone.txt", "to be removed")
    d = DiffResult(
        added=frozenset(),
        changed=frozenset(),
        removed=frozenset({Path("gone.txt")}),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
    assert not (dst / "gone.txt").exists()
    assert Path("gone.txt") in fr.files_changed


def test_apply_creates_parent_dirs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    dst.mkdir()
    _w(src / "deep" / "nest" / "x.py", "x=1")
    d = DiffResult(
        added=frozenset({Path("deep/nest/x.py")}),
        changed=frozenset(),
        removed=frozenset(),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
    assert (dst / "deep" / "nest" / "x.py").read_text() == "x=1"


def test_apply_partial_failure_marks_not_applied(tmp_path: Path) -> None:
    """A copy that fails (non-existent source) marks the whole result not-applied."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    # The diff claims `phantom.txt` was added, but the source doesn't have it.
    d = DiffResult(
        added=frozenset({Path("phantom.txt")}),
        changed=frozenset(),
        removed=frozenset(),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is False


def test_apply_unlink_missing_target_is_silent(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    # Removing a file that isn't there is a no-op (still "applied").
    d = DiffResult(
        added=frozenset(),
        changed=frozenset(),
        removed=frozenset({Path("ghost.txt")}),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_patch_sync.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement patch_sync**

Create `eden/providers/_impl/patch_sync.py`:

```python
"""Snapshot / diff / apply for the isolated sandbox provider's patch-sync."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from eden.providers._types import FinalizeResult

_DEFAULT_IGNORE: tuple[str, ...] = (".git", ".eden")
_BUF_SIZE = 64 * 1024


@dataclass(frozen=True)
class DiffResult:
    added: frozenset[Path]
    changed: frozenset[Path]
    removed: frozenset[Path]


def snapshot(root: Path, *, ignore: tuple[str, ...] = _DEFAULT_IGNORE) -> dict[Path, str]:
    """Walk ``root`` and return ``{relative_path: sha256_hex}`` for every file.

    Top-level directories whose name is in ``ignore`` are skipped entirely.
    Symlinks are stored with their target paths included in the hash so a
    symlink retargeted to a different file produces a different hash.
    """
    out: dict[Path, str] = {}
    ignore_set = set(ignore)
    root = root.resolve()
    for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
        # Mutate `dirnames` in place to skip ignored top-level dirs.
        rel_current = Path(current_dir).resolve().relative_to(root)
        if rel_current == Path("."):
            dirnames[:] = [d for d in dirnames if d not in ignore_set]
        for name in filenames:
            full = Path(current_dir) / name
            try:
                rel = full.resolve(strict=False).relative_to(root)
            except ValueError:
                # symlink escaping root — treat as relative to current_dir
                rel = Path(current_dir).relative_to(root) / name
            try:
                if full.is_symlink():
                    target = os.readlink(full)
                    h = hashlib.sha256()
                    h.update(b"symlink:")
                    h.update(target.encode("utf-8") if isinstance(target, str) else target)
                    out[rel] = h.hexdigest()
                else:
                    out[rel] = _hash_file(full)
            except FileNotFoundError:
                # Disappeared mid-walk — skip silently.
                continue
    return out


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(_BUF_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def diff(*, before: dict[Path, str], after: dict[Path, str]) -> DiffResult:
    """Compute per-file change sets between two snapshots."""
    before_keys = set(before)
    after_keys = set(after)
    added = frozenset(after_keys - before_keys)
    removed = frozenset(before_keys - after_keys)
    changed = frozenset(p for p in (before_keys & after_keys) if before[p] != after[p])
    return DiffResult(added=added, changed=changed, removed=removed)


def apply(
    diff_result: DiffResult,
    *,
    src: Path,
    dst: Path,
) -> FinalizeResult:
    """Replay the diff against ``dst``.

    Adds and changes are copied from ``src`` to ``dst`` (parent dirs created).
    Removals unlink the file under ``dst`` (silent if already gone). Returns a
    summary; does NOT raise — individual file errors set ``applied=False``.
    """
    all_paths: list[Path] = sorted(diff_result.added | diff_result.changed | diff_result.removed)
    applied = True
    total_bytes = 0

    for rel in sorted(diff_result.added | diff_result.changed):
        src_file = src / rel
        dst_file = dst / rel
        try:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            data = src_file.read_bytes()
            dst_file.write_bytes(data)
            total_bytes += len(data)
        except OSError as exc:  # pragma: no cover — error path
            print(f"[patch_sync] copy failed: {rel}: {exc}", file=sys.stderr)
            applied = False

    for rel in sorted(diff_result.removed):
        dst_file = dst / rel
        try:
            if dst_file.exists() or dst_file.is_symlink():
                dst_file.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:  # pragma: no cover — error path
            print(f"[patch_sync] unlink failed: {rel}: {exc}", file=sys.stderr)
            applied = False

    return FinalizeResult(
        applied=applied,
        files_changed=tuple(all_paths),
        patch_size_bytes=total_bytes,
    )


__all__ = ["DiffResult", "apply", "diff", "snapshot"]
```

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_patch_sync.py -v`
Expected: PASS — 11 tests (one skipped on Windows).

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/providers/_impl/patch_sync.py tests/unit/test_patch_sync.py && \
.venv/bin/ruff format eden/providers/_impl/patch_sync.py tests/unit/test_patch_sync.py && \
.venv/bin/ruff format --check eden/providers/_impl/patch_sync.py tests/unit/test_patch_sync.py && \
.venv/bin/ruff check --fix eden/providers/_impl/patch_sync.py tests/unit/test_patch_sync.py && \
.venv/bin/ruff check eden/providers/_impl/patch_sync.py tests/unit/test_patch_sync.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/providers/_impl/patch_sync.py tests/unit/test_patch_sync.py && \
git commit -m "feat(patch_sync): add snapshot/diff/apply for isolated provider sync"
```

---

## Task 5: isolated provider

**Files:**
- Create: `eden/sandboxes/isolated/__init__.py`
- Create: `tests/unit/test_isolated_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_isolated_provider.py`:

```python
"""Verify the local isolated() provider's lifecycle and finalize behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle
from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.isolated import provider as isolated_provider

pytestmark = pytest.mark.unit


def _opts(host: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=host,
        host_repo_path=host,
        env={},
        mounts=(),
        name_hint="test",
    )


def test_provider_kind_and_name() -> None:
    p = isolated_provider()
    assert p.kind == "isolated"
    assert p.name == "isolated"


def test_provider_supports_default_strategies() -> None:
    p = isolated_provider()
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_carves_isolated_root_with_copy(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "src.py").write_text("x=1", encoding="utf-8")
    (host / "sub").mkdir()
    (host / "sub" / "y.txt").write_text("y", encoding="utf-8")

    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        assert handle.worktree_path != host
        assert handle.worktree_path.exists()
        assert (handle.worktree_path / "src.py").read_text() == "x=1"
        assert (handle.worktree_path / "sub" / "y.txt").read_text() == "y"
    finally:
        handle.close()


def test_create_handle_satisfies_isolated_protocol(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    try:
        assert isinstance(handle, IsolatedSandboxHandle)
    finally:
        handle.close()


def test_close_removes_isolated_root(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    isolated_root = handle.worktree_path
    assert isolated_root.exists()
    handle.close()
    assert not isolated_root.exists()


def test_close_is_idempotent(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    handle.close()
    handle.close()  # must not raise


def test_finalize_replays_added_and_changed(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "a.txt").write_text("alpha-orig", encoding="utf-8")
    (host / "b.txt").write_text("beta", encoding="utf-8")

    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        # Modify the isolated copy
        (handle.worktree_path / "a.txt").write_text("alpha-new", encoding="utf-8")
        (handle.worktree_path / "c.txt").write_text("gamma", encoding="utf-8")
        (handle.worktree_path / "b.txt").unlink()

        fr = handle.finalize(target=host)
        assert fr.applied is True
        assert (host / "a.txt").read_text() == "alpha-new"
        assert (host / "c.txt").read_text() == "gamma"
        assert not (host / "b.txt").exists()
        assert set(fr.files_changed) == {Path("a.txt"), Path("b.txt"), Path("c.txt")}
    finally:
        handle.close()


def test_default_base_dir_is_under_eden_isolated(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        # base_dir defaults to host_repo_path / ".eden" / "isolated" / ...
        assert (host / ".eden" / "isolated") in handle.worktree_path.parents
    finally:
        handle.close()


def test_explicit_base_dir(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    custom = tmp_path / "custom_base"
    p = isolated_provider(base_dir=custom)
    handle = p.create(_opts(host))
    try:
        assert custom in handle.worktree_path.parents
    finally:
        handle.close()
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_isolated_provider.py -v`
Expected: FAIL — `eden.sandboxes.isolated` not found.

- [ ] **Step 3: Implement isolated provider**

Create `eden/sandboxes/isolated/__init__.py`:

```python
"""Local isolated provider: copy worktree, run agent in copy, patch-sync back."""

from __future__ import annotations

import re
import secrets
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._helpers import make_isolated_provider
from eden.providers._impl import patch_sync
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.sandboxes._exec import stream_exec

_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_seed(s: str) -> str:
    out = _NAME_RE.sub("-", s).strip("-")
    return out[:64] if len(out) > 64 else (out or "run")


@dataclass
class _IsolatedHandle:
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        merged_cwd = cwd if cwd is not None else self.worktree_path
        return stream_exec(
            ["/bin/sh", "-c", cmd],
            cmd_for_error=cmd,
            shell=False,
            cwd=str(merged_cwd),
            env=env,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(sandbox, host)

    def finalize(self, target: Path) -> FinalizeResult:
        after = patch_sync.snapshot(self.worktree_path)
        d = patch_sync.diff(before=self.baseline, after=after)
        return patch_sync.apply(d, src=self.worktree_path, dst=target)

    def close(self) -> None:
        if self.worktree_path.exists():
            shutil.rmtree(self.worktree_path, ignore_errors=True)


def provider(*, base_dir: Path | None = None) -> SandboxProvider:
    """Local isolated provider: copy worktree to a tmp dir, run agent there,
    finalize by patch-syncing changes back to the host worktree.

    ``base_dir`` defaults to ``<host_repo_path>/.eden/isolated/`` (sibling of
    ``.eden/worktrees/`` and ``.eden/sessions/``). Each ``create()`` call
    carves a fresh subdirectory there.
    """
    fixed_base = base_dir

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        base = fixed_base if fixed_base is not None else (opts.host_repo_path / ".eden" / "isolated")
        base.mkdir(parents=True, exist_ok=True)
        suffix = secrets.token_hex(4)
        seed = opts.name_hint or opts.branch
        isolated_root = base / f"{_sanitize_seed(seed)}-{suffix}"

        baseline = patch_sync.snapshot(opts.worktree_path)
        shutil.copytree(
            opts.worktree_path,
            isolated_root,
            ignore=shutil.ignore_patterns(".git", ".eden"),
        )

        return _IsolatedHandle(
            worktree_path=isolated_root,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
        )

    return make_isolated_provider(name="isolated", create=_create)


__all__ = ["provider"]
```

- [ ] **Step 4: Run passing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_isolated_provider.py -v`
Expected: PASS — 9 tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/sandboxes/isolated tests/unit/test_isolated_provider.py && \
.venv/bin/ruff format eden/sandboxes/isolated/__init__.py tests/unit/test_isolated_provider.py && \
.venv/bin/ruff format --check eden/sandboxes/isolated/__init__.py tests/unit/test_isolated_provider.py && \
.venv/bin/ruff check --fix eden/sandboxes/isolated/__init__.py tests/unit/test_isolated_provider.py && \
.venv/bin/ruff check eden/sandboxes/isolated/__init__.py tests/unit/test_isolated_provider.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/sandboxes/isolated/__init__.py tests/unit/test_isolated_provider.py && \
git commit -m "feat(isolated): add local copy+patch-sync sandbox provider"
```

DO NOT use `git add eden/sandboxes/isolated`.

---

## Task 6: _AgentRunner cwd kwarg

**Files:**
- Modify: `eden/orchestrator/_runner.py`
- Create: `tests/unit/test_agent_runner_cwd.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agent_runner_cwd.py`:

```python
"""Verify the new cwd kwarg on _AgentRunner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.abort import AbortController
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._runner import _AgentRunner

pytestmark = pytest.mark.unit


def test_default_cwd_inherits_python_cwd(tmp_path: Path) -> None:
    """Without cwd= the agent runs with the parent's cwd (Phase 3a default)."""
    argv = [sys.executable, "-c", "import os, sys; sys.stdout.write(os.getcwd())"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        assert lines == [str(Path.cwd())]
    finally:
        wd.stop()


def test_cwd_kwarg_changes_subprocess_cwd(tmp_path: Path) -> None:
    """With cwd=tmp_path the agent runs in tmp_path."""
    argv = [sys.executable, "-c", "import os, sys; sys.stdout.write(os.getcwd())"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd, cwd=tmp_path) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        # The path may be normalized (e.g., /private/var/folders/... vs /var/folders/... on macOS)
        assert Path(lines[0]).resolve() == tmp_path.resolve()
    finally:
        wd.stop()


def test_explicit_none_cwd_matches_default(tmp_path: Path) -> None:
    argv = [sys.executable, "-c", "import os, sys; sys.stdout.write(os.getcwd())"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd, cwd=None) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        assert lines == [str(Path.cwd())]
    finally:
        wd.stop()
```

- [ ] **Step 2: Run failing test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/unit/test_agent_runner_cwd.py -v`
Expected: FAIL — `_AgentRunner.__init__` doesn't accept `cwd`.

- [ ] **Step 3: Add cwd kwarg to _AgentRunner**

Edit `eden/orchestrator/_runner.py`. Three small changes:

1. The `__init__` signature gains `cwd: Path | None = None` (added after `watchdog`).
2. Store as `self._cwd: Path | None = cwd` in `__init__` body.
3. The `__enter__` method's `subprocess.Popen` call adds a `cwd=str(self._cwd) if self._cwd is not None else None` argument.

The full updated `__init__` and `__enter__` should look like:

```python
class _AgentRunner:
    def __init__(
        self,
        *,
        argv: list[str],
        env: Mapping[str, str],
        watchdog: IdleWatchdog,
        cwd: Path | None = None,
    ) -> None:
        self._argv = list(argv)
        self._env = dict(env)
        self._watchdog = watchdog
        self._cwd = cwd
        self._proc: subprocess.Popen[str] | None = None
        self._stdout_q: Queue[Any] = Queue()
        self._stderr_chunks: list[str] = []

    def __enter__(self) -> _AgentRunner:
        merged = dict(os.environ)
        merged.update(self._env)
        self._proc = subprocess.Popen(
            self._argv,
            env=merged,
            cwd=str(self._cwd) if self._cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # ... existing assertions and thread setup unchanged
```

Also add `from pathlib import Path` to the imports if not already present (Phase 3a/3b may already have it).

- [ ] **Step 4: Run passing test + Phase 3a regression tests**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/pytest tests/unit/test_agent_runner_cwd.py tests/unit/test_agent_runner.py -v
```
Expected: PASS — 3 new + 5 existing = 8 tests.

- [ ] **Step 5: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/orchestrator/_runner.py tests/unit/test_agent_runner_cwd.py && \
.venv/bin/ruff format eden/orchestrator/_runner.py tests/unit/test_agent_runner_cwd.py && \
.venv/bin/ruff format --check eden/orchestrator/_runner.py tests/unit/test_agent_runner_cwd.py && \
.venv/bin/ruff check --fix eden/orchestrator/_runner.py tests/unit/test_agent_runner_cwd.py && \
.venv/bin/ruff check eden/orchestrator/_runner.py tests/unit/test_agent_runner_cwd.py
```
Expected: All clean.

- [ ] **Step 6: Commit (stage by name — only 2 files)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/orchestrator/_runner.py tests/unit/test_agent_runner_cwd.py && \
git commit -m "feat(orchestrator): add optional cwd kwarg to _AgentRunner"
```

---

## Task 7: _run_loop wiring (cwd + finalize call)

**Files:**
- Modify: `eden/orchestrator/_loop.py`

(No new test file — the wiring is exercised by the `isolated` e2e test in Task 9; Phase 3a's existing `test_run_loop.py` provides a regression net for non-isolated runs.)

- [ ] **Step 1: Replace `eden/orchestrator/_loop.py` with the wired version**

Read the current file first to preserve the exact structure. Then make these two additions inside `_run_loop`:

**Addition 1 — agent cwd plumbing.** Replace the existing `with _AgentRunner(argv=argv, env=setup.merged_env, watchdog=wd) as runner:` line with:

```python
agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None
with _AgentRunner(
    argv=argv,
    env=setup.merged_env,
    watchdog=wd,
    cwd=agent_cwd,
) as runner:
```

**Addition 2 — finalize call.** AFTER the iteration `for` loop body completes (i.e., after the loop's natural exit on completion or max_iterations) and BEFORE the existing `try/finally` teardown, add this block. Locate the existing pattern that looks like:

```python
            iterations.append(Iteration(
                index=i,
                completion_signal=iter_completion,
                ...
            ))
            if iter_completion is not None:
                completion_hit = iter_completion
                break

    finally:                                      # ← existing finally
```

Insert this BEFORE the `finally:` and AFTER the `for i in range(max_iterations):` loop closes:

```python
        # Phase 4a: post-iteration finalize for isolated providers.
        if handle is not None and hasattr(handle, "finalize"):
            try:
                fr = handle.finalize(target=wt.host_repo_path)
                if sink is not None:
                    sink.write(StreamEvent(
                        type="text",
                        agent_name=agent.name,
                        iteration=len(iterations),
                        timestamp=_utcnow(),
                        text=(
                            f"[eden] finalized: applied={fr.applied} "
                            f"files={len(fr.files_changed)} "
                            f"bytes={fr.patch_size_bytes}"
                        ),
                    ))
            except Exception as exc:
                if sink is not None:
                    sink.write(StreamEvent(
                        type="text",
                        agent_name=agent.name,
                        iteration=len(iterations),
                        timestamp=_utcnow(),
                        text=f"[eden] finalize failed: {exc}",
                    ))
```

This block is INSIDE the outer `try:` block (so it's skipped when `Aborted`/`IdleTimeout` is in flight), but OUTSIDE the iteration `for` loop (so it runs once after all iterations complete normally).

- [ ] **Step 2: Run Phase 3a/3b regression tests**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/pytest tests/unit/test_run_loop.py tests/e2e/test_run_smoke.py tests/e2e/test_claude_code_smoke.py -v
```
Expected: PASS — all existing run-loop tests (6 + 2 + 2 = 10 tests passing on macOS).

- [ ] **Step 3: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden/orchestrator && \
.venv/bin/ruff format eden/orchestrator/_loop.py && \
.venv/bin/ruff format --check eden/orchestrator/_loop.py && \
.venv/bin/ruff check --fix eden/orchestrator/_loop.py && \
.venv/bin/ruff check eden/orchestrator/_loop.py
```
Expected: All clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/orchestrator/_loop.py && \
git commit -m "feat(orchestrator): pass cwd to _AgentRunner; call handle.finalize() on success"
```

---

## Task 8: Top-level public re-exports

**Files:**
- Modify: `eden/__init__.py`

- [ ] **Step 1: Add FinalizeResult + IsolatedSandboxHandle to imports**

Edit `eden/__init__.py`. Add `FinalizeResult` and `IsolatedSandboxHandle` to the top-level surface:

1. Add `from eden.providers._protocols import IsolatedSandboxHandle` (alphabetical).
2. Update `from eden.providers._types import BranchStrategy, Mount` to include `FinalizeResult`:
   ```python
   from eden.providers._types import BranchStrategy, FinalizeResult, Mount
   ```
3. Add `"FinalizeResult"` and `"IsolatedSandboxHandle"` to `__all__` (alphabetical via ruff RUF022 unsafe-fix).

- [ ] **Step 2: Verify imports**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/python -c "import eden; assert eden.FinalizeResult is not None; assert eden.IsolatedSandboxHandle is not None; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Run full unit + e2e suite (regression check)**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/pytest -m "unit or e2e" --no-cov -q
```
Expected: All tests pass. Total: 292 (Phase 3b baseline) + new tests through Task 7 (~46) = ~338 passing.

- [ ] **Step 4: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy eden && \
.venv/bin/ruff format eden/__init__.py && \
.venv/bin/ruff format --check eden/__init__.py && \
.venv/bin/ruff check --fix eden/__init__.py && \
.venv/bin/ruff check eden/__init__.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add eden/__init__.py && \
git commit -m "feat(eden): re-export FinalizeResult + IsolatedSandboxHandle"
```

---

## Task 9: E2E smoke test for isolated provider

**Files:**
- Create: `tests/e2e/test_isolated_smoke.py`

- [ ] **Step 1: Write the e2e test**

Create `tests/e2e/test_isolated_smoke.py`:

```python
"""Smoke E2E: simulated_agent + isolated provider + finalize patch-sync."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes import isolated as isolated_sandbox

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="sandbox hook uses /bin/sh, not available on Windows",
)
def test_isolated_finalize_writes_sandbox_changes_to_host(e2e_git_repo: Path) -> None:
    """End-to-end: a sandbox hook writes a file inside the isolated root;
    after the iteration completes, finalize() copies that file to the host
    worktree, and the orchestrator emits a `[eden] finalized:` message."""
    # The sandbox hook runs IN the sandbox via handle.exec(), so for the
    # isolated provider its cwd is the isolated_root (where finalize will
    # diff against the baseline). simulated_agent's stdout-only behavior
    # means we use a hook for the filesystem side-effect.
    sandbox_hook = eden.Hook(
        cmd='echo "hello-from-agent" > new_file.txt',
    )
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="working\n<promise>COMPLETE</promise>\n"),
        sandbox=isolated_sandbox.provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    # File written inside the isolated sandbox landed on the host.
    target_file = e2e_git_repo / "new_file.txt"
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8").strip() == "hello-from-agent"

    # Finalize message recorded in the log file.
    assert result.log_file_path is not None
    log_body = result.log_file_path.read_text(encoding="utf-8")
    assert "[eden] finalized:" in log_body
    assert "applied=True" in log_body


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="sandbox hook uses /bin/sh, not available on Windows",
)
def test_isolated_finalize_propagates_deletes(e2e_git_repo: Path) -> None:
    """Deleting a file inside the isolated sandbox propagates to the host."""
    # Pre-populate a file in the host worktree (the e2e_git_repo fixture
    # initializes README.md). The sandbox hook deletes it.
    assert (e2e_git_repo / "README.md").exists()
    sandbox_hook = eden.Hook(cmd="rm README.md")
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=isolated_sandbox.provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert not (e2e_git_repo / "README.md").exists()
    assert result.log_file_path is not None
    assert "applied=True" in result.log_file_path.read_text(encoding="utf-8")
```

The sandbox hook runs via `handle.exec(...)` whose default cwd is `handle.worktree_path` (the isolated root, set in `_IsolatedHandle.exec`). So `echo > new_file.txt` lands in the isolated copy, NOT the host. The orchestrator's post-iteration `handle.finalize(target=wt.host_repo_path)` then computes the diff (added: `new_file.txt`) and applies it to the host worktree.

- [ ] **Step 2: Run e2e test**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/e2e/test_isolated_smoke.py -v`
Expected: PASS — 1 test (skipped on Windows). If the host-hook quoting is too brittle, fall back to the manual-handle approach described above.

- [ ] **Step 3: Run combined unit + e2e (regression check)**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest -m "unit or e2e" --no-cov -q`
Expected: All tests pass.

- [ ] **Step 4: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy tests/e2e/test_isolated_smoke.py && \
.venv/bin/ruff format tests/e2e/test_isolated_smoke.py && \
.venv/bin/ruff format --check tests/e2e/test_isolated_smoke.py && \
.venv/bin/ruff check --fix tests/e2e/test_isolated_smoke.py && \
.venv/bin/ruff check tests/e2e/test_isolated_smoke.py
```
Expected: All clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add tests/e2e/test_isolated_smoke.py && \
git commit -m "test(e2e): add isolated provider + finalize smoke run"
```

---

## Task 10: Podman integration test (Linux-only)

**Files:**
- Create: `tests/integration/test_podman.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_podman.py`:

```python
"""Integration tests for the podman provider.

Linux-only; gated on `shutil.which("podman")`. Mirrors the docker integration
tests' shape so podman behavior parity is verifiable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.podman import provider as podman_provider

pytestmark = pytest.mark.integration


def _require_podman() -> None:
    if shutil.which("podman") is None:
        pytest.skip("podman not installed")


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="eden-podman-test",
    )


def test_create_and_close(tmp_path: Path) -> None:
    _require_podman()
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    try:
        assert handle.worktree_path == Path("/workspace")
    finally:
        handle.close()


def test_exec_returns_stdout(tmp_path: Path) -> None:
    _require_podman()
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    try:
        result = handle.exec("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
    finally:
        handle.close()


def test_copy_file_in_then_exec(tmp_path: Path) -> None:
    _require_podman()
    src = tmp_path / "payload.txt"
    src.write_text("FROM HOST", encoding="utf-8")
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    try:
        handle.copy_file_in(src, Path("/tmp/payload.txt"))
        result = handle.exec("cat /tmp/payload.txt")
        assert result.exit_code == 0
        assert "FROM HOST" in result.stdout
    finally:
        handle.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    _require_podman()
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    handle.close()
    handle.close()  # must not raise
```

- [ ] **Step 2: Run the test (locally, if podman is installed; skip otherwise)**

`cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && .venv/bin/pytest tests/integration/test_podman.py -v -m integration`
Expected: 4 tests pass on Linux with podman installed; SKIP on systems without podman.

- [ ] **Step 3: mypy + ruff**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/mypy tests/integration/test_podman.py && \
.venv/bin/ruff format tests/integration/test_podman.py && \
.venv/bin/ruff format --check tests/integration/test_podman.py && \
.venv/bin/ruff check --fix tests/integration/test_podman.py && \
.venv/bin/ruff check tests/integration/test_podman.py
```
Expected: All clean.

- [ ] **Step 4: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add tests/integration/test_podman.py && \
git commit -m "test(integration): add podman parity tests (Linux-gated)"
```

---

## Task 11: Update README status

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump status line**

Edit `README.md:5` (the `> **Status:** ...` blockquote). Replace the existing line with:

```markdown
> **Status:** Pre-alpha. Phases 1–4a complete: package skeleton, provider Protocols, worktree manager, `no_sandbox`/`docker`/`podman` bind-mount providers, local `isolated` patch-sync provider, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent` and `claude_code` agents, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, Claude Code session JSONL capture, and post-iteration `finalize()` for isolated handles. Cloud providers (4b — vercel, daytona), other agents (5), CLI scaffolder (6), and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
git add README.md && \
git commit -m "docs: bump README status to phase 4a complete"
```

---

## Final verification (after every task is committed)

- [ ] **Step 1: Full local CI parity check**

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden && \
.venv/bin/ruff format --check eden tests && \
.venv/bin/ruff check --no-cache eden tests && \
.venv/bin/mypy --strict eden tests && \
.venv/bin/pytest -m "unit or e2e" --cov=eden --cov-fail-under=70
```
Expected: every command Success / PASS. Coverage stays ≥ 70%.

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

Then check GitHub CI — all 9 matrix jobs (Linux/macOS/Windows × py3.11/3.12/3.13) green for unit+e2e. The Linux integration job runs the docker tests (still passing — the extraction is behavior-preserving) PLUS the new podman tests (skip if podman not installed in the runner image).

- [ ] **Step 3: Tag the phase**

Wait for CI green before tagging.

```bash
git tag -a phase-4a -m "Phase 4a: provider parity (local) — podman, isolated, patch-sync"
git push origin phase-4a
```

---

## Notes for the implementer

- **No new threads.** `snapshot()` and `apply()` run synchronously on the main thread before/after the iteration loop. Phase 3a/3b's stdout-pump and idle-watchdog threading are unchanged.
- **`hasattr(handle, "finalize")` is the duck-type gate.** Bind-mount providers (docker, podman, no_sandbox) lack the attribute; the orchestrator's new finalize block is a no-op for them.
- **`make_container_provider` extraction is behavior-preserving.** Phase 2's `tests/integration/test_docker_*.py` files serve as the regression net — they must pass UNCHANGED after Task 2.
- **`agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None`** — the in-container path `/workspace` doesn't exist on the host filesystem, so `.exists()` returns False and the orchestrator falls back to `None`. Native (`isolated`, `no_sandbox`) paths exist; the orchestrator passes them through.
- **Soft failure on finalize errors.** Same pattern as Phase 3b's session-capture errors — the iteration's stdout, log file, and prior events are unaffected.
- **`isolated.provider()` ignores `opts.mounts`.** The host filesystem IS the sandbox surface for local isolated; users who need extra files must `copy_file_in` them after creation.
- **No file mode preservation.** A `chmod +x` inside the isolated sandbox does NOT propagate to the target. Documented limitation for 4a; Phase 5+ may add it.
- **No empty-directory preservation.** Snapshots only see files. An empty `__pycache__/` (etc.) on the sandbox side is not replicated to the target.
- **Podman is rootless by default.** Container `$HOME` is `/root` for the Phase 3b session-capture mount injection (when `agent.captures_sessions=True` AND the sandbox is a containerized provider). Rootless podman maps host UID inside the container; `~/.claude/projects` mount works the same way.
- **Coverage gate:** stays at 70%. Phase 3b baseline was 94.54%; Phase 4a adds heavily-tested code, so total stays well above gate.
- **Frequent commits.** Each task lands one commit (Task 2 lands one for clarity even though it touches 4 files — the extraction must be atomic to keep Phase 2 docker tests as the regression net).

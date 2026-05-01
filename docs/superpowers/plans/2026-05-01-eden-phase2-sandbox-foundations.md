# Eden Phase 2 — Sandbox Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the runtime substrate Phase 3+ build on: provider Protocols, the worktree manager (head + merge_to_head + named), `no_sandbox` and `docker` MVP providers, and a top-level `create_sandbox()` factory.

**Architecture:** A single Python package adds three sub-namespaces (`eden.providers`, `eden.worktree`, `eden.sandboxes`) on top of the Phase 1 skeleton. Sub-modules use `_`-prefixed file names for internals; each sub-package's `__init__.py` re-exports the public surface. All public types are frozen dataclasses or `@runtime_checkable` Protocols. Subprocess work uses sync `subprocess.Popen` with thread-drained pipes — no `asyncio`.

**Tech Stack:** Python 3.11+ (existing baseline), `subprocess`, `threading`, `fcntl`/`msvcrt` (no new pip deps), `pytest` for unit + integration tests, real Docker on Linux CI for integration. CI matrix unchanged from Phase 1 (3 OS × 3 Python).

**Reference spec:** `docs/superpowers/specs/2026-05-01-eden-phase2-sandbox-foundations-design.md`

**Phase 1 base:** This plan assumes Phase 1 is committed: `eden/{__init__.py,_version.py,py.typed,cli/}` exists, `pyproject.toml` is set up with mypy `--strict` + ruff + pytest markers (`unit`, `integration`, `smoke`), CI runs all three gates green on the 9-job matrix.

---

## File structure produced by this plan

```
eden/
├── __init__.py                            # (unchanged from phase 1)
├── _version.py                            # (unchanged)
├── py.typed                               # (unchanged)
├── errors.py                              # NEW — EdenError base
├── cli/                                   # (unchanged)
├── providers/
│   ├── __init__.py                        # NEW — public re-exports
│   ├── _types.py                          # NEW — BranchStrategy, Mount, ExecResult, CreateOptions
│   ├── _protocols.py                      # NEW — SandboxProvider, SandboxHandle, BindMountSandboxHandle
│   └── _helpers.py                        # NEW — make_bind_mount_provider
├── worktree/
│   ├── __init__.py                        # NEW — public re-exports
│   ├── errors.py                          # NEW — WorktreeError + 4 subclasses
│   ├── _lock.py                           # NEW — cross-platform advisory lock
│   ├── _git.py                            # NEW — git command wrappers
│   └── _create.py                         # NEW — create_worktree, WorktreeHandle, CloseResult
└── sandboxes/
    ├── __init__.py                        # NEW — public re-exports (create_sandbox, Sandbox)
    ├── errors.py                          # NEW — SandboxError + 6 subclasses
    ├── _exec.py                           # NEW — stream_exec helper
    ├── _factory.py                        # NEW — create_sandbox + Sandbox wrapper
    ├── no_sandbox/
    │   └── __init__.py                    # NEW — provider() + _NoSandboxHandle
    └── docker/
        └── __init__.py                    # NEW — provider(*, image, ...) + _DockerHandle

tests/
├── conftest.py                            # NEW — shared fixtures (tmp git repo, mock_subprocess)
├── unit/
│   ├── __init__.py                        # NEW
│   ├── test_branch_strategy.py            # NEW
│   ├── test_providers_protocol.py         # NEW
│   ├── test_make_bind_mount_provider.py   # NEW
│   ├── test_worktree_lock.py              # NEW
│   ├── test_worktree_head.py              # NEW
│   ├── test_worktree_strategies.py        # NEW (merge_to_head + named)
│   ├── test_stream_exec.py                # NEW
│   ├── test_no_sandbox.py                 # NEW
│   ├── test_docker_provider.py            # NEW (subprocess mocked)
│   └── test_create_sandbox.py             # NEW
└── integration/
    ├── __init__.py                        # NEW
    ├── conftest.py                        # NEW — eden_test_image session fixture
    ├── Dockerfile                         # NEW — alpine + git + bash
    ├── test_docker_exec.py                # NEW
    ├── test_docker_copy.py                # NEW
    └── test_docker_lifecycle.py           # NEW
```

**File responsibilities:**

- `eden/errors.py` — only `EdenError` base. Per-subsystem subclasses live next to the subsystem.
- `eden/providers/_types.py` — frozen dataclasses + `StrategyTag` literal. No imports from `eden.sandboxes` or `eden.worktree` (avoids cycles).
- `eden/providers/_protocols.py` — `@runtime_checkable` Protocols only. Imports `_types`.
- `eden/providers/_helpers.py` — `make_bind_mount_provider` factory.
- `eden/worktree/_lock.py` — cross-platform advisory file lock with stale-PID recovery. Pure stdlib.
- `eden/worktree/_git.py` — thin wrappers for `git status --porcelain`, `git rev-parse`, `git worktree add/remove`. Maps non-zero exits to `GitCommandFailed`.
- `eden/worktree/_create.py` — `create_worktree`, `WorktreeHandle`, `CloseResult`, branch-name generation, sanitization.
- `eden/sandboxes/_exec.py` — `stream_exec(...)` line-streams stdout+stderr via threads, supports timeout via SIGTERM→SIGKILL, returns `ExecResult` or raises `ExecTimeout`. Used by both providers.
- `eden/sandboxes/_factory.py` — `create_sandbox` resolves branch/strategy + invokes provider. `Sandbox` is a thin context-manager bundling `WorktreeHandle` + `SandboxHandle`.
- `eden/sandboxes/no_sandbox/__init__.py` — provider() + `_NoSandboxHandle`. Always operates in `opts.worktree_path`.
- `eden/sandboxes/docker/__init__.py` — `provider(*, image, mounts=None, env=None, network=None)` + `_DockerHandle`. Image is required; container started with `--entrypoint sleep infinity`.

**Test responsibilities:**

- `tests/conftest.py` — shared fixtures: `tmp_git_repo` (initializes a git repo in `tmp_path` with one commit on `main`), `mock_subprocess` (records argv, returns scripted results).
- `tests/unit/*` — `unit` marker; subprocess calls always mocked; real-git tests use `tmp_git_repo`. Run on all 9 CI jobs.
- `tests/integration/conftest.py` — session-scoped `eden_test_image` fixture; module-level skip on non-Linux.
- `tests/integration/Dockerfile` — alpine base + git + bash. Built once per session.

---

## Task 1: Errors hierarchy

**Files:**
- Create: `eden/errors.py`
- Create: `eden/worktree/__init__.py`
- Create: `eden/worktree/errors.py`
- Create: `eden/sandboxes/__init__.py`
- Create: `eden/sandboxes/errors.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/__init__.py` empty:

```bash
mkdir -p tests/unit
: > tests/unit/__init__.py
```

Create `tests/unit/test_errors.py`:

```python
"""Verify the Phase 2 exception hierarchy."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import EdenError
from eden.providers._types import ExecResult
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ExecFailed,
    ExecTimeout,
    ImageNotFound,
    ProviderUnavailable,
    SandboxError,
    UnsupportedStrategy,
)
from eden.worktree.errors import (
    BranchExists,
    DirtyHostBlocked,
    GitCommandFailed,
    WorktreeError,
    WorktreeLocked,
)


pytestmark = pytest.mark.unit


def test_eden_error_is_exception() -> None:
    assert issubclass(EdenError, Exception)


def test_worktree_error_inherits_eden_error() -> None:
    assert issubclass(WorktreeError, EdenError)


def test_sandbox_error_inherits_eden_error() -> None:
    assert issubclass(SandboxError, EdenError)


def test_worktree_locked_carries_path_and_pid() -> None:
    err = WorktreeLocked(lock_path=Path("/tmp/x.lock"), holder_pid=4242)
    assert err.lock_path == Path("/tmp/x.lock")
    assert err.holder_pid == 4242
    assert "4242" in str(err)


def test_dirty_host_blocked_carries_path_and_files() -> None:
    err = DirtyHostBlocked(
        host_repo_path=Path("/repo"), dirty_files=("a.py", "b.py")
    )
    assert err.host_repo_path == Path("/repo")
    assert err.dirty_files == ("a.py", "b.py")
    assert "a.py" in str(err)


def test_branch_exists_carries_branch() -> None:
    err = BranchExists(branch="feat/x")
    assert err.branch == "feat/x"
    assert "feat/x" in str(err)


def test_git_command_failed_carries_argv_and_stderr() -> None:
    err = GitCommandFailed(
        argv=("git", "status"), exit_code=128, stderr="boom"
    )
    assert err.argv == ("git", "status")
    assert err.exit_code == 128
    assert err.stderr == "boom"
    assert "128" in str(err)


def test_provider_unavailable_carries_provider_and_binary() -> None:
    err = ProviderUnavailable(provider="docker", binary="docker")
    assert err.provider == "docker"
    assert err.binary == "docker"


def test_image_not_found_carries_image_and_stderr() -> None:
    err = ImageNotFound(image="alpine:latest", stderr="not found")
    assert err.image == "alpine:latest"
    assert err.stderr == "not found"


def test_container_start_failed_carries_image_exit_stderr() -> None:
    err = ContainerStartFailed(image="alpine", exit_code=125, stderr="boom")
    assert err.exit_code == 125


def test_exec_failed_carries_result_and_cmd() -> None:
    result = ExecResult(stdout="", stderr="bad", exit_code=2)
    err = ExecFailed(result=result, argv_or_cmd="ls /missing")
    assert err.result is result
    assert err.argv_or_cmd == "ls /missing"


def test_exec_timeout_carries_partial_buffers() -> None:
    err = ExecTimeout(
        cmd="sleep 100",
        timeout=1.0,
        partial_stdout="hello",
        partial_stderr="warn",
    )
    assert err.timeout == 1.0
    assert err.partial_stdout == "hello"
    assert err.partial_stderr == "warn"


def test_unsupported_strategy_carries_provider_and_tag() -> None:
    err = UnsupportedStrategy(provider="docker", strategy="head")
    assert err.provider == "docker"
    assert err.strategy == "head"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_errors.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.errors'`.

- [ ] **Step 3: Create `eden/errors.py`**

```python
"""Base class for all Eden runtime errors."""

from __future__ import annotations


class EdenError(Exception):
    """Base for every error raised from the eden package."""
```

- [ ] **Step 4: Create `eden/worktree/__init__.py`**

```bash
mkdir -p eden/worktree
```

Empty for now (we'll fill in re-exports in Task 7):

```python
"""Eden worktree manager — public surface assembled in later tasks."""
```

- [ ] **Step 5: Create `eden/worktree/errors.py`**

```python
"""Worktree-specific exceptions."""

from __future__ import annotations

from pathlib import Path

from eden.errors import EdenError


class WorktreeError(EdenError):
    """Base for worktree errors."""


class WorktreeLocked(WorktreeError):
    def __init__(self, *, lock_path: Path, holder_pid: int) -> None:
        self.lock_path = lock_path
        self.holder_pid = holder_pid
        super().__init__(
            f"worktree lock at {lock_path} held by pid {holder_pid}"
        )


class DirtyHostBlocked(WorktreeError):
    def __init__(
        self, *, host_repo_path: Path, dirty_files: tuple[str, ...]
    ) -> None:
        self.host_repo_path = host_repo_path
        self.dirty_files = dirty_files
        joined = ", ".join(dirty_files[:10]) or "(unknown)"
        super().__init__(
            f"host repo {host_repo_path} has uncommitted changes: {joined}"
        )


class BranchExists(WorktreeError):
    def __init__(self, *, branch: str) -> None:
        self.branch = branch
        super().__init__(f"branch {branch!r} already exists")


class GitCommandFailed(WorktreeError):
    def __init__(
        self, *, argv: tuple[str, ...], exit_code: int, stderr: str
    ) -> None:
        self.argv = argv
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"git command failed (exit {exit_code}): "
            f"{' '.join(argv)}\n{stderr}"
        )
```

- [ ] **Step 6: Create `eden/sandboxes/__init__.py`**

```bash
mkdir -p eden/sandboxes
```

Empty for now (filled in Task 12):

```python
"""Eden sandbox providers and factory — public surface assembled in later tasks."""
```

- [ ] **Step 7: Create `eden/sandboxes/errors.py`**

```python
"""Sandbox-provider exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from eden.errors import EdenError

if TYPE_CHECKING:
    from eden.providers._types import ExecResult, StrategyTag


class SandboxError(EdenError):
    """Base for sandbox-provider errors."""


class ProviderUnavailable(SandboxError):
    def __init__(self, *, provider: str, binary: str) -> None:
        self.provider = provider
        self.binary = binary
        super().__init__(
            f"provider {provider!r} requires binary {binary!r} on PATH"
        )


class ImageNotFound(SandboxError):
    def __init__(self, *, image: str, stderr: str) -> None:
        self.image = image
        self.stderr = stderr
        super().__init__(
            f"docker image {image!r} not found locally\n{stderr}"
        )


class ContainerStartFailed(SandboxError):
    def __init__(self, *, image: str, exit_code: int, stderr: str) -> None:
        self.image = image
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"docker run for image {image!r} failed (exit {exit_code})\n"
            f"{stderr}"
        )


class ExecFailed(SandboxError):
    def __init__(self, *, result: "ExecResult", argv_or_cmd: str) -> None:
        self.result = result
        self.argv_or_cmd = argv_or_cmd
        super().__init__(
            f"command {argv_or_cmd!r} failed (exit {result.exit_code})\n"
            f"{result.stderr}"
        )


class ExecTimeout(SandboxError):
    def __init__(
        self,
        *,
        cmd: str,
        timeout: float,
        partial_stdout: str,
        partial_stderr: str,
    ) -> None:
        self.cmd = cmd
        self.timeout = timeout
        self.partial_stdout = partial_stdout
        self.partial_stderr = partial_stderr
        super().__init__(f"command {cmd!r} timed out after {timeout}s")


class UnsupportedStrategy(SandboxError):
    def __init__(self, *, provider: str, strategy: "StrategyTag") -> None:
        self.provider = provider
        self.strategy = strategy
        super().__init__(
            f"provider {provider!r} does not support strategy "
            f"{strategy!r}"
        )
```

- [ ] **Step 8: Run errors test (will still fail until providers/_types is in place)**

```bash
python -m pytest tests/unit/test_errors.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.providers'` (the test imports `ExecResult`).

We will fix this in Task 2. Defer the green run.

- [ ] **Step 9: Run gates against what's there so far**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden
```

Expected: all three pass on the new files.

- [ ] **Step 10: Commit**

```bash
git add eden/errors.py eden/worktree/__init__.py eden/worktree/errors.py \
        eden/sandboxes/__init__.py eden/sandboxes/errors.py \
        tests/unit/__init__.py tests/unit/test_errors.py
git commit -m "feat: add EdenError base + Phase 2 exception subclasses"
```

---

## Task 2: Provider types — BranchStrategy, Mount, ExecResult, CreateOptions

**Files:**
- Create: `eden/providers/__init__.py`
- Create: `eden/providers/_types.py`
- Create: `tests/unit/test_branch_strategy.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_branch_strategy.py`:

```python
"""Verify BranchStrategy factory methods and frozen-dataclass semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    Mount,
)


pytestmark = pytest.mark.unit


def test_head_strategy() -> None:
    s = BranchStrategy.head()
    assert s.tag == "head"
    assert s.branch is None
    assert s.base == "main"


def test_merge_to_head_default_base() -> None:
    s = BranchStrategy.merge_to_head()
    assert s.tag == "merge_to_head"
    assert s.branch is None
    assert s.base == "main"


def test_merge_to_head_custom_base() -> None:
    s = BranchStrategy.merge_to_head(base="develop")
    assert s.base == "develop"


def test_named_strategy() -> None:
    s = BranchStrategy.named("feat/x")
    assert s.tag == "named"
    assert s.branch == "feat/x"
    assert s.base == "main"


def test_named_with_custom_base() -> None:
    s = BranchStrategy.named("feat/x", base="develop")
    assert s.base == "develop"


def test_branch_strategy_is_frozen() -> None:
    s = BranchStrategy.head()
    with pytest.raises(FrozenInstanceError):
        s.tag = "named"  # type: ignore[misc]


def test_mount_defaults_to_read_write() -> None:
    m = Mount(host=Path("/h"), sandbox=Path("/s"))
    assert m.read_only is False


def test_mount_read_only() -> None:
    m = Mount(host=Path("/h"), sandbox=Path("/s"), read_only=True)
    assert m.read_only is True


def test_mount_is_frozen() -> None:
    m = Mount(host=Path("/h"), sandbox=Path("/s"))
    with pytest.raises(FrozenInstanceError):
        m.read_only = True  # type: ignore[misc]


def test_exec_result_ok_property() -> None:
    assert ExecResult(stdout="", stderr="", exit_code=0).ok is True
    assert ExecResult(stdout="", stderr="", exit_code=1).ok is False


def test_exec_result_check_passes_on_zero() -> None:
    r = ExecResult(stdout="hi", stderr="", exit_code=0)
    assert r.check() is r


def test_exec_result_check_raises_on_nonzero() -> None:
    from eden.sandboxes.errors import ExecFailed
    r = ExecResult(stdout="", stderr="bad", exit_code=2)
    with pytest.raises(ExecFailed) as excinfo:
        r.check()
    assert excinfo.value.result is r


def test_create_options_holds_fields() -> None:
    opts = CreateOptions(
        branch="feat/x",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={"K": "V"},
        mounts=(Mount(host=Path("/a"), sandbox=Path("/b")),),
        name_hint="hint",
    )
    assert opts.branch == "feat/x"
    assert opts.env == {"K": "V"}
    assert len(opts.mounts) == 1


def test_create_options_is_frozen() -> None:
    opts = CreateOptions(
        branch="feat/x",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={},
        mounts=(),
        name_hint=None,
    )
    with pytest.raises(FrozenInstanceError):
        opts.branch = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_branch_strategy.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.providers'`.

- [ ] **Step 3: Create `eden/providers/__init__.py`**

```bash
mkdir -p eden/providers
```

Empty re-export shell (filled in Task 5):

```python
"""Eden provider Protocols and core types — public re-exports added in Task 5."""
```

- [ ] **Step 4: Create `eden/providers/_types.py`**

```python
"""Frozen dataclasses and aliases for the provider surface."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

StrategyTag = Literal["head", "merge_to_head", "named"]


@dataclass(frozen=True)
class BranchStrategy:
    tag: StrategyTag
    branch: str | None = None
    base: str = "main"

    @staticmethod
    def head() -> "BranchStrategy":
        return BranchStrategy(tag="head")

    @staticmethod
    def merge_to_head(base: str = "main") -> "BranchStrategy":
        return BranchStrategy(tag="merge_to_head", base=base)

    @staticmethod
    def named(branch: str, base: str = "main") -> "BranchStrategy":
        return BranchStrategy(tag="named", branch=branch, base=base)


@dataclass(frozen=True)
class Mount:
    host: Path
    sandbox: Path
    read_only: bool = False


@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def check(self) -> "ExecResult":
        if self.ok:
            return self
        # Lazy import to avoid eden.providers ↔ eden.sandboxes cycle.
        from eden.sandboxes.errors import ExecFailed

        raise ExecFailed(result=self, argv_or_cmd="<see result>")


@dataclass(frozen=True)
class CreateOptions:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    env: Mapping[str, str]
    mounts: tuple[Mount, ...]
    name_hint: str | None
```

- [ ] **Step 5: Run tests — expect green**

```bash
python -m pytest tests/unit/test_errors.py tests/unit/test_branch_strategy.py -v
```

Expected: 13 (errors) + 14 (strategy) = 27 passed.

- [ ] **Step 6: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add eden/providers/__init__.py eden/providers/_types.py \
        tests/unit/test_branch_strategy.py
git commit -m "feat: add BranchStrategy, Mount, ExecResult, CreateOptions"
```

---

## Task 3: Provider Protocols (SandboxProvider, SandboxHandle, BindMountSandboxHandle)

**Files:**
- Create: `eden/providers/_protocols.py`
- Create: `tests/unit/test_providers_protocol.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_providers_protocol.py`:

```python
"""Verify provider Protocols and runtime_checkable behavior."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxHandle,
    SandboxProvider,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
)


pytestmark = pytest.mark.unit


class _GoodHandle:
    worktree_path = Path("/wt")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        return None

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        return None

    def close(self) -> None:
        return None


class _BadHandleNoExec:
    worktree_path = Path("/wt")


class _GoodProvider:
    name = "fake"
    kind = "bind_mount"

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return True

    def create(self, opts: CreateOptions) -> SandboxHandle:
        return _GoodHandle()


def test_good_handle_satisfies_protocol() -> None:
    assert isinstance(_GoodHandle(), SandboxHandle)


def test_bad_handle_rejected() -> None:
    assert not isinstance(_BadHandleNoExec(), SandboxHandle)


def test_bind_mount_handle_subclasses_sandbox_handle() -> None:
    # A BindMountSandboxHandle is just a SandboxHandle with a marker tag.
    assert isinstance(_GoodHandle(), BindMountSandboxHandle)


def test_provider_protocol() -> None:
    p = _GoodProvider()
    assert isinstance(p, SandboxProvider)
    assert p.name == "fake"
    assert p.kind == "bind_mount"
    assert p.supports_strategy(BranchStrategy.head()) is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_providers_protocol.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.providers._protocols'`.

- [ ] **Step 3: Create `eden/providers/_protocols.py`**

```python
"""Runtime-checkable Protocols for sandbox providers and handles."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from eden.providers._types import BranchStrategy, CreateOptions, ExecResult


@runtime_checkable
class SandboxHandle(Protocol):
    worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult: ...

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...

    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class BindMountSandboxHandle(SandboxHandle, Protocol):
    """Marker — bind-mount providers don't add methods, but the type tag
    distinguishes them from isolated handles for orchestrator narrowing."""


@runtime_checkable
class SandboxProvider(Protocol):
    name: str
    kind: Literal["bind_mount", "isolated", "none"]

    def supports_strategy(self, strategy: BranchStrategy) -> bool: ...

    def create(self, opts: CreateOptions) -> SandboxHandle: ...
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_providers_protocol.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add eden/providers/_protocols.py tests/unit/test_providers_protocol.py
git commit -m "feat: add SandboxHandle, BindMountSandboxHandle, SandboxProvider Protocols"
```

---

## Task 4: `make_bind_mount_provider` helper

**Files:**
- Create: `eden/providers/_helpers.py`
- Create: `tests/unit/test_make_bind_mount_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_make_bind_mount_provider.py`:

```python
"""Verify make_bind_mount_provider produces a valid SandboxProvider."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
)


pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/wt")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        return None

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        return None

    def close(self) -> None:
        return None


def _make_create() -> Callable[[CreateOptions], BindMountSandboxHandle]:
    return lambda opts: _StubHandle()  # type: ignore[return-value]


def test_make_bind_mount_provider_basic() -> None:
    p = make_bind_mount_provider("stub", _make_create())
    assert isinstance(p, SandboxProvider)
    assert p.name == "stub"
    assert p.kind == "bind_mount"


def test_default_supports_all_three_strategies() -> None:
    p = make_bind_mount_provider("stub", _make_create())
    assert p.supports_strategy(BranchStrategy.head()) is True
    assert p.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert p.supports_strategy(BranchStrategy.named("x")) is True


def test_restricted_strategies() -> None:
    p = make_bind_mount_provider(
        "stub",
        _make_create(),
        supported_strategies=frozenset({"merge_to_head"}),
    )
    assert p.supports_strategy(BranchStrategy.head()) is False
    assert p.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert p.supports_strategy(BranchStrategy.named("x")) is False


def test_create_invokes_callable() -> None:
    seen: list[CreateOptions] = []

    def create(opts: CreateOptions) -> BindMountSandboxHandle:
        seen.append(opts)
        return _StubHandle()  # type: ignore[return-value]

    p = make_bind_mount_provider("stub", create)
    opts = CreateOptions(
        branch="main",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={},
        mounts=(),
        name_hint=None,
    )
    h = p.create(opts)
    assert seen == [opts]
    assert h.worktree_path == Path("/wt")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_make_bind_mount_provider.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.providers._helpers'`.

- [ ] **Step 3: Create `eden/providers/_helpers.py`**

```python
"""Factory helpers for assembling SandboxProvider instances."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxHandle,
    SandboxProvider,
)
from eden.providers._types import BranchStrategy, CreateOptions, StrategyTag


@dataclass
class _BindMountProvider:
    name: str
    kind: Literal["bind_mount"]
    _create_fn: Callable[[CreateOptions], BindMountSandboxHandle]
    _supported: frozenset[StrategyTag]

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return strategy.tag in self._supported

    def create(self, opts: CreateOptions) -> SandboxHandle:
        return self._create_fn(opts)


_DEFAULT_STRATEGIES: frozenset[StrategyTag] = frozenset(
    {"head", "merge_to_head", "named"}
)


def make_bind_mount_provider(
    name: str,
    create: Callable[[CreateOptions], BindMountSandboxHandle],
    *,
    supported_strategies: frozenset[StrategyTag] = _DEFAULT_STRATEGIES,
) -> SandboxProvider:
    """Wrap a `create` function into a `SandboxProvider` with kind=bind_mount."""
    return _BindMountProvider(
        name=name,
        kind="bind_mount",
        _create_fn=create,
        _supported=supported_strategies,
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_make_bind_mount_provider.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add eden/providers/_helpers.py tests/unit/test_make_bind_mount_provider.py
git commit -m "feat: add make_bind_mount_provider helper"
```

---

## Task 5: `eden.providers` public re-exports

**Files:**
- Modify: `eden/providers/__init__.py`

- [ ] **Step 1: Replace `eden/providers/__init__.py`**

Replace the placeholder with the full re-export surface:

```python
"""Public surface for sandbox providers and core types."""

from __future__ import annotations

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxHandle,
    SandboxProvider,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    Mount,
    StrategyTag,
)

__all__ = [
    "BindMountSandboxHandle",
    "BranchStrategy",
    "CreateOptions",
    "ExecResult",
    "Mount",
    "SandboxHandle",
    "SandboxProvider",
    "StrategyTag",
    "make_bind_mount_provider",
]
```

- [ ] **Step 2: Verify imports from the public namespace work**

Add a quick smoke test. Append to `tests/unit/test_providers_protocol.py`:

```python
def test_public_surface_importable() -> None:
    from eden.providers import (  # noqa: F401
        BindMountSandboxHandle,
        BranchStrategy,
        CreateOptions,
        ExecResult,
        Mount,
        SandboxHandle,
        SandboxProvider,
        StrategyTag,
        make_bind_mount_provider,
    )
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/unit -v
```

Expected: all unit tests so far pass (errors + branch_strategy + protocols + helpers + new public-surface test).

- [ ] **Step 4: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add eden/providers/__init__.py tests/unit/test_providers_protocol.py
git commit -m "feat: expose public eden.providers surface"
```

---

## Task 6: Worktree advisory lock

**Files:**
- Create: `eden/worktree/_lock.py`
- Create: `tests/unit/test_worktree_lock.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_worktree_lock.py`:

```python
"""Verify cross-platform advisory file lock with stale-PID recovery."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from eden.worktree._lock import acquire_lock
from eden.worktree.errors import WorktreeLocked


pytestmark = pytest.mark.unit


def test_acquire_creates_lock_file_with_pid(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    try:
        assert p.exists()
        assert p.read_text().strip() == str(os.getpid())
    finally:
        h.release()


def test_release_removes_lock_file(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    h.release()
    assert not p.exists()


def test_release_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    h.release()
    h.release()  # should not raise


def test_acquire_creates_parent_directory(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "deeper" / "lock"
    h = acquire_lock(p)
    try:
        assert p.exists()
    finally:
        h.release()


def test_recovers_from_stale_dead_pid(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    # Use a definitely-dead PID (2**31 - 1 is way past any normal PID range).
    dead_pid = 2**31 - 1
    p.write_text(str(dead_pid))
    h = acquire_lock(p)
    try:
        assert p.read_text().strip() == str(os.getpid())
    finally:
        h.release()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only flock test")
def test_blocks_when_holder_alive(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    try:
        # The current process holds the lock — a sibling acquire from the
        # same process raises because flock is per-fd in this code path
        # AND we read our own pid as the holder.
        with pytest.raises(WorktreeLocked) as excinfo:
            acquire_lock(p)
        assert excinfo.value.lock_path == p
        assert excinfo.value.holder_pid == os.getpid()
    finally:
        h.release()


def test_corrupt_pid_file_treated_as_stale(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-a-number")
    h = acquire_lock(p)
    try:
        assert p.read_text().strip() == str(os.getpid())
    finally:
        h.release()
```

Note: on Windows, `msvcrt.locking` is per-process and the second acquire from the same process may behave differently than POSIX `flock`. The `test_blocks_when_holder_alive` test is POSIX-only.

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_worktree_lock.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.worktree._lock'`.

- [ ] **Step 3: Create `eden/worktree/_lock.py`**

```python
"""Cross-platform advisory file lock with stale-PID recovery."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from eden.worktree.errors import WorktreeLocked

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:  # pragma: no cover - branch covered on Windows runners
    import msvcrt
else:
    import fcntl


@dataclass
class _LockHandle:
    path: Path
    fd: int = -1
    _released: list[bool] = field(default_factory=lambda: [False])

    def release(self) -> None:
        if self._released[0]:
            return
        self._released[0] = True
        if self.fd < 0:
            return
        try:
            if _IS_WINDOWS:  # pragma: no cover
                try:
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def _try_lock(fd: int) -> bool:
    try:
        if _IS_WINDOWS:  # pragma: no cover
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _read_pid(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire_lock(path: Path) -> _LockHandle:
    """Acquire an exclusive advisory lock on `path`.

    On contention, read the holder PID. If `os.kill(pid, 0)` raises
    `ProcessLookupError`, the holder is dead — unlink the file and retry once.
    Otherwise raise `WorktreeLocked`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(2):
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        if _try_lock(fd):
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode("ascii"))
            return _LockHandle(path=path, fd=fd)

        os.close(fd)

        if attempt == 0:
            holder_pid = _read_pid(path)
            if holder_pid is None or not _pid_alive(holder_pid):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                continue

        holder_pid = _read_pid(path) or 0
        raise WorktreeLocked(lock_path=path, holder_pid=holder_pid)

    holder_pid = _read_pid(path) or 0
    raise WorktreeLocked(lock_path=path, holder_pid=holder_pid)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_worktree_lock.py -v
```

Expected on Linux/macOS: 7 passed. On Windows: 6 passed, 1 skipped.

- [ ] **Step 5: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add eden/worktree/_lock.py tests/unit/test_worktree_lock.py
git commit -m "feat: add cross-platform worktree advisory lock"
```

---

## Task 7: Worktree git wrappers + `head` strategy

**Files:**
- Create: `eden/worktree/_git.py`
- Create: `eden/worktree/_create.py`
- Modify: `eden/worktree/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/test_worktree_head.py`

- [ ] **Step 1: Create the shared `tmp_git_repo` fixture**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures for the eden test suite."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Iterator[Path]:
    """Initialize a tmp git repo with one commit on the `main` branch."""
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    seed = tmp_path / "README.md"
    seed.write_text("seed\n")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    yield tmp_path
```

- [ ] **Step 2: Write the failing test for `head` strategy**

Create `tests/unit/test_worktree_head.py`:

```python
"""Verify create_worktree with the head strategy."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import (
    CloseResult,
    WorktreeHandle,
    create_worktree,
)
from eden.worktree.errors import DirtyHostBlocked, WorktreeLocked


pytestmark = pytest.mark.unit


def test_head_returns_unmanaged_handle_using_host_path(
    tmp_git_repo: Path,
) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
    )
    try:
        assert isinstance(h, WorktreeHandle)
        assert h.managed is False
        assert h.worktree_path == tmp_git_repo
        assert h.host_repo_path == tmp_git_repo
        assert h.branch == "HEAD"
    finally:
        h.close()


def test_head_blocks_on_dirty_host(tmp_git_repo: Path) -> None:
    (tmp_git_repo / "dirty.txt").write_text("uncommitted")
    with pytest.raises(DirtyHostBlocked) as excinfo:
        create_worktree(
            host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
        )
    assert excinfo.value.host_repo_path == tmp_git_repo
    assert any("dirty.txt" in f for f in excinfo.value.dirty_files)


def test_head_close_returns_released_only(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
    )
    result = h.close()
    assert isinstance(result, CloseResult)
    assert result.action == "released_only"


def test_head_lock_blocks_second_acquire(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
    )
    try:
        with pytest.raises(WorktreeLocked):
            create_worktree(
                host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
            )
    finally:
        h.close()


def test_head_close_is_idempotent(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
    )
    r1 = h.close()
    r2 = h.close()
    assert r1.action == "released_only"
    assert r2.action == "released_only"


def test_head_supports_context_manager(tmp_git_repo: Path) -> None:
    with create_worktree(
        host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()
    ) as h:
        assert h.managed is False
```

Note: `test_head_lock_blocks_second_acquire` only runs cleanly on POSIX where `flock` is per-fd; on Windows the second acquire may succeed because `msvcrt.locking` is per-process. Mark it accordingly.

Replace its decoration with:

```python
@pytest.mark.skipif(
    __import__("sys").platform == "win32",
    reason="msvcrt.locking is per-process; same-process re-acquire isn't blocked",
)
def test_head_lock_blocks_second_acquire(tmp_git_repo: Path) -> None:
    ...
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_worktree_head.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.worktree._create'`.

- [ ] **Step 4: Create `eden/worktree/_git.py`**

```python
"""Thin wrappers around git commands the worktree manager runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

from eden.worktree.errors import GitCommandFailed


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> tuple[str, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitCommandFailed(
            argv=argv, exit_code=proc.returncode, stderr=proc.stderr
        )
    return proc.stdout, proc.stderr


def status_porcelain(*, repo_path: Path) -> str:
    stdout, _ = _run_git(("git", "status", "--porcelain"), cwd=repo_path)
    return stdout


def branch_exists(*, repo_path: Path, branch: str) -> bool:
    proc = subprocess.run(
        ("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def worktree_add(
    *,
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    base: str,
) -> None:
    _run_git(
        (
            "git",
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            base,
        ),
        cwd=repo_path,
    )


def worktree_remove(*, repo_path: Path, worktree_path: Path) -> None:
    _run_git(
        ("git", "worktree", "remove", "--force", str(worktree_path)),
        cwd=repo_path,
    )
```

- [ ] **Step 5: Create `eden/worktree/_create.py` (head-only support for now)**

```python
"""Worktree manager: create_worktree, WorktreeHandle, CloseResult."""

from __future__ import annotations

import datetime as _dt
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from eden.providers._types import BranchStrategy
from eden.worktree._git import (
    branch_exists,
    status_porcelain,
    worktree_add,
    worktree_remove,
)
from eden.worktree._lock import _LockHandle, acquire_lock
from eden.worktree.errors import BranchExists, DirtyHostBlocked


_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


def _sanitize(name: str) -> str:
    s = _SANITIZE_RE.sub("-", name.lower()).strip("-")
    return s or "x"


@dataclass(frozen=True)
class CloseResult:
    action: Literal["removed", "preserved", "released_only"]
    reason: str | None = None


@dataclass(frozen=True)
class WorktreeHandle:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    managed: bool
    _lock_handle: _LockHandle = field(repr=False)
    _closed: list[bool] = field(
        default_factory=lambda: [False], repr=False
    )

    def __enter__(self) -> "WorktreeHandle":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> CloseResult:
        if self._closed[0]:
            return CloseResult(action="released_only", reason="already-closed")
        self._closed[0] = True
        try:
            if not self.managed:
                return CloseResult(action="released_only")
            dirty = bool(
                status_porcelain(repo_path=self.worktree_path).strip()
            )
            if dirty:
                print(
                    f"eden: leaving dirty worktree on disk at "
                    f"{self.worktree_path}"
                )
                return CloseResult(action="preserved", reason="dirty")
            worktree_remove(
                repo_path=self.host_repo_path,
                worktree_path=self.worktree_path,
            )
            return CloseResult(action="removed")
        finally:
            self._lock_handle.release()


def _generate_branch(name_hint: str | None) -> str:
    suffix = secrets.token_hex(4)
    if name_hint:
        return f"eden/{_sanitize(name_hint)}-{suffix}"
    ts = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"eden/{ts}-{suffix}"


def _lock_path_for(host_repo_path: Path, branch: str | None) -> Path:
    base = host_repo_path / ".eden" / "worktrees"
    if branch is None:
        return base / "_head.lock"
    return base / f"{_sanitize(branch)}.lock"


def _worktree_path_for(host_repo_path: Path, branch: str) -> Path:
    return host_repo_path / ".eden" / "worktrees" / _sanitize(branch)


def create_worktree(
    *,
    host_repo_path: Path,
    strategy: BranchStrategy,
    name_hint: str | None = None,
) -> WorktreeHandle:
    if strategy.tag == "head":
        dirty = status_porcelain(repo_path=host_repo_path).strip()
        if dirty:
            files = tuple(
                line[3:]
                for line in dirty.splitlines()
                if len(line) > 3
            )[:10]
            raise DirtyHostBlocked(
                host_repo_path=host_repo_path, dirty_files=files
            )
        lock = acquire_lock(_lock_path_for(host_repo_path, None))
        return WorktreeHandle(
            branch="HEAD",
            worktree_path=host_repo_path,
            host_repo_path=host_repo_path,
            managed=False,
            _lock_handle=lock,
        )

    if strategy.tag == "merge_to_head":
        branch = _generate_branch(name_hint)
    else:  # named
        assert strategy.branch is not None
        branch = strategy.branch
        if branch_exists(repo_path=host_repo_path, branch=branch):
            raise BranchExists(branch=branch)

    wt_path = _worktree_path_for(host_repo_path, branch)
    lock = acquire_lock(_lock_path_for(host_repo_path, branch))
    try:
        worktree_add(
            repo_path=host_repo_path,
            worktree_path=wt_path,
            branch=branch,
            base=strategy.base,
        )
    except Exception:
        lock.release()
        raise

    return WorktreeHandle(
        branch=branch,
        worktree_path=wt_path,
        host_repo_path=host_repo_path,
        managed=True,
        _lock_handle=lock,
    )
```

- [ ] **Step 6: Update `eden/worktree/__init__.py` to expose head-strategy public surface**

```python
"""Worktree manager — public surface."""

from __future__ import annotations

from eden.worktree._create import (
    CloseResult,
    WorktreeHandle,
    create_worktree,
)

__all__ = ["CloseResult", "WorktreeHandle", "create_worktree"]
```

- [ ] **Step 7: Run head-strategy tests**

```bash
python -m pytest tests/unit/test_worktree_head.py -v
```

Expected: all tests pass on Linux/macOS (one skipped on Windows).

- [ ] **Step 8: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add eden/worktree/_git.py eden/worktree/_create.py \
        eden/worktree/__init__.py tests/conftest.py \
        tests/unit/test_worktree_head.py
git commit -m "feat: add create_worktree head strategy + WorktreeHandle"
```

---

## Task 8: Worktree `merge_to_head` and `named` strategies

**Files:**
- Create: `tests/unit/test_worktree_strategies.py`

(No production code changes needed — Task 7 already shipped the full `create_worktree` body. This task validates the merge_to_head and named branches end-to-end.)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_worktree_strategies.py`:

```python
"""Verify merge_to_head and named worktree strategies."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import create_worktree
from eden.worktree.errors import BranchExists


pytestmark = pytest.mark.unit


def _branch_of(repo: Path, worktree: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return out


def test_merge_to_head_creates_managed_worktree(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
    )
    try:
        assert h.managed is True
        assert h.branch.startswith("eden/")
        assert h.worktree_path.exists()
        assert h.worktree_path != tmp_git_repo
        assert _branch_of(tmp_git_repo, h.worktree_path) == h.branch
    finally:
        h.close()


def test_merge_to_head_uses_name_hint(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
        name_hint="My Feature!",
    )
    try:
        assert h.branch.startswith("eden/my-feature-")
    finally:
        h.close()


def test_merge_to_head_close_removes_clean_worktree(
    tmp_git_repo: Path,
) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
    )
    wt = h.worktree_path
    result = h.close()
    assert result.action == "removed"
    assert not wt.exists()


def test_merge_to_head_close_preserves_dirty_worktree(
    tmp_git_repo: Path,
) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
    )
    (h.worktree_path / "uncommitted.txt").write_text("dirt")
    result = h.close()
    assert result.action == "preserved"
    assert result.reason == "dirty"
    assert h.worktree_path.exists()


def test_named_strategy_creates_branch(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/x"),
    )
    try:
        assert h.branch == "feat/x"
        assert _branch_of(tmp_git_repo, h.worktree_path) == "feat/x"
    finally:
        h.close()


def test_named_strategy_rejects_existing_branch(tmp_git_repo: Path) -> None:
    subprocess.run(
        ["git", "branch", "feat/exists"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    with pytest.raises(BranchExists) as excinfo:
        create_worktree(
            host_repo_path=tmp_git_repo,
            strategy=BranchStrategy.named("feat/exists"),
        )
    assert excinfo.value.branch == "feat/exists"


def test_named_with_custom_base(tmp_git_repo: Path) -> None:
    subprocess.run(
        ["git", "checkout", "-b", "develop"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/y", base="develop"),
    )
    try:
        assert h.branch == "feat/y"
    finally:
        h.close()
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/unit/test_worktree_strategies.py -v
```

Expected: 7 passed.

- [ ] **Step 3: Run all worktree tests + gates**

```bash
python -m pytest tests/unit -v
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_worktree_strategies.py
git commit -m "test: cover merge_to_head and named worktree strategies"
```

---

## Task 9: `stream_exec` subprocess helper

**Files:**
- Create: `eden/sandboxes/_exec.py`
- Create: `tests/unit/test_stream_exec.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_stream_exec.py`:

```python
"""Verify stream_exec subprocess streaming helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.sandboxes._exec import stream_exec
from eden.sandboxes.errors import ExecTimeout


pytestmark = pytest.mark.unit


def test_zero_exit_captures_stdout() -> None:
    result = stream_exec(
        [sys.executable, "-c", "print('hello')"],
        cmd_for_error="python -c print",
        shell=False,
    )
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.ok is True


def test_nonzero_exit_returned_in_result() -> None:
    result = stream_exec(
        [sys.executable, "-c", "import sys; sys.exit(7)"],
        cmd_for_error="python -c sys.exit(7)",
        shell=False,
    )
    assert result.exit_code == 7
    assert result.ok is False


def test_stderr_captured_separately() -> None:
    result = stream_exec(
        [
            sys.executable,
            "-c",
            "import sys; print('e', file=sys.stderr); print('o')",
        ],
        cmd_for_error="python -c stderr",
        shell=False,
    )
    assert "o" in result.stdout
    assert "e" in result.stderr


def test_on_line_callback_invoked_per_line() -> None:
    seen: list[str] = []
    stream_exec(
        [sys.executable, "-c", "print('a'); print('b')"],
        cmd_for_error="python -c print",
        shell=False,
        on_line=seen.append,
    )
    assert "a" in seen
    assert "b" in seen


def test_shell_mode_uses_shell() -> None:
    result = stream_exec(
        "echo shellmode" if sys.platform != "win32" else "echo shellmode",
        cmd_for_error="echo shellmode",
        shell=True,
    )
    assert result.exit_code == 0
    assert "shellmode" in result.stdout


def test_cwd_is_respected(tmp_path: Path) -> None:
    result = stream_exec(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cmd_for_error="getcwd",
        shell=False,
        cwd=tmp_path,
    )
    assert str(tmp_path) in result.stdout


def test_env_passthrough() -> None:
    result = stream_exec(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('EDEN_TEST_KEY', '<missing>'))",
        ],
        cmd_for_error="env",
        shell=False,
        env={"EDEN_TEST_KEY": "passed"},
    )
    assert "passed" in result.stdout


def test_timeout_raises_exec_timeout() -> None:
    with pytest.raises(ExecTimeout) as excinfo:
        stream_exec(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            cmd_for_error="sleep 60",
            shell=False,
            timeout=0.5,
        )
    assert excinfo.value.timeout == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_stream_exec.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.sandboxes._exec'`.

- [ ] **Step 3: Create `eden/sandboxes/_exec.py`**

```python
"""Streaming subprocess helper used by no_sandbox and docker handles."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from queue import Empty, Queue
from typing import IO, Any

from eden.providers._types import ExecResult
from eden.sandboxes.errors import ExecTimeout


_SENTINEL: Any = object()


def _drain(stream: IO[str], queue: Queue[Any]) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        queue.put(_SENTINEL)


def stream_exec(
    argv: list[str] | str,
    *,
    cmd_for_error: str,
    shell: bool = False,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
    timeout: float | None = None,
) -> ExecResult:
    """Run a subprocess with line-buffered stdout+stderr drained via threads.

    On `timeout`: SIGTERM, then SIGKILL after a 5s grace, then raise
    `ExecTimeout` carrying whatever was captured.
    """
    merged_env: dict[str, str] = dict(os.environ)
    if env:
        merged_env.update(env)

    proc = subprocess.Popen(
        argv,
        shell=shell,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout_q: Queue[Any] = Queue()
    stderr_q: Queue[Any] = Queue()
    t_out = threading.Thread(
        target=_drain, args=(proc.stdout, stdout_q), daemon=True
    )
    t_err = threading.Thread(
        target=_drain, args=(proc.stderr, stderr_q), daemon=True
    )
    t_out.start()
    t_err.start()

    out_chunks: list[str] = []
    err_chunks: list[str] = []
    out_done = False
    err_done = False
    deadline = (time.monotonic() + timeout) if timeout is not None else None

    while not (out_done and err_done):
        if deadline is not None and time.monotonic() > deadline:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise ExecTimeout(
                cmd=cmd_for_error,
                timeout=timeout or 0.0,
                partial_stdout="".join(out_chunks),
                partial_stderr="".join(err_chunks),
            )

        if not out_done:
            try:
                item = stdout_q.get(timeout=0.05)
            except Empty:
                item = None
            if item is _SENTINEL:
                out_done = True
            elif item is not None:
                out_chunks.append(item)
                if on_line is not None:
                    on_line(item.rstrip("\n"))

        if not err_done:
            try:
                item = stderr_q.get(timeout=0.05)
            except Empty:
                item = None
            if item is _SENTINEL:
                err_done = True
            elif item is not None:
                err_chunks.append(item)
                if on_line is not None:
                    on_line(item.rstrip("\n"))

    proc.wait()
    return ExecResult(
        stdout="".join(out_chunks),
        stderr="".join(err_chunks),
        exit_code=proc.returncode,
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_stream_exec.py -v
```

Expected: 8 passed (timeout test takes ~0.5s).

- [ ] **Step 5: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add eden/sandboxes/_exec.py tests/unit/test_stream_exec.py
git commit -m "feat: add stream_exec subprocess helper with timeout"
```

---

## Task 10: `no_sandbox` provider

**Files:**
- Create: `eden/sandboxes/no_sandbox/__init__.py`
- Create: `tests/unit/test_no_sandbox.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_no_sandbox.py`:

```python
"""Verify the no_sandbox provider."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.no_sandbox import provider


pytestmark = pytest.mark.unit


def test_provider_metadata() -> None:
    p = provider()
    assert p.name == "no_sandbox"
    assert p.kind == "bind_mount"
    assert p.supports_strategy(BranchStrategy.head()) is True
    assert p.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert p.supports_strategy(BranchStrategy.named("x")) is True


def test_handle_exec_runs_in_worktree(tmp_path: Path) -> None:
    p = provider()
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        result = handle.exec(
            f'"{sys.executable}" -c "import os; print(os.getcwd())"'
        )
        assert result.exit_code == 0
        assert str(tmp_path) in result.stdout
    finally:
        handle.close()


def test_handle_exec_explicit_cwd_overrides(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    p = provider()
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        result = handle.exec(
            f'"{sys.executable}" -c "import os; print(os.getcwd())"',
            cwd=sub,
        )
        assert str(sub) in result.stdout
    finally:
        handle.close()


def test_handle_copy_in_and_out(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("body")
    dst = tmp_path / "b.txt"
    handle = provider().create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        handle.copy_file_in(src, dst)
        assert dst.read_text() == "body"
        out = tmp_path / "c.txt"
        handle.copy_file_out(dst, out)
        assert out.read_text() == "body"
    finally:
        handle.close()


def test_handle_close_is_noop(tmp_path: Path) -> None:
    handle = provider().create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    handle.close()
    handle.close()  # idempotent
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_no_sandbox.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.sandboxes.no_sandbox'`.

- [ ] **Step 3: Create `eden/sandboxes/no_sandbox/__init__.py`**

```bash
mkdir -p eden/sandboxes/no_sandbox
```

Then write:

```python
"""no_sandbox: run commands directly on the host via subprocess+shell."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes._exec import stream_exec


@dataclass
class _NoSandboxHandle:
    worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return stream_exec(
            cmd,
            cmd_for_error=cmd,
            shell=True,
            cwd=cwd or self.worktree_path,
            env=env,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        shutil.copy2(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        shutil.copy2(sandbox, host)

    def close(self) -> None:
        return None


def _create_no_sandbox(opts: CreateOptions) -> BindMountSandboxHandle:
    return _NoSandboxHandle(worktree_path=opts.worktree_path)  # type: ignore[return-value]


def provider() -> SandboxProvider:
    return make_bind_mount_provider(
        name="no_sandbox",
        create=_create_no_sandbox,
        supported_strategies=frozenset({"head", "merge_to_head", "named"}),
    )


__all__ = ["provider"]
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_no_sandbox.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add eden/sandboxes/no_sandbox/__init__.py tests/unit/test_no_sandbox.py
git commit -m "feat: add no_sandbox provider"
```

---

## Task 11: `docker` provider (unit-tested with mocked subprocess)

**Files:**
- Create: `eden/sandboxes/docker/__init__.py`
- Create: `tests/unit/test_docker_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_docker_provider.py`:

```python
"""Verify the docker provider with mocked subprocess + shutil.which."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from eden.providers._types import CreateOptions, Mount
from eden.sandboxes import docker as docker_mod
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ProviderUnavailable,
)


pytestmark = pytest.mark.unit


@dataclass
class _Recorded:
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


@dataclass
class _SubprocessFake:
    queue: list[tuple[str, str, int]] = field(default_factory=list)
    calls: list[_Recorded] = field(default_factory=list)
    which_returns: str | None = "/usr/bin/docker"

    def queue_run(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.queue.append((stdout, stderr, returncode))

    def run(self, argv: list[str], *args: Any, **kwargs: Any) -> Any:
        if not self.queue:
            raise AssertionError(f"unexpected subprocess.run({argv!r})")
        out, err, rc = self.queue.pop(0)
        rec = _Recorded(
            argv=tuple(argv), stdout=out, stderr=err, returncode=rc
        )
        self.calls.append(rec)
        return subprocess.CompletedProcess(
            args=argv, returncode=rc, stdout=out, stderr=err
        )


@pytest.fixture
def fake_subprocess(monkeypatch: pytest.MonkeyPatch) -> _SubprocessFake:
    fake = _SubprocessFake()
    monkeypatch.setattr(
        "eden.sandboxes.docker.shutil.which",
        lambda name: fake.which_returns,
    )
    monkeypatch.setattr(
        "eden.sandboxes.docker.subprocess.run", fake.run
    )
    return fake


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="feat/x",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={"USER_KEY": "u"},
        mounts=(),
        name_hint="hint",
    )


def test_provider_metadata() -> None:
    p = docker_mod.provider(image="alpine:3.20")
    assert p.name == "docker"
    assert p.kind == "bind_mount"


def test_create_raises_when_docker_missing(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.which_returns = None
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ProviderUnavailable):
        p.create(_opts(tmp_path))


def test_create_raises_when_image_missing(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(
        stderr="No such image", returncode=1
    )  # docker image inspect
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ImageNotFound) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.image == "alpine:3.20"


def test_create_raises_when_run_fails(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)  # image inspect succeeds
    fake_subprocess.queue_run(
        stderr="cannot start", returncode=125
    )  # docker run fails
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ContainerStartFailed) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.exit_code == 125


def test_create_builds_expected_argv(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)  # run
    p = docker_mod.provider(
        image="alpine:3.20",
        env={"PROVIDER_KEY": "v"},
        network="bridge",
    )
    handle = p.create(_opts(tmp_path))
    assert handle.worktree_path == Path("/workspace")  # type: ignore[attr-defined]

    run_call = fake_subprocess.calls[1]
    assert run_call.argv[:5] == ("docker", "run", "-d", "--rm", "-i")
    # contains workspace bind
    assert any(
        f"{tmp_path}:/workspace" == a
        for a in run_call.argv
    )
    # contains both env vars
    joined = " ".join(run_call.argv)
    assert "PROVIDER_KEY=v" in joined
    assert "USER_KEY=u" in joined
    # network
    assert "bridge" in run_call.argv
    # entrypoint sleep + image + infinity argument tail
    assert "--entrypoint" in run_call.argv
    assert "sleep" in run_call.argv
    assert run_call.argv[-2] == "alpine:3.20"
    assert run_call.argv[-1] == "infinity"


def test_provider_mount_overrides_caller_mount(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(stdout="cid\n", returncode=0)
    caller_mount = Mount(host=tmp_path / "a", sandbox=Path("/data"))
    provider_mount = Mount(
        host=tmp_path / "b", sandbox=Path("/data"), read_only=True
    )
    p = docker_mod.provider(image="alpine:3.20", mounts=(provider_mount,))
    p.create(
        CreateOptions(
            branch="feat/x",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(caller_mount,),
            name_hint=None,
        )
    )
    run_argv = fake_subprocess.calls[1].argv
    # Provider override wins -> /data should map to b, not a.
    bind_strings = [
        run_argv[i + 1]
        for i, a in enumerate(run_argv)
        if a == "-v"
    ]
    matching = [s for s in bind_strings if s.endswith(":/data:ro")]
    assert matching, f"expected /data bind with ro, got {bind_strings!r}"
    assert any(str(tmp_path / "b") in s for s in matching)
    assert not any(str(tmp_path / "a") in s for s in bind_strings)


def test_handle_exec_uses_docker_exec(
    tmp_path: Path,
    fake_subprocess: _SubprocessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))

    captured: dict[str, Any] = {}

    def fake_stream_exec(argv: list[str], **kwargs: Any) -> Any:
        from eden.providers._types import ExecResult

        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return ExecResult(stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr(
        "eden.sandboxes.docker.stream_exec", fake_stream_exec
    )
    result = handle.exec(
        "echo hi", cwd=Path("/workspace/sub"), env={"K": "V"}
    )
    assert result.exit_code == 0
    argv = captured["argv"]
    assert argv[0:3] == ["docker", "exec", "-i"]
    assert "-w" in argv
    assert "/workspace/sub" in argv
    assert "-e" in argv
    assert "K=V" in argv
    assert "cid123" in argv
    assert argv[-3:] == ["/bin/sh", "-c", "echo hi"]


def test_handle_close_calls_docker_kill(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)  # docker kill
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.close()
    kill_call = fake_subprocess.calls[2]
    assert kill_call.argv == ("docker", "kill", "cid123")


def test_handle_close_swallows_no_such_container(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(
        stderr="Error: No such container: cid123", returncode=1
    )
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.close()  # must not raise


def test_handle_copy_in_invokes_docker_cp(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)  # docker cp
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.copy_file_in(tmp_path / "x", Path("/sandbox/y"))
    cp_call = fake_subprocess.calls[2]
    assert cp_call.argv[0:2] == ("docker", "cp")
    assert cp_call.argv[-1] == "cid123:/sandbox/y"


def test_handle_copy_out_invokes_docker_cp(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.copy_file_out(Path("/sandbox/y"), tmp_path / "x")
    cp_call = fake_subprocess.calls[2]
    assert cp_call.argv[0:2] == ("docker", "cp")
    assert cp_call.argv[2] == "cid123:/sandbox/y"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_docker_provider.py -v
```

Expected: `ModuleNotFoundError: No module named 'eden.sandboxes.docker'`.

- [ ] **Step 3: Create `eden/sandboxes/docker/__init__.py`**

```bash
mkdir -p eden/sandboxes/docker
```

Then write:

```python
"""docker provider: run commands inside a long-lived docker container."""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

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
class _DockerHandle:
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
        argv: list[str] = ["docker", "exec", "-i"]
        if cwd is not None:
            argv.extend(["-w", str(cwd)])
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
            ["docker", "cp", str(host), f"{self.container_id}:{sandbox}"],
            check=True,
            capture_output=True,
            text=True,
        )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        subprocess.run(
            ["docker", "cp", f"{self.container_id}:{sandbox}", str(host)],
            check=True,
            capture_output=True,
            text=True,
        )

    def close(self) -> None:
        proc = subprocess.run(
            ["docker", "kill", self.container_id],
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


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    provider_mounts: tuple[Mount, ...] = mounts or ()
    provider_env: dict[str, str] = dict(env) if env else {}

    def _create(opts: CreateOptions) -> BindMountSandboxHandle:
        if not shutil.which("docker"):
            raise ProviderUnavailable(provider="docker", binary="docker")

        inspect = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            raise ImageNotFound(image=image, stderr=inspect.stderr)

        # Mount precedence: implicit /workspace, then opts.mounts, then
        # provider_mounts (last write wins on sandbox-path collision).
        mount_map: dict[Path, Mount] = {}
        mount_map[Path("/workspace")] = Mount(
            host=opts.worktree_path, sandbox=Path("/workspace")
        )
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
            "docker",
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
            spec = f"{m.host}:{m.sandbox}"
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
        return _DockerHandle(  # type: ignore[return-value]
            container_id=container_id,
            worktree_path=Path("/workspace"),
            host_worktree_path=opts.worktree_path,
        )

    return make_bind_mount_provider(name="docker", create=_create)


__all__ = ["provider"]
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_docker_provider.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add eden/sandboxes/docker/__init__.py tests/unit/test_docker_provider.py
git commit -m "feat: add docker provider MVP (subprocess-mocked unit tests)"
```

---

## Task 12: `create_sandbox` factory + `Sandbox` wrapper + public re-exports

**Files:**
- Create: `eden/sandboxes/_factory.py`
- Modify: `eden/sandboxes/__init__.py`
- Create: `tests/unit/test_create_sandbox.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_create_sandbox.py`:

```python
"""Verify the top-level create_sandbox factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

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

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

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


def test_unsupported_strategy_raises(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider(supported=frozenset({"merge_to_head"}))
    with pytest.raises(UnsupportedStrategy):
        create_sandbox(
            sandbox=p, branch_strategy=BranchStrategy.head()
        )


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


def test_close_closes_handle_then_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p)
    handle = s.handle
    s.close()
    assert handle.closed[0] is True  # type: ignore[attr-defined]


def test_sandbox_is_context_manager(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    with create_sandbox(sandbox=p) as s:
        assert isinstance(s, Sandbox)


def test_cwd_stored_on_sandbox(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = _StubProvider()
    s = create_sandbox(sandbox=p, cwd=Path("/some/cwd"))
    try:
        assert s.cwd == Path("/some/cwd")
    finally:
        s.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_create_sandbox.py -v
```

Expected: `ImportError: cannot import name 'create_sandbox' from 'eden.sandboxes'`.

- [ ] **Step 3: Create `eden/sandboxes/_factory.py`**

```python
"""create_sandbox top-level factory + Sandbox context-manager wrapper."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes.errors import UnsupportedStrategy
from eden.worktree._create import WorktreeHandle, create_worktree


@dataclass
class Sandbox:
    worktree: WorktreeHandle
    handle: SandboxHandle
    cwd: Path | None = None

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.handle.close()
        finally:
            self.worktree.close()


def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
) -> Sandbox:
    """Resolve branch/strategy, carve a worktree, and create the sandbox handle."""
    if branch is not None and branch_strategy is not None:
        raise ValueError(
            "branch and branch_strategy are mutually exclusive"
        )

    if branch is not None:
        strategy = BranchStrategy.named(branch)
    elif branch_strategy is not None:
        strategy = branch_strategy
    elif sandbox.kind == "none":
        strategy = BranchStrategy.head()
    else:
        strategy = BranchStrategy.merge_to_head()

    if not sandbox.supports_strategy(strategy):
        raise UnsupportedStrategy(
            provider=sandbox.name, strategy=strategy.tag
        )

    wt = create_worktree(
        host_repo_path=Path.cwd(),
        strategy=strategy,
        name_hint=name,
    )

    try:
        handle = sandbox.create(
            CreateOptions(
                branch=wt.branch,
                worktree_path=wt.worktree_path,
                host_repo_path=wt.host_repo_path,
                env=env or {},
                mounts=mounts or (),
                name_hint=name,
            )
        )
    except Exception:
        wt.close()
        raise

    return Sandbox(worktree=wt, handle=handle, cwd=cwd)
```

- [ ] **Step 4: Replace `eden/sandboxes/__init__.py` with public re-exports**

```python
"""Public surface for sandbox providers and the create_sandbox factory."""

from __future__ import annotations

from eden.sandboxes._factory import Sandbox, create_sandbox

__all__ = ["Sandbox", "create_sandbox"]
```

- [ ] **Step 5: Run create_sandbox tests**

```bash
python -m pytest tests/unit/test_create_sandbox.py -v
```

Expected: 9 passed.

- [ ] **Step 6: Run the full unit suite + gates**

```bash
python -m pytest tests/unit -v
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all unit tests pass; all gates pass.

- [ ] **Step 7: Commit**

```bash
git add eden/sandboxes/_factory.py eden/sandboxes/__init__.py \
        tests/unit/test_create_sandbox.py
git commit -m "feat: add create_sandbox factory and Sandbox wrapper"
```

---

## Task 13: Docker integration tests

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/Dockerfile`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_docker_lifecycle.py`
- Create: `tests/integration/test_docker_exec.py`
- Create: `tests/integration/test_docker_copy.py`

- [ ] **Step 1: Create the integration test directory marker**

```bash
mkdir -p tests/integration
: > tests/integration/__init__.py
```

- [ ] **Step 2: Create the test Dockerfile**

Create `tests/integration/Dockerfile`:

```dockerfile
# Eden integration test image.
# Minimal alpine + git + bash; sleep is the entrypoint set at run time.
FROM alpine:3.20

RUN apk add --no-cache bash git

WORKDIR /workspace
```

- [ ] **Step 3: Create the integration conftest with image fixture**

Create `tests/integration/conftest.py`:

```python
"""Session-scoped fixtures for docker integration tests."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest


# Skip the entire integration suite on non-Linux runners.
if sys.platform != "linux":
    pytest.skip(
        "docker daemon only available on linux runners",
        allow_module_level=True,
    )


_DOCKERFILE = Path(__file__).resolve().parent / "Dockerfile"


def _hash_dockerfile() -> str:
    return hashlib.sha256(_DOCKERFILE.read_bytes()).hexdigest()[:12]


@pytest.fixture(scope="session")
def eden_test_image() -> Iterator[str]:
    if not shutil.which("docker"):
        pytest.skip("docker binary not available")

    info = subprocess.run(
        ["docker", "info"], capture_output=True, text=True
    )
    if info.returncode != 0:
        pytest.skip("docker daemon not reachable")

    tag = f"eden-test:{_hash_dockerfile()}"
    inspect = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
        text=True,
    )
    if inspect.returncode != 0:
        build = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                tag,
                "-f",
                str(_DOCKERFILE),
                str(_DOCKERFILE.parent),
            ],
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            pytest.fail(
                f"failed to build {tag}: {build.stderr}",
                pytrace=False,
            )
    yield tag
```

- [ ] **Step 4: Create lifecycle test**

Create `tests/integration/test_docker_lifecycle.py`:

```python
"""Smoke test: docker provider create → exec → close cycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.docker import provider


pytestmark = pytest.mark.integration


def test_create_exec_close(
    eden_test_image: str, tmp_path: Path
) -> None:
    p = provider(image=eden_test_image)
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="lifecycle",
        )
    )
    try:
        result = handle.exec("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
    finally:
        handle.close()


def test_close_removes_container(
    eden_test_image: str, tmp_path: Path
) -> None:
    p = provider(image=eden_test_image)
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="cleanup",
        )
    )
    cid = handle.container_id  # type: ignore[attr-defined]
    handle.close()

    inspect = subprocess.run(
        ["docker", "inspect", cid],
        capture_output=True,
        text=True,
    )
    assert inspect.returncode != 0  # gone after kill + --rm
```

- [ ] **Step 5: Create exec tests**

Create `tests/integration/test_docker_exec.py`:

```python
"""Verify docker exec wiring: cwd, env, on_line, exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.docker import provider


pytestmark = pytest.mark.integration


@pytest.fixture
def handle(eden_test_image: str, tmp_path: Path):
    p = provider(image=eden_test_image)
    h = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={"GLOBAL": "global-val"},
            mounts=(),
            name_hint="exec",
        )
    )
    yield h
    h.close()


def test_default_cwd_is_workspace(handle) -> None:
    result = handle.exec("pwd")
    assert "/workspace" in result.stdout


def test_explicit_cwd_overrides(handle) -> None:
    result = handle.exec("pwd", cwd=Path("/tmp"))
    assert "/tmp" in result.stdout


def test_env_visible_to_command(handle) -> None:
    result = handle.exec("echo $GLOBAL")
    assert "global-val" in result.stdout


def test_per_call_env_overrides(handle) -> None:
    result = handle.exec("echo $LOCAL", env={"LOCAL": "x"})
    assert "x" in result.stdout


def test_nonzero_exit_returned(handle) -> None:
    result = handle.exec("exit 7")
    assert result.exit_code == 7


def test_on_line_callback_invoked(handle) -> None:
    seen: list[str] = []
    handle.exec("echo a; echo b", on_line=seen.append)
    assert "a" in seen
    assert "b" in seen
```

- [ ] **Step 6: Create copy tests**

Create `tests/integration/test_docker_copy.py`:

```python
"""Verify docker cp wiring (copy_file_in / copy_file_out)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.docker import provider


pytestmark = pytest.mark.integration


def test_copy_in_and_out_round_trip(
    eden_test_image: str, tmp_path: Path
) -> None:
    p = provider(image=eden_test_image)
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="copy",
        )
    )
    try:
        src = tmp_path / "in.txt"
        src.write_text("hello in")
        handle.copy_file_in(src, Path("/tmp/in.txt"))
        result = handle.exec("cat /tmp/in.txt")
        assert "hello in" in result.stdout

        handle.exec("echo 'hello out' > /tmp/out.txt")
        dest = tmp_path / "out.txt"
        handle.copy_file_out(Path("/tmp/out.txt"), dest)
        assert "hello out" in dest.read_text()
    finally:
        handle.close()
```

- [ ] **Step 7: Run unit suite and confirm integration suite skips on non-Linux**

```bash
python -m pytest tests/unit -v
python -m pytest tests/integration -v
```

Expected on macOS/Windows: integration suite reports "skipped" at the module level. On Linux with docker available: integration suite passes.

- [ ] **Step 8: Run gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 9: Update CI workflow to include the integration step on Linux only**

Modify `.github/workflows/ci.yml`. Find the `pytest` step (the last step in the `test` job from Phase 1):

```yaml
      - name: pytest
        run: pytest -v
```

Replace it with:

```yaml
      - name: pytest (unit)
        run: pytest -v -m unit

      - name: pytest (integration)
        if: runner.os == 'Linux'
        run: pytest -v -m integration
```

Note: this still runs all *non*-marked tests (e.g., the existing Phase 1 `test_version.py` and `test_cli.py`) as part of the unit step? Not unless they have `pytestmark = pytest.mark.unit`. Add that marker by appending `pytestmark = pytest.mark.unit` to `tests/test_version.py` and `tests/test_cli.py`.

**Modify** `tests/test_version.py` — add at top below the docstring:

```python
import pytest

pytestmark = pytest.mark.unit
```

**Modify** `tests/test_cli.py` — same:

```python
import pytest

pytestmark = pytest.mark.unit
```

- [ ] **Step 10: Run the full suite and confirm everything is wired**

```bash
python -m pytest -m unit -v
python -m pytest -m integration -v  # skipped on non-Linux
```

Expected:
- `-m unit`: all Phase 1 + Phase 2 unit tests pass.
- `-m integration`: zero collected (or all skipped) on non-Linux.

- [ ] **Step 11: Commit**

```bash
git add tests/integration/ .github/workflows/ci.yml \
        tests/test_version.py tests/test_cli.py
git commit -m "test: add docker integration suite + split unit/integration in CI"
```

- [ ] **Step 12: Push and watch CI**

```bash
git push
gh run watch
```

Expected: 9-job matrix passes; integration step runs only on the 3 Linux jobs and passes there. If any fail, drill in:

```bash
gh run view --log-failed
```

---

## Task 14: README update + end-to-end smoke

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the status line in `README.md`**

Open `README.md`. Replace the status block:

```markdown
> **Status:** Pre-alpha. Phase 1 (skeleton) only — `eden run`, sandbox providers, agents, and templates are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

with:

```markdown
> **Status:** Pre-alpha. Phases 1–2 complete: package skeleton, provider Protocols, worktree manager, `no_sandbox` and `docker` MVP providers, `create_sandbox()` factory. `eden run`, agents, templates, and the interactive scaffolder are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.
```

- [ ] **Step 2: Smoke-test the public surface from a fresh Python session**

```bash
python -c "
from eden.providers import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    Mount,
    SandboxHandle,
    SandboxProvider,
    make_bind_mount_provider,
)
from eden.worktree import create_worktree, WorktreeHandle, CloseResult
from eden.sandboxes import create_sandbox, Sandbox
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider
from eden.sandboxes.docker import provider as docker_provider
print('all imports OK')
"
```

Expected: prints `all imports OK`.

- [ ] **Step 3: Run the full gate suite once more**

```bash
python -m pytest tests/unit -v
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all pass.

- [ ] **Step 4: Commit and push**

```bash
git add README.md
git commit -m "docs: bump README status to Phase 2 complete"
git push
```

- [ ] **Step 5: Verify CI is green**

```bash
gh run watch
```

Expected: all 9 matrix jobs pass; the 3 Linux jobs run integration tests in addition to unit.

---

## Self-review

Run through this checklist before declaring the plan done.

**1. Spec coverage:**

| Spec section | Implemented in |
|---|---|
| §1 Public surface (`eden.providers`) | Tasks 2-5 |
| §1 Public surface (`eden.worktree`) | Tasks 7, 8 |
| §1 Public surface (`eden.sandboxes`) | Tasks 10, 11, 12 |
| §1 Errors module | Task 1 |
| §2.1 BranchStrategy | Task 2 |
| §2.2 SandboxProvider Protocol | Task 3 |
| §2.3 CreateOptions | Task 2 |
| §2.4 SandboxHandle + BindMountSandboxHandle | Task 3 |
| §2.5 ExecResult | Task 2 |
| §2.6 make_bind_mount_provider | Task 4 |
| §2.7 Mount | Task 2 |
| §3.1 create_worktree | Tasks 7, 8 |
| §3.2 WorktreeHandle + close behavior | Task 7 (close path tested in Task 8) |
| §3.3 Lock implementation | Task 6 |
| §4.1 no_sandbox | Task 10 |
| §4.2 docker provider | Task 11 |
| §4.3 create_sandbox | Task 12 |
| §5 Error handling — all 11 classes | Task 1 |
| §6.1 Test layout (unit + integration) | All tasks; integration in 13 |
| §6.2 Unit test marker on all 9 CI jobs | Task 13 (CI yaml) |
| §6.3 Integration skip on non-Linux + eden_test_image fixture | Task 13 |
| §6.4 Coverage targets | Achieved by test density across tasks |
| §6.5 CI matrix unchanged | Task 13 (workflow modification preserves matrix) |
| §6.6 Determinism (fake PID 2**31-1) | Task 6 stale-lock test |
| §7 Build-task ordering | This plan's tasks 1→14 follow the 11-step ordering |

No gaps.

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later" / "add appropriate error handling" / "similar to Task N" anywhere. Each step gives concrete code or commands.

**3. Type consistency:**

| Symbol | Defined | Used elsewhere |
|---|---|---|
| `EdenError` | Task 1 (`eden/errors.py`) | Task 1 worktree+sandboxes errors |
| `WorktreeLocked` | Task 1 | Tasks 6, 7 |
| `DirtyHostBlocked` | Task 1 | Task 7 |
| `BranchExists` | Task 1 | Task 8 |
| `GitCommandFailed` | Task 1 | Task 7 |
| `ProviderUnavailable` | Task 1 | Task 11 |
| `ImageNotFound` | Task 1 | Task 11 |
| `ContainerStartFailed` | Task 1 | Task 11 |
| `ExecFailed` | Task 1 | Task 2 (via lazy import in `ExecResult.check`) |
| `ExecTimeout` | Task 1 | Task 9 (`stream_exec`) |
| `UnsupportedStrategy` | Task 1 | Task 12 |
| `BranchStrategy.head/merge_to_head/named` | Task 2 | Tasks 7, 8, 12 |
| `Mount` | Task 2 | Tasks 11, 12 |
| `ExecResult` | Task 2 | Tasks 3, 9, 10, 11 |
| `CreateOptions` | Task 2 | Tasks 3, 4, 10, 11, 12 |
| `SandboxHandle.{exec,copy_file_in,copy_file_out,close}` | Task 3 | Tasks 10, 11, 12 |
| `make_bind_mount_provider` | Task 4 | Tasks 10, 11 |
| `acquire_lock` / `_LockHandle` | Task 6 | Task 7 |
| `_run_git`, `status_porcelain`, `branch_exists`, `worktree_add`, `worktree_remove` | Task 7 | Task 7 |
| `create_worktree` / `WorktreeHandle` / `CloseResult` | Task 7 | Tasks 8, 12 |
| `stream_exec` | Task 9 | Tasks 10, 11 |
| `provider` (no_sandbox) | Task 10 | Task 12 (used through stub) |
| `provider` (docker) | Task 11 | Task 13 (integration) |
| `Sandbox` / `create_sandbox` | Task 12 | Task 14 (smoke import) |

All names consistent across tasks.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-01-eden-phase2-sandbox-foundations.md`.

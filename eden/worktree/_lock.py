"""Cross-platform advisory file lock with stale-PID recovery."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from eden.worktree.errors import WorktreeLocked

if sys.platform == "win32":  # pragma: no cover - branch covered on Windows runners
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
            if sys.platform == "win32":  # pragma: no cover
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
        if sys.platform == "win32":  # pragma: no cover
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

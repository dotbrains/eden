""":class:`SessionStorage` implementation for the codex CLI.

Codex stores per-session JSONL transcripts under a date-nested directory
tree at ``~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-<...>-<session_id>.jsonl``.
The exact rollout filename prefix is undocumented and may change; the
locator below scans the entire sessions tree for a file whose name ends
with ``-<session_id>.jsonl`` (mirrors the upstream walker).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.providers._protocols import SandboxHandle
from eden.providers._types import Mount
from eden.session._store import write_session_copy

_SANDBOX_SESSIONS_DIR = Path("/home/agent/.codex/sessions")


def _is_codex_session_filename(name: str, session_id: str) -> bool:
    """Match codex's ``rollout-<timestamp>-<session_id>.jsonl`` shape."""
    return name.startswith("rollout-") and name.endswith(f"-{session_id}.jsonl")


def find_codex_session_path(root: Path, session_id: str) -> Path | None:
    """Walk ``root`` (typically ``~/.codex/sessions``) for a file whose name
    matches the codex rollout filename convention for ``session_id``.

    Returns the first match (depth-first), or ``None`` if no file matches.
    Errors reading individual directories are skipped so a permission-denied
    subtree doesn't abort the search.
    """
    if not root.exists():
        return None
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_file() and _is_codex_session_filename(entry.name, session_id):
                    return entry
                if entry.is_dir():
                    stack.append(entry)
            except OSError:
                continue
    return None


@dataclass(frozen=True)
class CodexSessionStorage:
    """Capture codex's per-iteration transcript JSONL.

    Mounts ``~/.codex/sessions`` into the container so codex's writes land
    somewhere the host can read. After each iteration, locates the JSONL
    via the dated-directory walker and copies it to
    ``<repo>/.eden/sessions/<branch>/iter-<i>-<session_id>.jsonl`` with
    sandbox-cwd → host-cwd path rewriting.

    Resume is a no-op on the host side because codex reads sessions directly
    from the mounted host directory (same model as claude_code).
    """

    home: Path | None = None
    """Override ``~`` for tests (resolves ``~/.codex/sessions``)."""

    def _sessions_dir(self) -> Path:
        return (self.home if self.home is not None else Path.home()) / ".codex" / "sessions"

    def extra_mounts(self) -> tuple[Mount, ...]:
        host_dir = self._sessions_dir()
        if not host_dir.exists():
            # codex creates the directory on first run; eden cannot mount a
            # non-existent host path. On a fresh machine the first iteration
            # writes into the container's own filesystem and capture will
            # simply fail soft (returns None).
            return ()
        return (Mount(host=host_dir, sandbox=_SANDBOX_SESSIONS_DIR),)

    def host_capture(
        self,
        *,
        handle: SandboxHandle,
        session_id: str,
        host_repo_path: Path,
        branch: str,
        iteration: int,
    ) -> Path | None:
        from eden.session._branch import sanitize_branch

        src = find_codex_session_path(self._sessions_dir(), session_id)
        if src is None:
            return None
        safe_branch = sanitize_branch(branch)
        dest = (
            host_repo_path
            / ".eden"
            / "sessions"
            / safe_branch
            / f"iter-{iteration}-{session_id}.jsonl"
        )
        # Mirror the legacy effective-cwd heuristic from claude_code: when
        # the worktree lives inside ``host_repo_path`` (no_sandbox / native),
        # rewrite from host_repo_path; otherwise (containerized) rewrite from
        # the handle's sandbox-side worktree path.
        wt = handle.worktree_path
        if host_repo_path in wt.parents or wt == host_repo_path:
            effective_cwd = host_repo_path
        else:
            effective_cwd = wt
        try:
            write_session_copy(
                src=src,
                dest=dest,
                sandbox_prefix=effective_cwd.as_posix(),
                host_prefix=str(host_repo_path),
            )
        except OSError as exc:
            raise SessionCaptureFailed(
                message=f"failed to write codex session copy to {dest}: {exc}",
                cause=exc,
            ) from exc
        return dest

    def sandbox_transfer(
        self,
        *,
        handle: SandboxHandle,
        host_session_file: Path,
        session_id: str,
    ) -> None:
        # codex reads sessions from the mounted ``~/.codex/sessions`` host
        # directory, so resume needs no in-container push — same model as
        # claude_code.
        return None

    def locate_session_on_host(
        self,
        *,
        session_id: str,
        sandbox_cwd: Path,
    ) -> Path | None:
        """Walk the date-nested sessions tree for a ``rollout-*-<id>.jsonl``.

        ``sandbox_cwd`` is unused — codex's layout doesn't encode cwd in
        the JSONL path.
        """
        return find_codex_session_path(self._sessions_dir(), session_id)


__all__ = ["CodexSessionStorage", "find_codex_session_path"]

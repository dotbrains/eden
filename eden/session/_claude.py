"""Default ``SessionStorage`` implementation for Claude Code."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eden.providers._protocols import SandboxHandle
from eden.providers._types import Mount
from eden.session import capture_session, capture_sidechain_sessions


def _find_session_in_projects_dir(projects_dir: Path, session_id: str) -> Path | None:
    if not projects_dir.is_dir():
        return None
    try:
        entries = sorted(projects_dir.iterdir())
    except OSError:
        return None
    for entry in entries:
        try:
            candidate = entry / f"{session_id}.jsonl"
            if entry.is_dir() and candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


@dataclass(frozen=True)
class ClaudeSessionStorage:
    """Capture Claude Code's per-iteration transcript JSONL.

    Mounts ``~/.claude/projects`` into the container so the agent's
    writes land somewhere the host can read, then ``host_capture``
    locates the JSONL by Claude's project-slug convention and rewrites
    paths from the sandbox CWD to the host CWD.

    Equivalent to the pre-ADR-0012 orchestrator behaviour when
    ``capture_sessions=True`` — extracted into a struct so codex / pi /
    opencode can each ship their own variant without forking
    ``_run_loop``.
    """

    home: Path | None = None
    """Override ``~`` for tests (resolves ``~/.claude/projects``)."""

    def _projects_dir(self) -> Path:
        return (self.home if self.home is not None else Path.home()) / ".claude" / "projects"

    def extra_mounts(self) -> tuple[Mount, ...]:
        host_dir = self._projects_dir()
        if not host_dir.exists():
            # Claude Code creates the directory on first use; eden can
            # not mount a non-existent host path, so on a fresh machine
            # the first iteration will write into the container's own
            # filesystem and capture will simply fail soft.
            return ()
        return (Mount(host=host_dir, sandbox=Path("/root/.claude/projects")),)

    def host_capture(
        self,
        *,
        handle: SandboxHandle,
        session_id: str,
        host_repo_path: Path,
        branch: str,
        iteration: int,
        since: float | None = None,
    ) -> Path | None:
        # Mirror the legacy effective-cwd heuristic: when the worktree
        # path lives inside ``host_repo_path`` (no_sandbox / native),
        # use the host repo path. Otherwise (containerized), use the
        # handle's own sandbox-side worktree path.
        wt = handle.worktree_path
        if host_repo_path in wt.parents or wt == host_repo_path:
            effective_cwd = host_repo_path
        else:
            effective_cwd = wt
        main = capture_session(
            session_id=session_id,
            sandbox_cwd=effective_cwd,
            host_repo_path=host_repo_path,
            branch=branch,
            iteration=iteration,
            home=self.home,
        )
        # Also curate any subagent/workflow transcripts that Claude wrote as
        # separate session files this run. Best-effort by contract — it never
        # raises — so the main capture's success is what we return.
        capture_sidechain_sessions(
            main_session_id=session_id,
            sandbox_cwd=effective_cwd,
            host_repo_path=host_repo_path,
            branch=branch,
            iteration=iteration,
            since=since,
            home=self.home,
        )
        return main

    def sandbox_transfer(
        self,
        *,
        handle: SandboxHandle,
        host_session_file: Path,
        session_id: str,
    ) -> None:
        # Claude Code reads sessions directly from the mounted
        # ``~/.claude/projects`` host directory, so transfer is a no-op.
        return None

    def locate_session_on_host(
        self,
        *,
        session_id: str,
        sandbox_cwd: Path,
    ) -> Path | None:
        """Locate ``<projects_dir>/<slug>/<session_id>.jsonl`` if it exists.

        Claude derives the project-slug from the cwd it was running in when
        the session was captured. The caller must pass the same
        ``sandbox_cwd`` the agent will see at resume time (typically the
        host repo path for ``no_sandbox`` or ``/workspace`` for a
        containerized run).
        """
        from eden.session._slug import claude_projects_slug

        slug = claude_projects_slug(sandbox_cwd)
        path = self._projects_dir() / slug / f"{session_id}.jsonl"
        if path.is_file():
            return path
        return _find_session_in_projects_dir(self._projects_dir(), session_id)


__all__ = ["ClaudeSessionStorage"]

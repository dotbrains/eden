""":class:`SessionStorage` implementation for the pi CLI.

Pi stores per-session JSONL transcripts under
``~/.pi/agent/sessions/--<encoded-cwd>--/<timestamp>_<session_id>.jsonl``.
The first JSONL line is a ``{"type":"session","id":"<id>","cwd":"<cwd>"...}``
header; subsequent entries (``message_update``, ``tool_execution_start``,
…) don't repeat the cwd.

The encoded-cwd directory matters for resume: pi resolves
``--session <id>`` against the *current project's* encoded directory
first; a captured file in any other encoded dir hits pi's interactive
"fork session?" prompt, which hangs in print/json mode. So when
transferring a session into the sandbox for resume we land it under the
sandbox-cwd-encoded dir, not the host-cwd-encoded dir.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.providers._protocols import SandboxHandle
from eden.providers._types import Mount
from eden.session._pi_paths import (
    encode_pi_session_dir,
    find_pi_session_path,
    read_session_cwd,
    transfer_pi_session,
)

_SANDBOX_SESSIONS_DIR = Path("/home/agent/.pi/agent/sessions")


@dataclass(frozen=True)
class PiSessionStorage:
    """Capture pi's per-iteration transcript JSONL.

    Mounts ``~/.pi/agent/sessions`` into the container at
    ``/home/agent/.pi/agent/sessions``. After each iteration, locates the
    JSONL via :func:`find_pi_session_path`, rewrites the session header's
    ``cwd`` from sandbox → host, and copies the result to
    ``<repo>/.eden/sessions/<branch>/iter-<i>-<session_id>.jsonl``.

    Resume: the captured file is re-rewritten back to the sandbox cwd
    and placed inside the sandbox's ``--<encoded-sandbox-cwd>--/`` dir
    so pi's project-first resolver doesn't trigger the "fork session?"
    prompt.
    """

    home: Path | None = None
    """Override ``~`` for tests (resolves ``~/.pi/agent/sessions``)."""

    def _sessions_dir(self) -> Path:
        return (self.home if self.home is not None else Path.home()) / ".pi" / "agent" / "sessions"

    def extra_mounts(self) -> tuple[Mount, ...]:
        host_dir = self._sessions_dir()
        if not host_dir.exists():
            # pi creates the directory on first run; eden cannot mount a
            # non-existent host path. On a fresh machine the first
            # iteration writes inside the container and capture fails
            # soft.
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
        since: float | None = None,
    ) -> Path | None:
        # ``since`` is unused: pi has no separate-file subagent transcripts to
        # scope. Accepted to satisfy the SessionStorage protocol.
        from eden.session._branch import sanitize_branch

        src = find_pi_session_path(self._sessions_dir(), session_id)
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
        # Mirror the effective-cwd heuristic from claude / codex: when the
        # worktree lives inside ``host_repo_path`` (no_sandbox / native),
        # rewrite from host_repo_path; otherwise (containerized) rewrite
        # from the handle's sandbox-side worktree path.
        wt = handle.worktree_path
        if host_repo_path in wt.parents or wt == host_repo_path:
            effective_cwd = host_repo_path
        else:
            effective_cwd = wt
        try:
            jsonl = src.read_text(encoding="utf-8")
            rewritten = transfer_pi_session(jsonl, effective_cwd, host_repo_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rewritten, encoding="utf-8")
        except OSError as exc:
            raise SessionCaptureFailed(
                message=f"failed to write pi session copy to {dest}: {exc}",
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
        """Push a captured JSONL back into the sandbox under the encoded dir."""
        jsonl = host_session_file.read_text(encoding="utf-8")
        sandbox_cwd = handle.worktree_path
        header_cwd = read_session_cwd(jsonl)
        from_cwd = Path(header_cwd) if header_cwd is not None else host_session_file.parent
        rewritten = transfer_pi_session(jsonl, from_cwd, sandbox_cwd)
        enc = encode_pi_session_dir(sandbox_cwd)
        target = _SANDBOX_SESSIONS_DIR / enc / host_session_file.name
        with tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(rewritten)
            tmp_path = Path(tmp.name)
        try:
            handle.copy_file_in(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)

    def locate_session_on_host(
        self,
        *,
        session_id: str,
        sandbox_cwd: Path,
    ) -> Path | None:
        """Walk ``~/.pi/agent/sessions`` for a ``*_<session_id>.jsonl``.

        ``sandbox_cwd`` is unused — pi's id is globally unique within the
        sessions tree, and the precheck only cares that some matching
        file exists.
        """
        return find_pi_session_path(self._sessions_dir(), session_id)


__all__ = [
    "PiSessionStorage",
    "encode_pi_session_dir",
    "find_pi_session_path",
    "transfer_pi_session",
]

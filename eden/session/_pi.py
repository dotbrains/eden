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

Mirrors upstream's pi-resume support (v0.6.6, 932aa70).
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.providers._protocols import SandboxHandle
from eden.providers._types import Mount

_SANDBOX_SESSIONS_DIR = Path("/home/agent/.pi/agent/sessions")
_NON_ALNUM_RE = re.compile(r"[/\\:]")


def encode_pi_session_dir(cwd: Path) -> str:
    """Return pi's ``--<enc>--`` directory name for a given cwd.

    Strips the leading separator, replaces ``/``, ``\\``, and ``:`` with
    ``-``, then wraps in ``--``. Mirrors upstream's
    ``encodePiSessionDir``.
    """
    s = str(cwd)
    s = s.lstrip("/\\")
    s = _NON_ALNUM_RE.sub("-", s)
    return f"--{s}--"


def _is_pi_session_filename(name: str, session_id: str) -> bool:
    """Match pi's ``<...>_<session_id>.jsonl`` convention."""
    return name.endswith(f"_{session_id}.jsonl")


def find_pi_session_path(root: Path, session_id: str) -> Path | None:
    """Walk ``root`` (typically ``~/.pi/agent/sessions``) for a session JSONL.

    Returns the first match. Walks one level deep because pi groups
    sessions by encoded-cwd directory; deeper layouts are not supported
    by the upstream CLI today. OSError on individual subdirs is swallowed
    so a permission-denied subtree doesn't abort the search.
    """
    if not root.exists():
        return None
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
            for f in entry.iterdir():
                if f.is_file() and _is_pi_session_filename(f.name, session_id):
                    return f
        except OSError:
            continue
    return None


def transfer_pi_session(jsonl: str, from_cwd: Path, to_cwd: Path) -> str:
    """Rewrite the session header's ``cwd`` field from ``from_cwd`` to ``to_cwd``.

    Only the ``{"type":"session"}`` header line is touched; every other
    JSONL line passes through verbatim, including malformed JSON
    (preserved so a captured stream stays byte-faithful outside the one
    field we own).

    Paths are compared and emitted in POSIX form (``as_posix()``)
    because pi writes its JSONL inside a Linux container — ``str(Path)``
    on a Windows host would produce backslashes that wouldn't match the
    forward slashes already in the file.
    """
    if jsonl == "":
        return ""
    from_s = from_cwd.as_posix()
    to_s = to_cwd.as_posix()
    out: list[str] = []
    for line in jsonl.split("\n"):
        if line == "":
            out.append(line)
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if (
            isinstance(entry, dict)
            and entry.get("type") == "session"
            and entry.get("cwd") == from_s
        ):
            entry["cwd"] = to_s
            out.append(json.dumps(entry, ensure_ascii=False))
        else:
            out.append(line)
    return "\n".join(out)


def _read_session_cwd(jsonl: str) -> str | None:
    """Return the ``cwd`` value from the session header, or ``None``."""
    for line in jsonl.split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("type") == "session":
            cwd = entry.get("cwd")
            return cwd if isinstance(cwd, str) else None
    return None


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
    ) -> Path | None:
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
        header_cwd = _read_session_cwd(jsonl)
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

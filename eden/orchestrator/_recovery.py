"""Recovery-message formatters surfaced when a run hits an unrecoverable state.

When ``_run_loop`` is about to raise ``AgentError`` it emits the formatted
recovery message as a ``StreamEvent`` first, so the user sees actionable
guidance in the run log even if their caller catches the exception silently.
The format is copy-pastable shell commands, mirroring upstream's
``buildRecoveryMessage`` style.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from eden.errors import AgentError


def format_agent_error_recovery(
    *,
    error: AgentError,
    branch: str,
    worktree_path: Path,
    log_path: Path | None,
) -> str:
    """Return a multi-line recovery message for an ``AgentError`` failure.

    Includes:

    - the parsed error body (so it survives even if the exception's ``str()``
      is dropped by the caller),
    - the worktree path so the user can ``cd`` and inspect partial work,
    - the log file (``None`` when logging was disabled),
    - branch name for ``git diff`` / ``git checkout`` follow-up,
    - copy-pastable next-step commands. ``shlex.quote`` wraps every
      interpolated value so paths with spaces (a real case under macOS's
      "User Name" home dirs) don't break the paste.
    """
    body = error.parsed_error or error.stderr.strip() or "(no agent output captured)"
    wt_q = shlex.quote(str(worktree_path))
    branch_q = shlex.quote(branch)
    lines: list[str] = [
        "[eden] agent run failed — recovery info:",
        f"  agent:    {error.agent_name}",
        f"  exit:    {error.exit_code}",
        f"  error:    {body}",
        f"  branch:   {branch}",
        f"  worktree: {worktree_path}",
    ]
    if log_path is not None:
        lines.append(f"  log:      {log_path}")
    lines.append("")
    lines.append("Next steps:")
    lines.append(f"  cd {wt_q}")
    lines.append("  git status")
    if log_path is not None:
        lines.append(f"  less {shlex.quote(str(log_path))}")
    lines.append(f"  git diff {branch_q}    # review any uncommitted work the agent left")
    lines.append("  eden clean            # remove the worktree once you're done")
    return "\n".join(lines)


__all__ = ["format_agent_error_recovery"]

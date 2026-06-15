"""Assemble RunResult from orchestrator state."""

from __future__ import annotations

from pathlib import Path

from eden._types import Commit, Iteration, RunResult, Usage, _RunContext


def assemble(
    *,
    iterations: list[Iteration],
    completion_signal: str | None,
    branch: str,
    stdout: str,
    worktree_path: Path,
    preserved_worktree_path: Path | None,
    cwd: Path,
    prompt: str,
    env: dict[str, str],
    log_file_path: Path | None,
    session_id: str | None,
    session_file_path: Path | None,
    usage: Usage | None,
    commits: list[Commit] | None = None,
    output: object | None = None,
    ctx: _RunContext | None = None,
) -> RunResult:
    return RunResult(
        iterations=iterations,
        completion_signal=completion_signal,
        branch=branch,
        stdout=stdout,
        commits=commits if commits is not None else [],
        worktree_path=worktree_path,
        preserved_worktree_path=preserved_worktree_path,
        merged_to_target_branch=None,
        cwd=cwd,
        prompt=prompt,
        env=env,
        log_file_path=log_file_path,
        session_id=session_id,
        session_file_path=session_file_path,
        usage=usage,
        output=output,
        _ctx=ctx,
    )

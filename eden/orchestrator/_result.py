"""Assemble RunResult from orchestrator state."""

from __future__ import annotations

from pathlib import Path

from eden._types import Commit, Iteration, RunResult, Usage, _RunContext
from eden.agents._protocol import Agent
from eden.output import OutputDefinition, extract_structured_output
from eden.providers._protocols import SandboxProvider


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


def assemble_loop_result(
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
    commits: list[Commit],
    output: OutputDefinition | None,
    agent: Agent,
    sandbox: SandboxProvider,
) -> RunResult:
    last = iterations[-1] if iterations else None
    extracted: object | None = None
    if output is not None:
        extracted = extract_structured_output(
            stdout,
            output,
            branch=branch,
            preserved_worktree_path=preserved_worktree_path,
            session_id=last.session_id if last else None,
            session_file_path=last.session_file_path if last else None,
        )

    return assemble(
        iterations=iterations,
        completion_signal=completion_signal,
        branch=branch,
        stdout=stdout,
        worktree_path=worktree_path,
        preserved_worktree_path=preserved_worktree_path,
        cwd=cwd,
        prompt=prompt,
        env=env,
        log_file_path=log_file_path,
        session_id=last.session_id if last else None,
        session_file_path=last.session_file_path if last else None,
        usage=last.usage if last else None,
        commits=commits,
        output=extracted,
        ctx=_RunContext(agent=agent, sandbox=sandbox, cwd=cwd),
    )

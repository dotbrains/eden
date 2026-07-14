"""Run loop result assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eden._types import Commit, Iteration, RunResult
from eden.agents._protocol import Agent
from eden.orchestrator._result import assemble_loop_result
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxProvider
from eden.streaming._bounded_tail import BoundedTail


@dataclass(frozen=True)
class LoopIterationResult:
    iteration: Iteration
    completion: str | None
    rendered_prompt: str


def build_loop_result(
    *,
    iterations: list[Iteration],
    completion_hit: str | None,
    branch: str,
    stdout_chunks: BoundedTail,
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
    return assemble_loop_result(
        iterations=iterations,
        completion_signal=completion_hit,
        branch=branch,
        stdout=stdout_chunks.to_string(),
        worktree_path=worktree_path,
        preserved_worktree_path=preserved_worktree_path,
        cwd=cwd,
        prompt=prompt,
        env=env,
        log_file_path=log_file_path,
        commits=commits,
        output=output,
        agent=agent,
        sandbox=sandbox,
    )


__all__ = ["LoopIterationResult", "build_loop_result"]

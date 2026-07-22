from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eden._types import Timeouts
from eden.abort import AbortSignal
from eden.agents._protocol import Agent
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.orchestrator.interactive._interactive_cleanup import close_interactive_resources
from eden.orchestrator.interactive._interactive_exec import (
    build_interactive_argv,
    run_interactive_exec,
)
from eden.orchestrator.interactive._interactive_prompt import render_interactive_prompt
from eden.orchestrator.interactive._interactive_resources import prepare_interactive_resources
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes._git_setup import configure_sandbox_git
from eden.worktree._create import WorktreeHandle


@dataclass(frozen=True)
class InteractiveResult:
    """Result returned by :func:`eden.interactive`.

    ``exit_code`` is the agent process's exit status. ``branch`` is the
    worktree branch the session ran on (may equal ``"HEAD"`` for the head
    strategy). ``worktree_path`` is the host path that was the agent's CWD.
    """

    branch: str
    exit_code: int
    worktree_path: Path
    cwd: Path


def interactive(
    *,
    agent: Agent,
    sandbox: SandboxProvider | None = None,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, object] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
    collect_args: bool | None = None,
    signal: AbortSignal | None = None,
    timeouts: Timeouts | None = None,
    _existing_worktree: WorktreeHandle | None = None,
) -> InteractiveResult:
    """Run an agent attached to the parent TTY.

    Unlike :func:`eden.run`, the agent inherits stdin / stdout / stderr and
    returns when the agent process exits.

    ``sandbox`` defaults to ``no_sandbox()``.

    Optional prompt inputs render like ``run()`` (``{{SOURCE_BRANCH}}``,
    ``{{TARGET_BRANCH}}``, shell expansion, custom args) and pass
    the resulting text to the agent's interactive argv builder. Agents that
    define a ``build_interactive_command(ctx)`` method use it; others fall
    back to ``build_command(ctx)``.

    ``collect_args`` controls interactive collection of missing ``{{KEY}}``
    placeholders. By default, eden collects them only when ``stdin`` is a TTY.
    """
    resources = prepare_interactive_resources(
        sandbox=sandbox,
        signal=signal,
        existing_worktree=_existing_worktree,
        cwd=cwd,
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        env=env,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        copy_to_worktree=copy_to_worktree,
        name=name,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        timeouts=timeouts,
    )
    wt = resources.worktree
    handle = None
    hooks_or_default = hooks if hooks is not None else Hooks()
    try:
        apply_copy_to_worktree(
            paths=copy_to_worktree,
            source_root=resources.cwd_path,
            worktree_path=wt.worktree_path,
            timeout=resources.timeouts.copy_to_worktree,
        )
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks_or_default.host,
            worktree_path=wt.worktree_path,
            env=resources.merged_env,
            timeouts=resources.timeouts,
        )
        handle = resources.sandbox.create(
            CreateOptions(
                branch=wt.branch,
                worktree_path=wt.worktree_path,
                host_repo_path=wt.host_repo_path,
                env=resources.merged_env,
                mounts=(),
                name_hint=name,
            )
        )
        if resources.sandbox.kind != "none":
            configure_sandbox_git(handle, wt.host_repo_path, timeout=resources.timeouts.git_setup)
        run_sandbox_hooks(
            phase=HookPhase.OnSandboxReady,
            hooks=hooks_or_default.sandbox,
            handle=handle,
            env=resources.merged_env,
            timeouts=resources.timeouts,
        )

        rendered = render_interactive_prompt(
            prompt_text=resources.prompt_text,
            prompt_is_literal=resources.prompt_is_literal,
            prompt_args=prompt_args,
            collect_args=collect_args,
            source_branch=wt.branch,
            target_branch=resources.target_branch,
            handle=handle,
        )
        argv = build_interactive_argv(
            agent=agent,
            rendered_prompt=rendered,
            handle=handle,
            worktree_path=wt.worktree_path,
            branch=wt.branch,
            name=name,
        )
        exit_code = run_interactive_exec(
            handle=handle,
            sandbox_name=resources.sandbox.name,
            argv=argv,
            env=resources.merged_env,
            signal=signal,
        )
        return InteractiveResult(
            branch=wt.branch,
            exit_code=exit_code,
            worktree_path=wt.worktree_path,
            cwd=resources.cwd_path,
        )
    finally:
        close_interactive_resources(
            handle=handle,
            worktree=wt,
            hooks=hooks_or_default,
            env=resources.merged_env,
            timeouts=resources.timeouts,
            close_worktree=_existing_worktree is None,
        )

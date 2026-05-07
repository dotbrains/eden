"""``eden.interactive()`` — launch an agent attached to the parent TTY."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.env import merge_env
from eden.errors import InvalidOptions
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.orchestrator._setup import resolve_branch_strategy, resolve_target_branch
from eden.prompt import render_prompt
from eden.prompt._source import resolve_source
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions
from eden.worktree._create import create_worktree


@dataclass(frozen=True)
class InteractiveResult:
    """Returned by :func:`eden.interactive` after the agent exits.

    ``exit_code`` is the agent process's exit status. ``branch`` is the
    worktree branch the session ran on (may equal ``"HEAD"`` for the head
    strategy). ``worktree_path`` is the host path that was the agent's CWD;
    callers can stage / commit from there.
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
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
) -> InteractiveResult:
    """Run an agent attached to the parent TTY for an interactive session.

    Unlike :func:`eden.run`, the agent inherits the caller's stdin / stdout /
    stderr — the user types directly into the agent's TUI. There is no
    iteration loop, no idle watchdog, no stream parsing, no completion-signal
    matching. The function returns when the agent process exits.

    ``sandbox`` defaults to ``no_sandbox()``. Other providers raise
    :class:`InvalidOptions` for now — TTY allocation in containerized
    sandboxes (``docker exec -t``) is a separate, deeper feature.

    ``prompt`` / ``prompt_file`` / ``prompt_args`` are optional. When supplied,
    eden renders the prompt the same way ``run()`` does (``{{SOURCE_BRANCH}}``,
    ``{{TARGET_BRANCH}}``, ``!`...``` shell expansion, custom args) and passes
    the resulting text to the agent's interactive argv builder. Agents that
    define a ``build_interactive_command(ctx)`` method use it; others fall
    back to ``build_command(ctx)``.
    """
    if sandbox is None:
        from eden.sandboxes.no_sandbox import provider as no_sandbox

        sandbox = no_sandbox()

    cwd_path = Path(cwd) if cwd is not None else Path.cwd()
    if not cwd_path.exists() or not cwd_path.is_dir():
        from eden.errors import CwdError

        raise CwdError(message=f"cwd does not exist or is not a directory: {cwd_path}")
    if not (cwd_path / ".git").exists():
        from eden.errors import CwdError

        raise CwdError(
            message=f"cwd is not a git repository: {cwd_path}",
            hint="run `git init` or pass a different cwd",
        )

    prompt_text = ""
    if prompt is not None or prompt_file is not None:
        prompt_text = resolve_source(
            prompt=prompt, prompt_file=prompt_file, prompt_args=prompt_args
        )

    merged_env = merge_env({}, env or {})

    # Interactive sessions default to ``head`` when the provider supports it
    # — interactive UX expects the agent's writes to land in the host repo
    # directly. ``resolve_branch_strategy`` defaults bind_mount providers to
    # ``merge_to_head`` (right for ``run()`` loops) which is the wrong default
    # here. Fall back to ``merge_to_head`` only when ``head`` is unsupported.
    if branch_strategy is not None:
        strategy = branch_strategy
    elif sandbox.supports_strategy(BranchStrategy.head()):
        strategy = BranchStrategy.head()
    else:
        strategy = resolve_branch_strategy(
            branch_strategy=None, sandbox_kind=sandbox.kind
        )
    if not sandbox.supports_strategy(strategy):
        from eden.sandboxes.errors import UnsupportedStrategy

        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

    target_branch = resolve_target_branch(host_repo_path=cwd_path)

    wt = create_worktree(host_repo_path=cwd_path, strategy=strategy, name_hint=name)
    handle = None
    hooks_or_default = hooks if hooks is not None else Hooks()
    from eden._types import Timeouts

    timeouts = Timeouts()
    try:
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks_or_default.host,
            worktree_path=wt.worktree_path,
            env=merged_env,
            timeouts=timeouts,
        )
        handle = sandbox.create(
            CreateOptions(
                branch=wt.branch,
                worktree_path=wt.worktree_path,
                host_repo_path=wt.host_repo_path,
                env=merged_env,
                mounts=(),
                name_hint=name,
            )
        )
        run_sandbox_hooks(
            phase=HookPhase.OnSandboxReady,
            hooks=hooks_or_default.sandbox,
            handle=handle,
            env=merged_env,
            timeouts=timeouts,
        )

        rendered = (
            render_prompt(
                text=prompt_text,
                args=prompt_args or {},
                source_branch=wt.branch,
                target_branch=target_branch,
                handle=handle,
            )
            if prompt_text
            else ""
        )
        ctx = IterationContext(
            iteration=0,
            prompt=rendered,
            sandbox_handle=handle,
            worktree_path=wt.worktree_path,
            branch=wt.branch,
            name=name,
        )
        build_interactive = getattr(agent, "build_interactive_command", None)
        argv = (
            build_interactive(ctx)
            if callable(build_interactive)
            else agent.build_command(ctx)
        )

        # Dispatch via the handle's ``interactive_exec`` method when available
        # — bind-mount providers (no_sandbox, docker, podman) implement it; the
        # docker / podman impls wrap argv in ``<binary> exec -it`` so the user
        # gets a real TTY inside the container. Isolated providers (Daytona,
        # Vercel, the local isolated copy) don't expose a TTY: raise a clear
        # InvalidOptions instead.
        ix = getattr(handle, "interactive_exec", None)
        if not callable(ix):
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    f"sandbox={sandbox.name!r} does not expose an interactive "
                    "TTY"
                ),
                hint=(
                    "use eden.run() for non-interactive runs against this "
                    "provider, or pick no_sandbox / docker / podman for "
                    "interactive sessions"
                ),
            )
        # The exec runs inside the sandbox, so cwd is the in-container
        # worktree path (``handle.worktree_path``), not the host path.
        exit_code = ix(argv, cwd=handle.worktree_path, env=merged_env)
        return InteractiveResult(
            branch=wt.branch,
            exit_code=exit_code,
            worktree_path=wt.worktree_path,
            cwd=cwd_path,
        )
    finally:
        if handle is not None:
            try:
                run_sandbox_hooks(
                    phase=HookPhase.OnClose,
                    hooks=hooks_or_default.sandbox,
                    handle=handle,
                    env=merged_env,
                    timeouts=timeouts,
                )
            except Exception:
                pass
        try:
            run_host_hooks(
                phase=HookPhase.OnClose,
                hooks=hooks_or_default.host,
                worktree_path=wt.worktree_path,
                env=merged_env,
                timeouts=timeouts,
            )
        except Exception:
            pass
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        wt.close()


__all__ = ["InteractiveResult", "interactive"]

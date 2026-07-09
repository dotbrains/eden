"""``eden.interactive()`` — launch an agent attached to the parent TTY."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eden._types import Timeouts
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._flox import flox_wrap
from eden.agents._protocol import Agent
from eden.env import load_eden_env, merge_env
from eden.errors import InvalidOptions
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.orchestrator._setup import resolve_branch_strategy, resolve_target_branch
from eden.prompt import render_prompt
from eden.prompt._collect import collect_missing_args
from eden.prompt._source import resolve_source
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions
from eden.worktree._create import WorktreeHandle, create_worktree


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

    ``collect_args`` controls interactive collection of missing
    ``{{KEY}}`` placeholders. When ``None`` (default), eden collects them
    only when ``stdin`` is a TTY — CI runs hit the normal
    :class:`eden.errors.PromptError`. Pass ``True`` / ``False`` to force.
    """
    import sys

    if signal is not None:
        signal.raise_if_aborted()

    if sandbox is None:
        from eden.sandboxes.no_sandbox import provider as no_sandbox

        sandbox = no_sandbox()

    if _existing_worktree is not None:
        if branch_strategy is not None or base_branch is not None:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "branch_strategy/base_branch are incompatible with an existing worktree; "
                    "the branch was fixed when the worktree was carved"
                ),
            )
        if copy_to_worktree:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "copy_to_worktree= is incompatible with an existing worktree; "
                    "seed files when creating the worktree or sandbox"
                ),
            )

    cwd_path = (
        _existing_worktree.host_repo_path
        if _existing_worktree is not None
        else Path(cwd)
        if cwd is not None
        else Path.cwd()
    )
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
    prompt_is_literal = False
    if prompt is not None or prompt_file is not None:
        source = resolve_source(prompt=prompt, prompt_file=prompt_file, prompt_args=prompt_args)
        prompt_text = source.text
        prompt_is_literal = source.is_literal

    # .eden/.env values flow into the sandbox; explicit env= overrides them.
    caller_env = {**load_eden_env(cwd_path), **(dict(env) if env else {})}
    merged_env = merge_env({}, caller_env)

    # Interactive sessions default to ``head`` when the provider supports it
    # — interactive UX expects the agent's writes to land in the host repo
    # directly. ``resolve_branch_strategy`` defaults bind_mount providers to
    # ``merge_to_head`` (right for ``run()`` loops) which is the wrong default
    # here. Fall back to ``merge_to_head`` only when ``head`` is unsupported.
    if _existing_worktree is not None:
        strategy = BranchStrategy.named(_existing_worktree.branch)
    elif branch_strategy is not None and base_branch is not None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "base_branch is mutually exclusive with branch_strategy; the "
                "strategy's own `base` controls the fork point"
            ),
            hint=(
                "pass base via BranchStrategy.merge_to_head(base=...) or .named(branch, base=...)"
            ),
        )
    if branch_strategy is not None:
        strategy = branch_strategy
    elif sandbox.supports_strategy(BranchStrategy.head()):
        strategy = BranchStrategy.head()
    else:
        strategy = resolve_branch_strategy(
            branch_strategy=None,
            sandbox_kind=sandbox.kind,
            base_branch=base_branch,
        )
    if not sandbox.supports_strategy(strategy):
        from eden.sandboxes.errors import UnsupportedStrategy

        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

    if copy_to_worktree and strategy.tag == "head":
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "copy_to_worktree= is incompatible with branch_strategy 'head'; "
                "the worktree IS the host repo, so copying would overwrite it"
            ),
            hint=(
                "drop copy_to_worktree or pick a branch strategy that carves "
                "a separate worktree (merge_to_head or named)"
            ),
        )

    target_branch = resolve_target_branch(host_repo_path=cwd_path)

    timeouts_or_default = timeouts if timeouts is not None else Timeouts()
    wt = (
        _existing_worktree
        if _existing_worktree is not None
        else create_worktree(
            host_repo_path=cwd_path,
            strategy=strategy,
            name_hint=name,
            throw_on_duplicate_worktree=throw_on_duplicate_worktree,
            git_timeout=timeouts_or_default.git_setup,
        )
    )
    handle = None
    hooks_or_default = hooks if hooks is not None else Hooks()
    try:
        apply_copy_to_worktree(
            paths=copy_to_worktree,
            source_root=cwd_path,
            worktree_path=wt.worktree_path,
        )
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks_or_default.host,
            worktree_path=wt.worktree_path,
            env=merged_env,
            timeouts=timeouts_or_default,
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
            timeouts=timeouts_or_default,
        )

        if not prompt_text:
            rendered = ""
        elif prompt_is_literal:
            # Inline prompts are passed to the agent verbatim — no
            # substitution, no shell expansion, no built-in injection.
            rendered = prompt_text
        else:
            effective_args: Mapping[str, str] = prompt_args or {}
            should_collect = collect_args if collect_args is not None else sys.stdin.isatty()
            if should_collect:
                effective_args = collect_missing_args(prompt_text, effective_args)
            rendered = render_prompt(
                text=prompt_text,
                args=effective_args,
                source_branch=wt.branch,
                target_branch=target_branch,
                handle=handle,
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
        argv = build_interactive(ctx) if callable(build_interactive) else agent.build_command(ctx)
        # Per-agent Flox runtime (ADR-0014): wrap before the handle wraps argv
        # in ``<binary> exec -it``, so for container providers ``flox`` runs
        # inside the container (and so must be present in the image, alongside
        # the declared env dir). For no_sandbox the wrap runs on the host.
        argv = flox_wrap(argv, flox_env=getattr(agent, "flox_env", None))

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
                message=(f"sandbox={sandbox.name!r} does not expose an interactive TTY"),
                hint=(
                    "use eden.run() for non-interactive runs against this "
                    "provider, or pick no_sandbox / docker / podman for "
                    "interactive sessions"
                ),
            )
        # The exec runs inside the sandbox, so cwd is the in-container
        # worktree path (``handle.worktree_path``), not the host path.
        interactive_params: Mapping[str, inspect.Parameter]
        try:
            interactive_params = inspect.signature(ix).parameters
        except (TypeError, ValueError):
            interactive_params = {}
        if "signal" in interactive_params:
            exit_code = ix(argv, cwd=handle.worktree_path, env=merged_env, signal=signal)
        else:
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
                    timeouts=timeouts_or_default,
                )
            except Exception:
                pass
        try:
            run_host_hooks(
                phase=HookPhase.OnClose,
                hooks=hooks_or_default.host,
                worktree_path=wt.worktree_path,
                env=merged_env,
                timeouts=timeouts_or_default,
            )
        except Exception:
            pass
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        if _existing_worktree is None:
            wt.close()


__all__ = ["InteractiveResult", "interactive"]

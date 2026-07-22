"""Startup helpers for the orchestrator loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from eden._types import Timeouts
from eden.abort import AbortSignal
from eden.agents._flox import validate_flox_env
from eden.agents._protocol import Agent
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.logging._config import Logging
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._setup import SetupResult
from eden.orchestrator.loop._loop_resources import register_loop_emergency_cleanup
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, Mount
from eden.tracing import span
from eden.worktree._create import WorktreeHandle


@dataclass(frozen=True)
class LoopRuntime:
    handle: SandboxHandle
    unregister_shutdown: Callable[[], None] | None
    logger: LoopLogger
    log_path: Path | None
    flox_env_dir: Path | None


def start_loop_runtime(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    setup: SetupResult,
    worktree: WorktreeHandle,
    caller_managed: bool,
    existing_handle: SandboxHandle | None,
    copy_to_worktree: list[str] | None,
    hooks: Hooks,
    timeouts: Timeouts,
    extra_mounts: tuple[Mount, ...],
    name: str | None,
    target_branch: str,
    logging_cfg: Logging | None,
    signal: AbortSignal,
) -> LoopRuntime:
    if not caller_managed:
        # Seed user-supplied files into the worktree before
        # ``on_worktree_ready`` hooks fire; hooks may depend on them.
        apply_copy_to_worktree(
            paths=copy_to_worktree,
            source_root=setup.cwd,
            worktree_path=worktree.worktree_path,
            timeout=timeouts.copy_to_worktree,
        )
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks.host,
            worktree_path=worktree.worktree_path,
            env=setup.merged_env,
            timeouts=timeouts,
        )

    signal.raise_if_aborted()

    handle = existing_handle
    if not caller_managed:
        with span(
            "eden.sandbox.create",
            attributes={
                "sandbox.name": sandbox.name,
                "sandbox.kind": sandbox.kind,
                "branch": worktree.branch,
            },
        ):
            handle = sandbox.create(
                CreateOptions(
                    branch=worktree.branch,
                    worktree_path=worktree.worktree_path,
                    host_repo_path=worktree.host_repo_path,
                    env=setup.merged_env,
                    mounts=extra_mounts,
                    name_hint=name,
                )
            )
            run_sandbox_hooks(
                phase=HookPhase.OnSandboxReady,
                hooks=hooks.sandbox,
                handle=handle,
                env=setup.merged_env,
                timeouts=timeouts,
            )
    assert handle is not None

    unregister_shutdown: Callable[[], None] | None = None
    if not caller_managed:
        # SIGTERM doesn't run try/finally, so register emergency cleanup for
        # abrupt parent death. The normal cleanup path unregisters this first.
        unregister_shutdown = register_loop_emergency_cleanup(handle=handle, worktree=worktree)

    logger = LoopLogger.open(
        logging_cfg=logging_cfg,
        host_repo_path=setup.cwd,
        branch=worktree.branch,
        target_branch=target_branch,
        name=name,
        env_values=tuple(setup.merged_env.values()),
    )

    raw_flox_env = getattr(agent, "flox_env", None)
    flox_env_dir = validate_flox_env(raw_flox_env) if raw_flox_env is not None else None

    return LoopRuntime(
        handle=handle,
        unregister_shutdown=unregister_shutdown,
        logger=logger,
        log_path=logger.log_path,
        flox_env_dir=flox_env_dir,
    )

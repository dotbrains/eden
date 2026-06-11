"""create_sandbox top-level factory + Sandbox context-manager wrapper."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.abort._signal import AbortController
from eden.env import load_eden_env
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes.errors import UnsupportedStrategy
from eden.streaming import StreamEvent
from eden.worktree._create import WorktreeHandle, create_worktree

if TYPE_CHECKING:
    from eden.agents._protocol import Agent
    from eden.output import OutputDefinition


def _seconds(value: float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return _seconds(value)


@dataclass
class Sandbox:
    worktree: WorktreeHandle
    handle: SandboxHandle
    sandbox_provider: SandboxProvider
    cwd: Path | None = None
    owns_worktree: bool = True

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the sandbox handle, and the worktree if this sandbox owns it.

        When the sandbox was created over a caller-provided worktree
        (``create_sandbox(worktree=...)``), ownership is split: ``close()``
        tears down the container only and the caller's ``worktree.close()``
        decides the worktree's fate (preserved if dirty, removed if clean).

        If both teardown steps fail, the handle's exception propagates — the
        worktree close is still attempted, but its failure is reported and
        suppressed so it cannot replace the primary error.
        """
        try:
            self.handle.close()
        except BaseException:
            if self.owns_worktree:
                try:
                    self.worktree.close()
                except Exception as cleanup_exc:
                    print(f"eden: worktree close also failed: {cleanup_exc}")
            raise
        if self.owns_worktree:
            self.worktree.close()

    def run(
        self,
        *,
        agent: Agent,
        prompt: str | None = None,
        prompt_file: str | Path | None = None,
        prompt_args: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
        max_iterations: int = 1,
        completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
        idle_timeout: float | timedelta = 600.0,
        idle_warning_interval: float | timedelta | None = None,
        completion_timeout: float | timedelta | None = 60.0,
        name: str | None = None,
        hooks: Hooks | None = None,
        timeouts: Timeouts | None = None,
        on_event: Callable[[StreamEvent], None] | None = None,
        logging: Logging | None = None,
        signal: AbortSignal | None = None,
        output: OutputDefinition | None = None,
        resume_session: str | None = None,
    ) -> RunResult:
        """Run an agent against this existing sandbox + worktree.

        Mirrors the signature of :func:`eden.run` but reuses the worktree and
        handle the sandbox already holds — no new branch is carved, no new
        container is spawned. Use this to run multiple agents (e.g. an
        implementer followed by a reviewer) against the same branch.
        """
        # Lazy imports keep eden.sandboxes importable from agents/orchestrator
        # without cycles.
        from eden.errors import InvalidOptions
        from eden.orchestrator._loop import _run_loop
        from eden.orchestrator._setup import resolve_setup

        cwd_path = self.cwd if self.cwd is not None else self.worktree.host_repo_path
        provider_env: dict[str, str] = {}
        setup = resolve_setup(
            prompt=prompt,
            prompt_file=prompt_file,
            prompt_args=prompt_args,
            cwd=cwd_path,
            env=env,
            provider_env=provider_env,
            sandbox_kind=self.sandbox_provider.kind,
        )
        if resume_session is not None and max_iterations != 1:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "resume_session= is only valid with max_iterations=1; "
                    f"got max_iterations={max_iterations}"
                ),
            )
        if output is not None:
            if max_iterations != 1:
                raise InvalidOptions(
                    code="config.invalid_options",
                    message=(
                        "output= is only valid with max_iterations=1; got "
                        f"max_iterations={max_iterations}"
                    ),
                )
            tag_marker = f"<{output.tag}>"
            if tag_marker not in setup.prompt_text:
                raise InvalidOptions(
                    code="config.invalid_options",
                    message=(
                        f"output tag {tag_marker} not referenced in prompt; "
                        "the agent must be told which tag to emit"
                    ),
                )
        abort = signal if signal is not None else AbortController().signal
        return _run_loop(
            agent=agent,
            sandbox=self.sandbox_provider,
            setup=setup,
            branch_strategy=None,
            max_iterations=max_iterations,
            completion_signal=completion_signal,
            idle_timeout=_seconds(idle_timeout),
            idle_warning_interval=_maybe_seconds(idle_warning_interval),
            completion_timeout=_maybe_seconds(completion_timeout),
            name=name,
            hooks=hooks if hooks is not None else Hooks(),
            timeouts=timeouts if timeouts is not None else Timeouts(),
            on_event=on_event,
            logging_cfg=logging,
            signal=abort,
            prompt_args=prompt_args,
            output=output,
            resume_session=resume_session,
            existing_worktree=self.worktree,
            existing_handle=self.handle,
        )


def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    worktree: WorktreeHandle | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
    timeouts: Timeouts | None = None,
) -> Sandbox:
    """Resolve branch/strategy, carve a worktree, and create the sandbox handle.

    ``base_branch`` overrides the fork point of the default ``merge_to_head``
    strategy. It is mutually exclusive with ``branch_strategy``.

    ``worktree`` reuses a caller-managed :class:`WorktreeHandle` (from
    :func:`eden.create_worktree`) instead of carving a fresh one. Ownership is
    split: ``Sandbox.close()`` then tears down the container only, and the
    caller's ``worktree.close()`` decides the worktree's fate — so one
    worktree can host several sequential sandboxes (explore interactively,
    then run AFK; or run agents under different images on one branch).
    Mutually exclusive with ``branch``/``branch_strategy``/``base_branch``,
    whose job (picking the branch) was done when the worktree was carved.
    Mirrors sandcastle's ``wt.createSandbox(...)``.

    ``copy_to_worktree`` is a list of host-relative file/directory paths to
    copy from the host repo into the freshly-carved worktree before the
    sandbox boots. Incompatible with the ``head`` branch strategy.

    ``timeouts`` caps the carve's git plumbing via ``Timeouts.git_setup``
    (and is reused by ``close()`` for the teardown ``git worktree remove``).
    It governs this one-time carve only; per-run deadlines (``iteration_step``
    etc.) are passed to each subsequent ``sb.run(timeouts=...)``.
    """
    if branch is not None and branch_strategy is not None:
        raise ValueError("branch and branch_strategy are mutually exclusive")
    if branch_strategy is not None and base_branch is not None:
        raise ValueError(
            "base_branch is mutually exclusive with branch_strategy; "
            "set base via BranchStrategy.merge_to_head(base=...) or .named(branch, base=...)"
        )
    if worktree is not None and (
        branch is not None or branch_strategy is not None or base_branch is not None
    ):
        raise ValueError(
            "worktree is mutually exclusive with branch/branch_strategy/base_branch; "
            "the branch was fixed when the worktree was carved"
        )

    resolved_timeouts = timeouts if timeouts is not None else Timeouts()

    if worktree is not None:
        owns_worktree = False
        wt = worktree
        host_repo_path = wt.host_repo_path
        if copy_to_worktree and wt.worktree_path == wt.host_repo_path:
            from eden.errors import InvalidOptions

            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "copy_to_worktree= is incompatible with a head-style worktree; "
                    "the worktree IS the host repo, so copying would overwrite it"
                ),
                hint=(
                    "drop copy_to_worktree or carve the worktree with a strategy "
                    "that uses a separate directory (merge_to_head or named)"
                ),
            )
    else:
        owns_worktree = True
        base = base_branch or "main"
        if branch is not None:
            strategy = BranchStrategy.named(branch, base=base)
        elif branch_strategy is not None:
            strategy = branch_strategy
        elif sandbox.kind == "none":
            strategy = BranchStrategy.head()
        else:
            strategy = BranchStrategy.merge_to_head(base=base)

        if not sandbox.supports_strategy(strategy):
            raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

        if copy_to_worktree and strategy.tag == "head":
            from eden.errors import InvalidOptions

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

        host_repo_path = Path.cwd()
        wt = create_worktree(
            host_repo_path=host_repo_path,
            strategy=strategy,
            name_hint=name,
            throw_on_duplicate_worktree=throw_on_duplicate_worktree,
            git_timeout=resolved_timeouts.git_setup,
        )

    # .eden/.env values flow into the container at create time so entrypoints
    # and on_sandbox_ready hooks see them; explicit env= still wins. The file
    # is looked up under the repo ``create_worktree`` carved from (the host
    # process's CWD when this factory carves), not the agent's ``cwd=`` —
    # those have different meanings in this factory.
    combined_env = {**load_eden_env(host_repo_path), **(dict(env) if env else {})}

    try:
        apply_copy_to_worktree(
            paths=copy_to_worktree,
            source_root=host_repo_path,
            worktree_path=wt.worktree_path,
        )
        handle = sandbox.create(
            CreateOptions(
                branch=wt.branch,
                worktree_path=wt.worktree_path,
                host_repo_path=wt.host_repo_path,
                env=combined_env,
                mounts=mounts or (),
                name_hint=name,
            )
        )
    except Exception:
        # A caller-provided worktree outlives this sandbox by design — only
        # close what this factory carved itself. A cleanup failure must not
        # replace the creation error, so it is reported and suppressed.
        if owns_worktree:
            try:
                wt.close()
            except Exception as cleanup_exc:
                print(f"eden: worktree cleanup also failed: {cleanup_exc}")
        raise

    return Sandbox(
        worktree=wt,
        handle=handle,
        sandbox_provider=sandbox,
        cwd=cwd,
        owns_worktree=owns_worktree,
    )

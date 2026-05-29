"""Shared frozen dataclasses for eden's public result surface.

Convention: every type here is a ``@dataclass(frozen=True)``. ``frozen``
prevents attribute reassignment on the dataclass itself; it does NOT make
contained collections (``list``, ``dict``) read-only. Callers should treat
the contained ``iterations``, ``commits``, and ``env`` collections on
``RunResult`` as snapshots — eden never mutates them after construction
and consumers should not either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eden.agents._protocol import Agent
    from eden.providers._protocols import SandboxProvider


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Commit:
    sha: str


@dataclass(frozen=True)
class Iteration:
    index: int
    completion_signal: str | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None


@dataclass(frozen=True)
class Timeouts:
    hook_step: float = 60.0
    iteration_step: float | None = None
    copy_to_worktree: float = 60.0


@dataclass(frozen=True)
class _RunContext:
    """Captured ``run()`` parameters that ``RunResult.resume()`` / ``.fork()`` re-use.

    Frozen, internal. Stored on :class:`RunResult` so the continuation
    methods can re-invoke ``eden.run`` with the same agent / sandbox /
    cwd without forcing the caller to re-pass them. ``hooks`` / ``env``
    / ``copy_to_worktree`` are deliberately omitted: most continuations
    rerun the same hooks anyway, and adding them here would force
    deep-copies of mutable Hooks objects that the caller may still hold.
    Callers needing override control pass kwargs to ``resume()`` /
    ``fork()``.
    """

    agent: Agent
    sandbox: SandboxProvider
    cwd: Path


@dataclass(frozen=True)
class RunResult:
    iterations: list[Iteration]
    completion_signal: str | None
    branch: str
    stdout: str
    commits: list[Commit]
    worktree_path: Path
    preserved_worktree_path: Path | None
    merged_to_target_branch: str | None
    cwd: Path
    prompt: str
    env: dict[str, str]
    log_file_path: Path | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None
    output: object | None = None
    _ctx: _RunContext | None = field(default=None, repr=False, compare=False)
    """Captured ``run()`` parameters; used by :meth:`resume` and :meth:`fork`.

    Excluded from ``repr`` (would print the entire agent / sandbox)
    and ``__eq__`` (so equality between two RunResults still compares
    only the data fields).
    """

    def resume(self, prompt: str, **overrides: Any) -> RunResult:
        """Run a follow-up iteration continuing this result's captured session.

        Equivalent to ``eden.run(agent=..., sandbox=..., cwd=...,
        prompt=prompt, resume_session=self.session_id, **overrides)`` with
        the agent / sandbox / cwd inherited from the call that produced
        this result. Mirrors upstream's ``RunResult.resume(prompt)``
        (v0.6.6, 58f335f).

        ``overrides`` accepts any kwarg :func:`eden.run` accepts; explicit
        overrides win over the captured context.

        Raises :class:`eden.errors.InvalidOptions` when no session was
        captured (``capture_sessions=False`` on the agent, or the agent
        never emitted a session id) or when the result was produced by an
        in-process API that does not store the run context.
        """
        return _continue(self, prompt=prompt, fork=False, overrides=overrides)

    def fork(self, prompt: str, **overrides: Any) -> RunResult:
        """Run a follow-up iteration that writes a NEW session id while
        continuing from this result's captured state.

        Lets concurrent fan-out (``r.fork(a)`` and ``r.fork(b)`` in
        parallel) avoid corrupting the parent session. Safe concurrent
        fan-out also requires distinct branches per child via
        ``branch_strategy=BranchStrategy.named(...)`` in ``overrides``;
        head and merge_to_head strategies are not safe for concurrent
        forks because every child writes to the same worktree. Mirrors
        upstream's ``RunResult.fork(prompt)`` (v0.6.6, 58f335f).

        Implemented via ``--fork-session`` (claude_code) /
        ``codex exec fork <id>`` (codex). Agents without session support
        raise :class:`eden.errors.InvalidOptions`.
        """
        return _continue(self, prompt=prompt, fork=True, overrides=overrides)


def _continue(
    result: RunResult,
    *,
    prompt: str,
    fork: bool,
    overrides: dict[str, Any],
) -> RunResult:
    """Shared implementation of ``RunResult.resume`` / ``.fork``."""
    from eden.errors import InvalidOptions

    if result._ctx is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=("RunResult has no captured run context; cannot resume / fork"),
            hint="resume / fork only work on results returned by eden.run()",
        )
    if result.session_id is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "RunResult has no session_id; cannot resume / fork. The agent "
                "either did not capture a session or did not emit one this run."
            ),
            hint=(
                "ensure the agent has capture_sessions=True (default for "
                "claude_code / codex / pi) and that the iteration produced a "
                "session id"
            ),
        )
    from eden.orchestrator import run as _run

    kwargs: dict[str, Any] = {
        "agent": result._ctx.agent,
        "sandbox": result._ctx.sandbox,
        "cwd": result._ctx.cwd,
        "prompt": prompt,
        "resume_session": result.session_id,
        "fork_session": fork,
    }
    kwargs.update(overrides)
    return _run(**kwargs)

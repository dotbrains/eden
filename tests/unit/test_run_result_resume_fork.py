"""Verify ``RunResult.resume()`` / ``.fork()`` sugar + fork_session wiring.

The resume/fork methods are pure sugar over ``eden.run(...,
resume_session=..., fork_session=...)`` — but they require the run loop
to thread ``fork_session`` through ``IterationContext`` and the agent's
argv builder. Both layers are covered here.
"""

from __future__ import annotations

import pytest

from eden._types import _RunContext
from eden.agents._context import IterationContext
from eden.agents.claude_code._argv import build_argv as claude_argv
from eden.agents.codex._argv import build_argv as codex_argv
from eden.errors import InvalidOptions

pytestmark = pytest.mark.unit


def test_iteration_context_defaults_fork_false() -> None:
    """Existing callers don't need to pass fork_session — it defaults False."""
    from pathlib import Path

    class _Stub:
        worktree_path = Path("/workspace")

        def exec(self, cmd, **kw):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def copy_file_in(self, host, sandbox):  # type: ignore[no-untyped-def]
            pass

        def copy_file_out(self, sandbox, host):  # type: ignore[no-untyped-def]
            pass

        def close(self) -> None:
            pass

    ctx = IterationContext(
        iteration=0,
        prompt="p",
        sandbox_handle=_Stub(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )
    assert ctx.fork_session is False


def test_claude_argv_fork_session_appended_only_with_resume() -> None:
    """``--fork-session`` must follow ``--resume <id>`` — never standalone."""
    # With resume + fork → both flags present.
    argv = claude_argv(
        model="m",
        effort=None,
        extra_args=(),
        resume_session="sess",
        fork_session=True,
    )
    i = argv.index("--resume")
    assert argv[i + 1] == "sess"
    assert "--fork-session" in argv
    assert argv.index("--fork-session") == i + 2  # immediately after the id


def test_claude_argv_fork_without_resume_omits_flag() -> None:
    """Defence in depth: a caller forgetting resume_session doesn't get a stray flag."""
    argv = claude_argv(model="m", effort=None, extra_args=(), fork_session=True)
    assert "--fork-session" not in argv
    assert "--resume" not in argv


def test_codex_argv_uses_fork_subcommand_when_fork_true() -> None:
    """``codex exec fork <id>`` replaces ``codex exec resume <id>``."""
    argv = codex_argv(
        model="m",
        effort=None,
        extra_args=(),
        resume_session="sess",
        fork_session=True,
    )
    # Order: codex, exec, fork, sess
    assert argv[:4] == ["codex", "exec", "fork", "sess"]
    assert "resume" not in argv


def test_codex_argv_uses_resume_subcommand_by_default() -> None:
    argv = codex_argv(
        model="m",
        effort=None,
        extra_args=(),
        resume_session="sess",
    )
    assert argv[:4] == ["codex", "exec", "resume", "sess"]
    assert "fork" not in argv


def test_runresult_resume_raises_without_ctx() -> None:
    """A RunResult with no captured context can't resume."""
    from eden._types import RunResult

    r = RunResult(
        iterations=[],
        completion_signal=None,
        branch="b",
        stdout="",
        commits=[],
        worktree_path=__import__("pathlib").Path("/wt"),
        preserved_worktree_path=None,
        merged_to_target_branch=None,
        cwd=__import__("pathlib").Path("/cwd"),
        prompt="",
        env={},
        log_file_path=None,
        session_id="sess",
        session_file_path=None,
        usage=None,
    )
    with pytest.raises(InvalidOptions) as excinfo:
        r.resume("follow-up")
    assert "captured run context" in excinfo.value.message


def test_runresult_resume_raises_without_session_id() -> None:
    """A captured RunResult with no session_id can't resume."""
    from pathlib import Path

    from eden._types import RunResult
    from eden.agents.simulated import simulated_agent
    from eden.sandboxes.no_sandbox import provider as no_sandbox

    r = RunResult(
        iterations=[],
        completion_signal=None,
        branch="b",
        stdout="",
        commits=[],
        worktree_path=Path("/wt"),
        preserved_worktree_path=None,
        merged_to_target_branch=None,
        cwd=Path("/cwd"),
        prompt="",
        env={},
        log_file_path=None,
        session_id=None,  # no session
        session_file_path=None,
        usage=None,
        _ctx=_RunContext(
            agent=simulated_agent(),
            sandbox=no_sandbox(),
            cwd=Path("/cwd"),
        ),
    )
    with pytest.raises(InvalidOptions) as excinfo:
        r.resume("follow-up")
    assert "session_id" in excinfo.value.message


def test_fork_requires_resume_session_at_run_level() -> None:
    """``eden.run(fork_session=True)`` without ``resume_session`` errors out."""
    from pathlib import Path

    from eden.agents.simulated import simulated_agent
    from eden.orchestrator import run
    from eden.sandboxes.no_sandbox import provider as no_sandbox

    with pytest.raises(InvalidOptions) as excinfo:
        run(
            agent=simulated_agent(),
            sandbox=no_sandbox(),
            prompt="x",
            cwd=Path.cwd(),
            fork_session=True,
        )
    assert "fork_session" in excinfo.value.message

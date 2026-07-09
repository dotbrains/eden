"""E2E: ``eden.interactive()`` runs the agent attached to the parent stdio."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.cli import cli_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def _exit_zero_agent() -> eden.Agent:
    """Build an agent whose argv exits 0 immediately (fast e2e)."""

    def _build(_ctx: IterationContext) -> list[str]:
        return [sys.executable, "-c", "import sys; sys.exit(0)"]

    return cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)


def _exit_n_agent(n: int) -> eden.Agent:
    def _build(_ctx: IterationContext) -> list[str]:
        return [sys.executable, "-c", f"import sys; sys.exit({n})"]

    return cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)


def test_interactive_returns_exit_code_and_branch(e2e_git_repo: Path) -> None:
    result = eden.interactive(
        agent=_exit_zero_agent(),
        sandbox=no_sandbox(),
    )
    assert isinstance(result, eden.InteractiveResult)
    assert result.exit_code == 0
    # Default branch strategy with no_sandbox is "head" — branch is "HEAD".
    assert result.branch == "HEAD"
    assert result.cwd == e2e_git_repo


def test_interactive_propagates_nonzero_exit(e2e_git_repo: Path) -> None:
    result = eden.interactive(
        agent=_exit_n_agent(7),
        sandbox=no_sandbox(),
    )
    assert result.exit_code == 7


def test_interactive_rejects_isolated_sandbox(e2e_git_repo: Path) -> None:
    """Isolated providers don't expose a TTY (no container to exec into)."""
    from eden.sandboxes.isolated import provider as isolated

    with pytest.raises(eden.InvalidOptions) as ex:
        eden.interactive(
            agent=_exit_zero_agent(),
            sandbox=isolated(),
        )
    assert "interactive" in ex.value.message.lower()


def test_interactive_default_sandbox_is_no_sandbox(e2e_git_repo: Path) -> None:
    """Calling interactive() without sandbox= falls back to no_sandbox()."""
    result = eden.interactive(agent=_exit_zero_agent())
    assert result.exit_code == 0


def test_interactive_rejects_pre_aborted_signal(e2e_git_repo: Path) -> None:
    ctrl = eden.AbortController()
    ctrl.abort(reason="stop")

    with pytest.raises(eden.Aborted) as ex:
        eden.interactive(agent=_exit_zero_agent(), sandbox=no_sandbox(), signal=ctrl.signal)

    assert ex.value.reason == "stop"


def test_interactive_aborts_running_session(e2e_git_repo: Path) -> None:
    ctrl = eden.AbortController()

    def _abort_soon() -> None:
        time.sleep(0.2)
        ctrl.abort(reason="stop")

    thread = threading.Thread(target=_abort_soon, daemon=True)
    thread.start()
    try:
        with pytest.raises(eden.Aborted) as ex:
            eden.interactive(
                agent=cli_agent(
                    name="sleepy",
                    model="x",
                    binary="ignored",
                    build_argv=lambda _ctx: [
                        sys.executable,
                        "-c",
                        "import time; time.sleep(30)",
                    ],
                ),
                sandbox=no_sandbox(),
                signal=ctrl.signal,
            )
    finally:
        thread.join(timeout=2.0)

    assert ex.value.reason == "stop"


def test_interactive_carves_named_branch(e2e_git_repo: Path) -> None:
    result = eden.interactive(
        agent=_exit_zero_agent(),
        sandbox=no_sandbox(),
        branch_strategy=eden.BranchStrategy.named("eden/interactive-test"),
    )
    assert result.branch == "eden/interactive-test"
    assert result.worktree_path != e2e_git_repo


def test_worktree_interactive_uses_existing_worktree(e2e_git_repo: Path) -> None:
    with eden.create_worktree() as wt:
        result = wt.interactive(agent=_exit_zero_agent(), sandbox=no_sandbox())
        assert result.exit_code == 0
        assert result.branch == wt.branch
        assert result.worktree_path == wt.worktree_path
        assert wt.worktree_path.exists()


def test_worktree_interactive_rejects_pre_aborted_signal(e2e_git_repo: Path) -> None:
    ctrl = eden.AbortController()
    ctrl.abort(reason="stop")

    with eden.create_worktree() as wt:
        with pytest.raises(eden.Aborted) as ex:
            wt.interactive(agent=_exit_zero_agent(), sandbox=no_sandbox(), signal=ctrl.signal)

    assert ex.value.reason == "stop"


def test_interactive_uses_build_interactive_command_when_present(
    e2e_git_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """If the agent defines build_interactive_command, eden uses it over build_command."""
    # Put the log file outside the git repo so head-strategy doesn't block on
    # untracked files.
    out_dir = tmp_path_factory.mktemp("interactive-log")
    log_file = out_dir / "log.txt"
    log_file.touch()

    class _Probe:
        name = "probe"
        model = "x"

        def build_command(self, ctx: IterationContext) -> list[str]:
            return [sys.executable, "-c", f"open({str(log_file)!r}, 'w').write('build_command')"]

        def build_interactive_command(self, ctx: IterationContext) -> list[str]:
            return [
                sys.executable,
                "-c",
                f"open({str(log_file)!r}, 'w').write('build_interactive_command')",
            ]

        def parse_stream(self, _line: str) -> None:  # pragma: no cover - unused here
            return None

    eden.interactive(agent=_Probe(), sandbox=no_sandbox())
    assert log_file.read_text() == "build_interactive_command"


def test_interactive_renders_prompt_substitutions(e2e_git_repo: Path, tmp_path: Path) -> None:
    """Agent receives a rendered prompt via build_interactive_command(ctx)."""
    seen: list[str] = []

    class _Probe:
        name = "probe"
        model = "x"

        def build_interactive_command(self, ctx: IterationContext) -> list[str]:
            seen.append(ctx.prompt)
            return [sys.executable, "-c", "import sys; sys.exit(0)"]

        def build_command(self, ctx: IterationContext) -> list[str]:  # pragma: no cover
            return self.build_interactive_command(ctx)

        def parse_stream(self, _line: str) -> None:  # pragma: no cover
            return None

    eden.interactive(
        agent=_Probe(),
        sandbox=no_sandbox(),
        prompt="branch={{SOURCE_BRANCH}}",
    )
    assert len(seen) == 1
    assert seen[0].startswith("branch=")


def test_interactive_rejects_non_git_cwd(tmp_path: Path) -> None:
    """Mirroring run(), interactive() requires a git repo."""
    with pytest.raises(eden.CwdError):
        eden.interactive(
            agent=_exit_zero_agent(),
            sandbox=no_sandbox(),
            cwd=tmp_path,  # not a git repo
        )

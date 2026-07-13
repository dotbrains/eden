"""E2E: basic interactive execution and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox
from tests.e2e.interactive_helpers import exit_n_agent, exit_zero_agent

pytestmark = pytest.mark.e2e


def test_interactive_returns_exit_code_and_branch(e2e_git_repo: Path) -> None:
    result = eden.interactive(
        agent=exit_zero_agent(),
        sandbox=no_sandbox(),
    )
    assert isinstance(result, eden.InteractiveResult)
    assert result.exit_code == 0
    # Default branch strategy with no_sandbox is "head" - branch is "HEAD".
    assert result.branch == "HEAD"
    assert result.cwd == e2e_git_repo


def test_interactive_propagates_nonzero_exit(e2e_git_repo: Path) -> None:
    result = eden.interactive(
        agent=exit_n_agent(7),
        sandbox=no_sandbox(),
    )
    assert result.exit_code == 7


def test_interactive_default_sandbox_is_no_sandbox(e2e_git_repo: Path) -> None:
    """Calling interactive() without sandbox= falls back to no_sandbox()."""
    result = eden.interactive(agent=exit_zero_agent())
    assert result.exit_code == 0


def test_interactive_rejects_non_git_cwd(tmp_path: Path) -> None:
    """Mirroring run(), interactive() requires a git repo."""
    with pytest.raises(eden.CwdError):
        eden.interactive(
            agent=exit_zero_agent(),
            sandbox=no_sandbox(),
            cwd=tmp_path,
        )

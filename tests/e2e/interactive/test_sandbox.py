"""E2E: interactive sandbox compatibility checks."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from tests.e2e.interactive_helpers import exit_zero_agent

pytestmark = pytest.mark.e2e


def test_interactive_rejects_isolated_sandbox(e2e_git_repo: Path) -> None:
    """Isolated providers don't expose a TTY."""
    from eden.sandboxes.isolated import provider as isolated

    with pytest.raises(eden.InvalidOptions) as ex:
        eden.interactive(
            agent=exit_zero_agent(),
            sandbox=isolated(),
        )
    assert "interactive" in ex.value.message.lower()

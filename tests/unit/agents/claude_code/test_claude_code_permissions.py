"""Verify claude_code permission flags."""

from __future__ import annotations

import pytest

from eden.agents import claude_code
from eden.errors import InvalidOptions
from tests.unit.agents.claude_code._helpers import _ctx

pytestmark = pytest.mark.unit


def test_dangerously_skip_permissions_default_off() -> None:
    a = claude_code(model="m")
    argv = a.build_command(_ctx())
    assert "--dangerously-skip-permissions" not in argv


def test_dangerously_skip_permissions_appends_flag() -> None:
    a = claude_code(model="m", dangerously_skip_permissions=True)
    argv = a.build_command(_ctx())
    assert "--dangerously-skip-permissions" in argv
    # Flag must precede the prompt-stdin sigil.
    assert argv.index("--dangerously-skip-permissions") < argv.index("-p")


def test_dangerously_skip_permissions_propagates_to_interactive() -> None:
    a = claude_code(model="m", dangerously_skip_permissions=True)
    argv = a.build_interactive_command(_ctx(prompt=""))
    assert "--dangerously-skip-permissions" in argv


def test_permission_mode_default_off() -> None:
    a = claude_code(model="m")
    argv = a.build_command(_ctx())
    assert "--permission-mode" not in argv


def test_permission_mode_appends_flag() -> None:
    a = claude_code(model="m", permission_mode="acceptEdits")
    argv = a.build_command(_ctx())
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
    assert argv.index("--permission-mode") < argv.index("-p")


def test_permission_mode_propagates_to_interactive() -> None:
    a = claude_code(model="m", permission_mode="plan")
    argv = a.build_interactive_command(_ctx(prompt=""))
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "plan"


def test_permission_mode_invalid_value_raises() -> None:
    with pytest.raises(InvalidOptions, match="permission_mode"):
        claude_code(model="m", permission_mode="bogus")  # type: ignore[arg-type]


def test_permission_mode_conflicts_with_skip_permissions() -> None:
    with pytest.raises(InvalidOptions, match="at most one"):
        claude_code(
            model="m",
            permission_mode="acceptEdits",
            dangerously_skip_permissions=True,
        )

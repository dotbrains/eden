"""Verify the backlog-manager registry shape and the new 'custom' entry."""

from __future__ import annotations

import pytest

from eden.cli._templates._backlog import (
    BacklogManager,
    get_backlog_manager,
    list_backlog_managers,
)

pytestmark = pytest.mark.unit


def test_known_managers() -> None:
    names = {m.name for m in list_backlog_managers()}
    assert names == {"github", "beads", "linear", "jira", "custom"}


def test_get_each_known_returns_manager() -> None:
    for name in ("github", "beads", "linear", "jira", "custom"):
        m = get_backlog_manager(name)
        assert isinstance(m, BacklogManager)
        assert m.name == name


def test_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_backlog_manager("not-real")  # type: ignore[arg-type]


def test_custom_entry_is_broken_until_configured() -> None:
    """Upstream parity: 'custom' scaffolds <TODO> stubs that the agent
    wires up on first run. Verify the markers are present so the agent
    has something to find."""
    m = get_backlog_manager("custom")
    assert "<TODO" in m.list_tasks_command
    assert "<TODO" in m.view_task_command
    assert "<TODO" in m.close_task_command
    assert "<TODO" in m.dockerfile_install
    assert "<TODO" in m.env_example_lines


def test_beads_close_uses_reason_flag() -> None:
    """Regression guard for upstream 0.6.0 fix."""
    m = get_backlog_manager("beads")
    assert "--reason" in m.close_task_command
    assert '"Completed by Eden"' in m.close_task_command


def test_gh_issue_list_has_limit_100() -> None:
    """Regression guard for upstream 0.6.0 fix."""
    m = get_backlog_manager("github")
    assert "--limit 100" in m.list_tasks_command


def test_beads_dockerfile_detects_arch() -> None:
    """Regression guard for the arm64 fix."""
    m = get_backlog_manager("beads")
    assert "uname -m" in m.dockerfile_install
    assert "bd-linux-${ARCH}" in m.dockerfile_install

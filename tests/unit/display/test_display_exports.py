"""Verify public Display exports."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_top_level_display_exports() -> None:
    """All three sinks plus the Display protocol are top-level imports."""
    from eden import Display, FileDisplay, RichDisplay, SilentDisplay

    assert Display is not None
    assert SilentDisplay is not None
    assert FileDisplay is not None
    assert RichDisplay is not None

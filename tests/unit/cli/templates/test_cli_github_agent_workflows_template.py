"""Verify GitHub agent workflow template rendering."""

from __future__ import annotations

from hashlib import sha256

import pytest

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.github import render_github_agent_workflows

pytestmark = pytest.mark.unit


def _fingerprint(files: dict[str, str]) -> str:
    rendered = "".join(f"{path}\0{contents}\0" for path, contents in sorted(files.items()))
    return sha256(rendered.encode()).hexdigest()


def test_render_github_agent_workflows_exact_github_output() -> None:
    files = render_github_agent_workflows(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:test",
        backlog=get_backlog_manager("github"),
    )

    assert set(files) == {
        "../.github/workflows/eden-agent-implement.yml",
        "../.github/workflows/eden-agent-review.yml",
        "Dockerfile",
        "github/implement_issue.py",
        "github/review_pr.py",
        "github/factory.py",
        "github/implement-issue.md",
        "github/review-pr.md",
        "github/SETUP_TRACKER.md",
        "github/REVIEW_OUTPUT.md",
        "CODING_STANDARDS.md",
        ".env.example",
        ".gitignore",
    }
    assert _fingerprint(files) == "edf55eb643b548d5a9c55c80172f170e39a75067c402dc2f4c4f7743ee8d1ca8"


def test_render_github_agent_workflows_exact_custom_output() -> None:
    files = render_github_agent_workflows(
        sandbox="podman",
        agent="codex",
        model="gpt-5",
        image_name="eden:pod",
        backlog=get_backlog_manager("custom"),
    )

    assert _fingerprint(files) == "ff43e9659b52a3d1fca022e755e24d147f738826c5c62b80ac88b38b354e7a98"

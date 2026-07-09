"""Verify GitHub agent workflow template rendering."""

from __future__ import annotations

from hashlib import sha256

import pytest

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.github_agent_workflows import render_github_agent_workflows

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
    assert _fingerprint(files) == "85e789f7479b625b4159f5b7812cc3508f9d20b07ca7fb8ed1edd445341fffc2"


def test_render_github_agent_workflows_exact_custom_output() -> None:
    files = render_github_agent_workflows(
        sandbox="podman",
        agent="codex",
        model="gpt-5",
        image_name="eden:pod",
        backlog=get_backlog_manager("custom"),
    )

    assert _fingerprint(files) == "de8420965d803550f964e3ecde7ef8d9f6cc127d3062de5ccc1ecf2ae01700fe"

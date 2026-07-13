"""GitHub Actions workflow helpers for the GitHub agent template."""

from __future__ import annotations

from eden.cli._templates.github._implement_workflow import IMPLEMENT_WORKFLOW
from eden.cli._templates.github._review_workflow import REVIEW_WORKFLOW


def render_workflow(text: str, *, image_name: str) -> str:
    """Undo Python-format escaping used for GitHub Actions expressions."""
    return (
        text.removeprefix("\\\n")
        .replace("{image_name}", image_name)
        .replace("${{{{", "${{")
        .replace("}}}}", "}}")
        .replace("${{GH_REPO%/*}}", "${GH_REPO%/*}")
        .replace("${{GH_REPO#*/}}", "${GH_REPO#*/}")
        .replace("${{author}}", "${author}")
        .replace("${{ISSUE_TITLE}}", "${ISSUE_TITLE}")
        .replace("${{title:0:256}}", "${title:0:256}")
        .replace("${{GH_REPO}}", "${GH_REPO}")
        .replace("${{ISSUE_NUMBER}}", "${ISSUE_NUMBER}")
        .replace("${{PARENT_NUMBER}}", "${PARENT_NUMBER}")
        .replace("${{SUB_COUNT}}", "${SUB_COUNT}")
        .replace("${{EXISTING_PR_URL}}", "${EXISTING_PR_URL}")
        .replace("${{RUNNER_TEMP}}", "${RUNNER_TEMP}")
        .replace("${{BRANCH}}", "${BRANCH}")
        .replace("${{BRANCH_HEAD_SHA}}", "${BRANCH_HEAD_SHA}")
        .replace("${{PR_NUMBER}}", "${PR_NUMBER}")
        .replace("${{rest_id}}", "${rest_id}")
        .replace("\\\\$", "\\$")
    )


__all__ = ["IMPLEMENT_WORKFLOW", "REVIEW_WORKFLOW", "render_workflow"]

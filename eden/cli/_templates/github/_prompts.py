"""Prompt text for GitHub agent workflows."""

from __future__ import annotations

IMPLEMENT_PROMPT = """\
# GitHub Issue

Issue #{{{{ISSUE_NUMBER}}}}: {{{{ISSUE_TITLE}}}}

!`gh issue view {{{{ISSUE_NUMBER}}}} --comments`

# Task

Implement the issue on branch `{{{{SOURCE_BRANCH}}}}`.

Workflow:
1. Read the issue and relevant files.
2. Make the smallest coherent code change.
3. Run focused tests and linters.
4. Commit with an `eden:` prefix.

When complete, output:

<promise>COMPLETE</promise>
"""

REVIEW_PROMPT = """\
# Pull Request Review

Review branch `{{{{SOURCE_BRANCH}}}}` against `{{{{TARGET_BRANCH}}}}`.

## Diff

!`git diff {{{{TARGET_BRANCH}}}}...{{{{SOURCE_BRANCH}}}}`

## Existing review comments

!`gh pr view {{{{PR_NUMBER}}}} --json comments,reviews`

## Standards

Read `.eden/CODING_STANDARDS.md`.

# Required Output

Write a GitHub review payload to `$REVIEW_OUTPUT`:

```json
{{"event":"COMMENT","body":"summary","comments":[]}}
```

Write thread replies to `$REVIEW_REPLIES`:

```json
[{{"commentId":"PRRC_kw...","body":"reply"}}]
```

If changes are needed, commit them with `review:`. Then output:

<promise>COMPLETE</promise>
"""

__all__ = ["IMPLEMENT_PROMPT", "REVIEW_PROMPT"]

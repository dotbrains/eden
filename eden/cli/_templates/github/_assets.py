"""Prompt and script text for the GitHub agent template."""

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

IMPLEMENT_SCRIPT = """\
from __future__ import annotations

import os

from eden import BranchStrategy, create_sandbox, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider

issue_number = os.environ["ISSUE_NUMBER"]
issue_title = os.environ["ISSUE_TITLE"]
branch = f"eden/issue-{{issue_number}}"

with create_sandbox(
    sandbox=sandbox_provider.provider({image_arg}),
    branch_strategy=BranchStrategy.named(branch),
    name=f"github-issue-{{issue_number}}",
) as sandbox:
    result = sandbox.run(
        name=f"implement-{{issue_number}}",
        agent={agent_call},
        prompt_file=".eden/github/implement-issue.md",
        prompt_args={{"ISSUE_NUMBER": issue_number, "ISSUE_TITLE": issue_title}},
        max_iterations=10,
    )
    if not result.commits:
        raise SystemExit("implementer produced no commits")
"""

REVIEW_SCRIPT = """\
from __future__ import annotations

import os
from pathlib import Path

from eden import BranchStrategy, create_sandbox, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider

pr_number = os.environ["PR_NUMBER"]
branch = os.environ["BRANCH"]

Path(os.environ["REVIEW_OUTPUT"]).write_text(
    '{{"event":"COMMENT","body":"Eden review completed.","comments":[]}}',
    encoding="utf-8",
)
Path(os.environ["REVIEW_REPLIES"]).write_text("[]", encoding="utf-8")

with create_sandbox(
    sandbox=sandbox_provider.provider({image_arg}),
    branch_strategy=BranchStrategy.head(),
    name=f"github-review-{{pr_number}}",
) as sandbox:
    sandbox.run(
        name=f"review-{{pr_number}}",
        agent={agent_call},
        prompt_file=".eden/github/review-pr.md",
        prompt_args={{"PR_NUMBER": pr_number}},
        max_iterations=3,
    )
"""

FACTORY_SCRIPT = """\
from __future__ import annotations

import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from eden import BranchStrategy, create_sandbox, create_worktree, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider

MAX_PARALLEL = int(os.environ.get("EDEN_FACTORY_MAX_PARALLEL", "4"))


def _tasks() -> list[dict[str, str]]:
    raw = os.popen({list_tasks_command!r}).read()
    return json.loads(raw or "[]")


def _run_task(task: dict[str, str]) -> str:
    task_id = str(task["id"])
    branch = f"eden/factory/{{task_id}}"
    original_cwd = os.getcwd()
    with create_worktree(
        branch_strategy=BranchStrategy.named(branch),
    ) as worktree:
        try:
            os.chdir(worktree.worktree_path)
            with create_sandbox(
                sandbox=sandbox_provider.provider({image_arg}),
                branch_strategy=BranchStrategy.head(),
            ) as sandbox:
                result = sandbox.run(
                    name=f"factory-{{task_id}}",
                    agent={agent_call},
                    prompt_file=".eden/github/implement-issue.md",
                    prompt_args={{
                        "ISSUE_NUMBER": task_id,
                        "ISSUE_TITLE": str(task.get("title", task_id)),
                    }},
                    max_iterations=10,
                )
                return f"{{task_id}}: {{len(result.commits)}} commits on {{branch}}"
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    tasks = _tasks()[:MAX_PARALLEL]
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futures = [pool.submit(_run_task, task) for task in tasks]
        for future in as_completed(futures):
            print(future.result())
"""

SETUP_TRACKER = """\
# Custom Tracker Setup

This scaffold is ready for GitHub Actions, but the selected backlog manager is
`{backlog_name}`. If it is `custom`, replace every `<TODO: ...>` command in
`.eden/github/factory.py`, `.eden/Dockerfile`, and `.eden/.env.example` before
running the factory.

Tracker commands should follow this contract:

- list: print JSON array objects with `id`, `title`, and optional `body`.
- view: print one task body for a stable id.
- close: mark a task complete only after tests pass and commits exist.

For GitHub-backed workflows, create these labels:

- `agent:implement`
- `agent:review`
- `agent:blocked`
- `agent:in-progress`
"""

REVIEW_CONTRACT = """\
# GitHub Review Output Contract

`.eden/github/review-pr.md` asks the reviewer to write two files.

`$REVIEW_OUTPUT` is sent to `POST /pulls/{number}/reviews`:

```json
{{"event":"COMMENT","body":"Summary.","comments":[]}}
```

`$REVIEW_REPLIES` is an array of replies to existing review comments:

```json
[{{"commentId":"PRRC_kw...","body":"Fixed in review commit abc123."}}]
```

Keep payloads small. If the reviewer changes code, it should commit with a
`review:` prefix before writing the payload.
"""


__all__ = [
    "FACTORY_SCRIPT",
    "IMPLEMENT_PROMPT",
    "IMPLEMENT_SCRIPT",
    "REVIEW_CONTRACT",
    "REVIEW_PROMPT",
    "REVIEW_SCRIPT",
    "SETUP_TRACKER",
]

"""sequential-reviewer template content.

A two-phase loop per task: an implementer agent commits changes on a named
branch, then a reviewer agent inspects the diff and approves or corrects.
Both agents share one ``Sandbox`` so the second run sees the implementer's
working tree directly.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._common import render_agent_call, render_agent_install
from eden.cli._templates._env import render_env_example
from eden.cli._templates.sequential_reviewer_assets import (
    DOCKERFILE,
    GITIGNORE,
    MAIN_PY,
)

IMPLEMENT_PROMPT = """\
# Context

## Open tasks

!`{list_tasks_command}`

The list above has already been filtered to tasks ready for work — do not
re-query the tracker or pull in tasks outside this list. If the list is
empty, there is nothing to do this iteration.

## Recent eden commits (last 10)

!`git log --oneline --grep="eden:" -10`

# Task

You are an autonomous coding agent. Pick the highest-priority open task and
implement it on this branch.

## Workflow

1. **Explore** — read the task and the relevant source files / tests.
2. **Plan** — decide what to change. Keep it small.
3. **Execute** — red/green/refactor: failing test first, then code.
4. **Verify** — run typecheck and tests; fix failures before continuing.
5. **Commit** — single git commit, `eden:` prefix.
6. **Close** — `{close_task_command}`.

## Rules

- One task per iteration.
- Do not close a task until tests pass and the commit is made.
- Do not leave commented-out code.

# Done

When the task is implemented and committed, output:

<promise>COMPLETE</promise>
"""


REVIEW_PROMPT = """\
# Task

Review the code changes on branch `{{{{SOURCE_BRANCH}}}}` and improve clarity,
consistency, and maintainability while preserving exact functionality.

# Context

## Branch diff

!`git diff {{{{TARGET_BRANCH}}}}...{{{{SOURCE_BRANCH}}}}`

## Commits on this branch

!`git log {{{{TARGET_BRANCH}}}}..{{{{SOURCE_BRANCH}}}} --oneline`

## Coding standards

See `.eden/CODING_STANDARDS.md`.

# Process

1. Read the diff and commits to understand the intent.
2. Look for opportunities to simplify, consolidate, or rename.
3. Check correctness — edge cases, error handling, type safety.
4. If the code is already clean, output `<promise>APPROVED</promise>` and stop.
5. Otherwise, make the corrections directly on this branch with a follow-up
   commit prefixed `review:`.

# Done

<promise>COMPLETE</promise>
"""


CODING_STANDARDS = """\
# Coding standards

These are the standards the reviewer agent enforces. Edit to fit your project.

## Clarity over cleverness

- Prefer explicit over implicit.
- Name things for what they are, not what they were.
- One branch = one logical change.

## Test discipline

- Every behaviour change has a test that fails without the fix.
- Integration tests beat mocks at boundaries you don't own.

## Commits

- Subject ≤ 72 characters, imperative mood.
- Body explains *why*, not *what*.
"""


def render_sequential_reviewer(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the sequential-reviewer files."""
    agent_import, agent_call = render_agent_call(
        template="sequential-reviewer",
        agent=agent,
        model=model,
    )
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)

    return {
        "Dockerfile": DOCKERFILE.format(
            agent_install=render_agent_install(agent),
            backlog_install=backlog.dockerfile_install,
        ),
        "implement-prompt.md": IMPLEMENT_PROMPT.format(
            list_tasks_command=backlog.list_tasks_command,
            close_task_command=backlog.close_task_command,
        ),
        "review-prompt.md": REVIEW_PROMPT,
        "CODING_STANDARDS.md": CODING_STANDARDS,
        "main.py": MAIN_PY.format(
            agent_import=agent_import,
            sandbox=sandbox,
            image_arg=image_arg,
            agent_call=agent_call,
        ),
        ".env.example": env_example,
        ".gitignore": GITIGNORE,
    }


__all__ = ["render_sequential_reviewer"]

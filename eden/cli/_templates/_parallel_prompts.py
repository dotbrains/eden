"""Shared prompt text for parallel planning templates."""

from __future__ import annotations

PARALLEL_PLAN_PROMPT = """\
# Task

Analyse the open backlog and build a dependency graph. Pick the tasks that are
**unblocked right now** — those whose dependencies are either closed or
non-existent — and emit a JSON plan listing them.

Each task gets a branch name using the exact format
``{branch_prefix}/<task-id>``. Do not add a slug or any other suffix; the name
must be deterministic so replanning the same task reuses the same branch.

# Context

## Open tasks

!`{list_tasks_command}`

The list above has already been filtered to tasks ready for work — do not
re-query the tracker or pull in tasks outside this list.

## Recent eden commits (last 10)

!`git log --oneline --grep="eden:" -10`

# Output format

Emit a single ``<plan>...</plan>`` block whose body is JSON:

```json
{{"tasks": [
  {{"id": "<task id>", "title": "<short title>", "branch": "{branch_prefix}/<task id>"}}
]}}
```

If nothing is unblocked, emit an empty ``tasks`` list — the outer loop will exit.

Do not pick more tasks than make sense to run in parallel; 4-6 is usually fine.
"""

PARALLEL_IMPLEMENT_PROMPT = """\
# Context

## Task

Task ID:    `{{{{TASK_ID}}}}`
Branch:     `{{{{TASK_BRANCH}}}}`
Title:      {{{{TASK_TITLE}}}}

## Task body

!`{view_task_command_subbed}`

## Recent eden commits (last 10)

!`git log --oneline --grep="eden:" -10`

# Workflow

1. **Explore** — read the task and the relevant source / tests.
2. **Plan** — decide what to change. Keep it small.
3. **Execute** — red/green/refactor: failing test first, then code.
4. **Verify** — run typecheck and tests; fix failures before continuing.
5. **Commit** — single git commit, ``eden:`` prefix.
6. **Close** — `{close_task_command}`.

# Done

When the task is implemented and committed, output:

<promise>COMPLETE</promise>
"""

PARALLEL_MERGE_PROMPT = """\
# Task

Merge the listed branches into the current branch.

# Branches to merge

{{{{BRANCHES}}}}

# Tasks completed

{{{{TASKS}}}}

# Steps

1. For each branch listed above, run ``git merge --no-ff <branch>``.
2. If a merge has conflicts, resolve them so the test suite still passes.
   Prefer the version on the feature branch unless the conflict is in code
   not touched by the task.
3. After all merges, run the project's typecheck and test commands.
4. If everything passes, commit the resolution with prefix ``merge:``.

# Done

<promise>COMPLETE</promise>
"""

PARALLEL_REVIEW_PROMPT = """\
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

PARALLEL_CODING_STANDARDS = """\
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

__all__ = [
    "PARALLEL_CODING_STANDARDS",
    "PARALLEL_IMPLEMENT_PROMPT",
    "PARALLEL_MERGE_PROMPT",
    "PARALLEL_PLAN_PROMPT",
    "PARALLEL_REVIEW_PROMPT",
]

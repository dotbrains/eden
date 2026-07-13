"""Static assets for the sequential-reviewer template."""

from __future__ import annotations

DOCKERFILE = """\
FROM python:3.13-slim

ARG AGENT_UID=1000
ARG AGENT_GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \\
    git gnupg \\
    && rm -rf /var/lib/apt/lists/*

{backlog_install}

RUN groupadd --gid ${{AGENT_GID}} agent \\
    && useradd --uid ${{AGENT_UID}} --gid ${{AGENT_GID}} \\
       --create-home --home-dir /home/agent --shell /bin/sh agent

WORKDIR /workspace
USER ${{AGENT_UID}}:${{AGENT_GID}}

CMD ["sleep", "infinity"]
"""


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


MAIN_PY = """\
\"\"\"Entry point for this Eden sequential-reviewer project.

Run with: python .eden/main.py
\"\"\"

import time

from eden import claude_code, create_sandbox
from eden.providers._types import BranchStrategy
from eden.sandboxes import {sandbox} as sandbox_provider

MAX_ITERATIONS = 10


if __name__ == "__main__":
    for i in range(1, MAX_ITERATIONS + 1):
        print(f"\\n=== Iteration {{i}}/{{MAX_ITERATIONS}} ===\\n")

        branch = f"eden/seq-reviewer/{{int(time.time())}}-{{i}}"

        with create_sandbox(
            sandbox=sandbox_provider.provider({image_arg}),
            branch_strategy=BranchStrategy.named(branch),
            name=f"seq-{{i}}",
        ) as sandbox:
            implement = sandbox.run(
                name="implementer",
                agent={agent_call},
                prompt_file=".eden/implement-prompt.md",
                max_iterations=20,
            )
            if not implement.commits:
                print("Implementer made no commits; skipping review.")
                continue

            print(f"\\nImplementation complete on {{implement.branch}} "
                  f"({{len(implement.commits)}} commits)")

            review = sandbox.run(
                name="reviewer",
                agent={agent_call},
                prompt_file=".eden/review-prompt.md",
                max_iterations=1,
            )
            print(f"Review complete: {{review.completion_signal}}")
"""


GITIGNORE = """\
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
"""


__all__ = [
    "CODING_STANDARDS",
    "DOCKERFILE",
    "GITIGNORE",
    "IMPLEMENT_PROMPT",
    "MAIN_PY",
    "REVIEW_PROMPT",
]

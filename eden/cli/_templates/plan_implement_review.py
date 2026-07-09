"""plan-implement-review template — three sequential agents on one sandbox.

Per task: a *planner* produces a structured plan (extracted via
``Output.string(tag="plan")``), an *implementer* receives that plan via
``prompt_args`` and commits changes, then a *reviewer* inspects the diff
and either approves or applies follow-up corrections. All three agents
share one ``Sandbox`` so the implementer and reviewer see the worktree
state the planner reasoned about.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._common import (
    GITIGNORE,
    render_agent_call,
    render_backlog_dockerfile,
    render_image_arg,
)
from eden.cli._templates._env import render_env_example

_PLAN_PROMPT = """\
# Context

## Open tasks

!`{list_tasks_command}`

## Recent eden commits (last 10)

!`git log --oneline --grep="eden:" -10`

# Task

You are a planning agent. Pick the highest-priority open task and produce a
*concrete, executable* plan — file paths, function names, test additions —
without changing any code yourself.

## Workflow

1. **Read the task** and the relevant source files / tests.
2. **Decompose** the change into 2-6 numbered steps. Each step should be a
   self-contained edit a junior engineer could execute in <15 minutes.
3. **List risks** — non-obvious dependencies, edge cases, files that must be
   touched together.

# Output

Wrap your final plan in `<plan>…</plan>` tags. Do NOT include code; the
implementer agent reads this string and writes the code. Example:

<plan>
Task: <one-line summary>

Steps:
1. <step>
2. <step>
…

Risks:
- <risk>
- <risk>

Acceptance:
- <test or behaviour that proves the change works>
</plan>

When the plan is wrapped, output the completion signal:

<promise>COMPLETE</promise>
"""


_IMPLEMENT_PROMPT = """\
# Plan from the planner agent

{{{{PLAN}}}}

# Task

You are the implementer. Execute the plan above on this branch. Stay within
the steps the planner specified — if you discover the plan is wrong, leave
a comment on the task explaining why and stop rather than improvising.

## Workflow

1. **Re-read the plan** carefully. Note the acceptance criteria.
2. **Execute** the steps in order: red/green/refactor where applicable.
3. **Verify** — run typecheck and tests; fix failures before continuing.
4. **Commit** — single git commit, `eden:` prefix, body referencing the task.
5. **Close** — `{close_task_command}`.

## Rules

- One commit per task. Do not bundle.
- Do not close the task until tests pass.
- Do not silently expand scope beyond the plan.

# Done

When the plan is implemented, tests pass, and the task is closed:

<promise>COMPLETE</promise>
"""


_REVIEW_PROMPT = """\
# Task

Review the code changes on branch `{{{{SOURCE_BRANCH}}}}` for clarity,
correctness, and consistency with the plan.

# Context

## Plan the implementer was given

{{{{PLAN}}}}

## Branch diff

!`git diff {{{{TARGET_BRANCH}}}}...{{{{SOURCE_BRANCH}}}}`

## Commits on this branch

!`git log {{{{TARGET_BRANCH}}}}..{{{{SOURCE_BRANCH}}}} --oneline`

## Coding standards

See `.eden/CODING_STANDARDS.md`.

# Process

1. Compare the diff against the plan — flag drift in either direction.
2. Look for opportunities to simplify, consolidate, or rename.
3. Check correctness — edge cases, error handling, type safety.
4. If the code is clean and matches the plan, output
   `<promise>APPROVED</promise>` and stop.
5. Otherwise, make corrections directly on this branch with a follow-up
   commit prefixed `review:`.

# Done

<promise>COMPLETE</promise>
"""


_CODING_STANDARDS = """\
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


_MAIN_PY = """\
\"\"\"Entry point for this Eden plan-implement-review project.

Run with: python .eden/main.py
\"\"\"

import time

from eden import Output, claude_code, create_sandbox
from eden.providers._types import BranchStrategy
from eden.sandboxes import {sandbox} as sandbox_provider

MAX_TASKS = 10


if __name__ == "__main__":
    for i in range(1, MAX_TASKS + 1):
        print(f"\\n=== Task {{i}}/{{MAX_TASKS}} ===\\n")

        branch = f"eden/pir/{{int(time.time())}}-{{i}}"

        with create_sandbox(
            sandbox=sandbox_provider.provider({image_arg}),
            branch_strategy=BranchStrategy.named(branch),
            name=f"pir-{{i}}",
        ) as sandbox:
            plan = sandbox.run(
                name="planner",
                agent={agent_call},
                prompt_file=".eden/plan-prompt.md",
                max_iterations=1,
                output=Output.string(tag="plan"),
            )
            if not plan.output:
                print("Planner produced no plan; skipping.")
                continue
            print(f"Plan extracted ({{len(plan.output)}} chars)")

            implement = sandbox.run(
                name="implementer",
                agent={agent_call},
                prompt_file=".eden/implement-prompt.md",
                prompt_args={{"PLAN": plan.output}},
                max_iterations=20,
            )
            if not implement.commits:
                print("Implementer made no commits; skipping review.")
                continue
            print(f"Implementation: {{len(implement.commits)}} commits on {{implement.branch}}")

            review = sandbox.run(
                name="reviewer",
                agent={agent_call},
                prompt_file=".eden/review-prompt.md",
                prompt_args={{"PLAN": plan.output}},
                max_iterations=1,
            )
            print(f"Review: {{review.completion_signal}}")
"""


def render_plan_implement_review(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the plan-implement-review files."""
    _, agent_call = render_agent_call(
        template="plan-implement-review",
        agent=agent,
        model=model,
    )
    image_arg = render_image_arg(sandbox=sandbox, image_name=image_name)
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)

    return {
        "Dockerfile": render_backlog_dockerfile(backlog),
        "plan-prompt.md": _PLAN_PROMPT.format(
            list_tasks_command=backlog.list_tasks_command,
        ),
        "implement-prompt.md": _IMPLEMENT_PROMPT.format(
            close_task_command=backlog.close_task_command,
        ),
        "review-prompt.md": _REVIEW_PROMPT,
        "CODING_STANDARDS.md": _CODING_STANDARDS,
        "main.py": _MAIN_PY.format(
            sandbox=sandbox,
            image_arg=image_arg,
            agent_call=agent_call,
        ),
        ".env.example": env_example,
        ".gitignore": GITIGNORE,
    }


__all__ = ["render_plan_implement_review"]

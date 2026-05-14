"""parallel-planner-with-review template content.

A four-phase loop that combines ``parallel-planner`` (one planner → N
parallel implementers) with ``sequential-reviewer`` (a per-branch reviewer
runs in the *same* sandbox the implementer used so it sees the working
tree directly):

- Phase 1 (plan): a single planning agent reads the backlog and emits a
  ``<plan>`` JSON block listing unblocked tasks + target branch names.
- Phase 2 (execute + review): one ``create_sandbox`` per task, run
  concurrently via ``ThreadPoolExecutor``. Each sandbox runs an
  implementer ``sandbox.run(...)`` and — if commits landed — a reviewer
  ``sandbox.run(...)`` on the same branch.
- Phase 3 (merge): a single merger agent merges the approved branches
  back into the target branch.

Adapted from upstream's parallel-planner-with-review template.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager

_DOCKERFILE = """\
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


_PLAN_PROMPT = """\
# Task

Analyse the open backlog and build a dependency graph. Pick the tasks that are
**unblocked right now** — those whose dependencies are either closed or
non-existent — and emit a JSON plan listing them.

Each task gets a unique short branch name like ``eden/pr/<task-id>``.

# Context

## Open tasks

!`{list_tasks_command}`

## Recent eden commits (last 10)

!`git log --oneline --grep="eden:" -10`

# Output format

Emit a single ``<plan>...</plan>`` block whose body is JSON:

```json
{{"tasks": [
  {{"id": "<task id>", "title": "<short title>", "branch": "eden/pr/<task id>"}}
]}}
```

If nothing is unblocked, emit an empty ``tasks`` list — the outer loop will exit.

Do not pick more tasks than make sense to run in parallel; 4-6 is usually fine.
"""


_IMPLEMENT_PROMPT = """\
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


_REVIEW_PROMPT = """\
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


_MERGE_PROMPT = """\
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
\"\"\"Entry point for this Eden parallel-planner-with-review project.

Run with: python .eden/main.py
\"\"\"

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict

from eden import (
    BranchStrategy,
    Output,
    StructuredOutputError,
    {agent_import},
    create_sandbox,
    run,
)
from eden.sandboxes import {sandbox} as sandbox_provider

MAX_ITERATIONS = 10
MAX_PARALLEL = 4


class _Task(TypedDict):
    id: str
    title: str
    branch: str


class _Plan(TypedDict):
    tasks: list[_Task]


def _validate_plan(raw: object) -> _Plan:
    assert isinstance(raw, dict), "plan must be a JSON object"
    assert isinstance(raw.get("tasks"), list), "plan.tasks must be a list"
    out: list[_Task] = []
    for t in raw["tasks"]:
        assert isinstance(t, dict), "each task must be an object"
        assert isinstance(t.get("id"), str)
        assert isinstance(t.get("title"), str)
        assert isinstance(t.get("branch"), str)
        out.append(_Task(id=t["id"], title=t["title"], branch=t["branch"]))
    return _Plan(tasks=out)


def _agent():
    return {agent_call}


def _sandbox():
    return sandbox_provider.provider({image_arg})


def _execute_and_review(task: _Task) -> _Task | None:
    \"\"\"Implement + review one task on its own sandbox/branch.

    Returns the task if implementation produced commits (so the merger
    should pick the branch up); ``None`` otherwise.
    \"\"\"
    with create_sandbox(
        sandbox=_sandbox(),
        branch_strategy=BranchStrategy.named(task["branch"]),
        name=f"pr-{{task['id']}}",
    ) as sandbox:
        implement = sandbox.run(
            name=f"impl-{{task['id']}}",
            agent=_agent(),
            prompt_file=".eden/implement-prompt.md",
            prompt_args={{
                "TASK_ID": task["id"],
                "TASK_TITLE": task["title"],
                "TASK_BRANCH": task["branch"],
            }},
            max_iterations=20,
        )
        if not implement.commits:
            print(f"  - {{task['id']}} produced no commits — skipping review")
            return None
        review = sandbox.run(
            name=f"review-{{task['id']}}",
            agent=_agent(),
            prompt_file=".eden/review-prompt.md",
            max_iterations=1,
        )
        print(f"  ✓ {{task['id']}}: implemented + reviewed ({{review.completion_signal}})")
        return task


def main() -> None:
    for i in range(1, MAX_ITERATIONS + 1):
        print(f"\\n=== Iteration {{i}}/{{MAX_ITERATIONS}} ===\\n")

        # Phase 1: plan
        try:
            plan_result = run(
                name="planner",
                agent=_agent(),
                sandbox=_sandbox(),
                prompt_file=".eden/plan-prompt.md",
                max_iterations=1,
                output=Output.object(tag="plan", schema=_validate_plan),
            )
        except StructuredOutputError as exc:
            print(f"Planner failed: {{exc}}")
            break
        plan = plan_result.output
        assert isinstance(plan, dict)
        tasks: list[_Task] = plan["tasks"]  # type: ignore[index]
        if not tasks:
            print("No unblocked tasks. Exiting.")
            break

        print(f"Planning complete. {{len(tasks)}} task(s) to run in parallel.")
        for t in tasks:
            print(f"  {{t['id']}}: {{t['title']}} -> {{t['branch']}}")

        # Phase 2: execute + review in parallel (each task on its own sandbox)
        completed: list[_Task] = []
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            futures = {{pool.submit(_execute_and_review, t): t for t in tasks}}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    print(f"  X {{t['id']}} failed: {{exc}}")
                    continue
                if result is not None:
                    completed.append(result)

        if not completed:
            print("Nothing to merge.")
            continue

        print(f"\\nExecution complete. {{len(completed)}} branch(es) ready to merge.")

        # Phase 3: merge
        run(
            name="merger",
            agent=_agent(),
            sandbox=_sandbox(),
            prompt_file=".eden/merge-prompt.md",
            prompt_args={{
                "BRANCHES": "\\n".join(f"- {{t['branch']}}" for t in completed),
                "TASKS": "\\n".join(f"- {{t['id']}}: {{t['title']}}" for t in completed),
            }},
            max_iterations=1,
        )
        print("Merge complete.")


if __name__ == "__main__":
    main()
"""


_GITIGNORE = """\
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
"""


_AGENT_IMPORT: dict[str, str] = {
    "claude-code": "claude_code",
    "codex": "codex",
    "opencode": "opencode",
    "pi": "pi",
}

_AGENT_CALL: dict[str, str] = {
    "claude-code": 'claude_code("{model}")',
    "codex": 'codex("{model}")',
    "opencode": 'opencode("{model}")',
    "pi": 'pi("{model}")',
}


_BASE_ENV: dict[str, str] = {
    "claude-code": (
        "# Anthropic API key (required for claude-code)\n# ANTHROPIC_API_KEY=sk-ant-...\n"
    ),
    "codex": "# OpenAI API key (required for codex)\n# OPENAI_API_KEY=sk-...\n",
    "opencode": "# Provider key for the model you've configured opencode to use\n",
    "pi": "# pi credentials\n",
}


def render_parallel_planner_with_review(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the parallel-planner-with-review template."""
    if agent not in _AGENT_IMPORT:
        raise ValueError(f"unsupported agent for parallel-planner-with-review: {agent!r}")
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = (
        "# Copy this file to .env and fill in the values your agent needs.\n\n"
        f"{_BASE_ENV.get(agent, '')}"
    )
    if backlog.env_example_lines:
        env_example += "\n" + backlog.env_example_lines

    view_subbed = backlog.view_task_command.replace("<ID>", "{{TASK_ID}}")

    agent_import = _AGENT_IMPORT[agent]
    agent_call = _AGENT_CALL[agent].format(model=model)
    return {
        "Dockerfile": _DOCKERFILE.format(backlog_install=backlog.dockerfile_install),
        "plan-prompt.md": _PLAN_PROMPT.format(
            list_tasks_command=backlog.list_tasks_command,
        ),
        "implement-prompt.md": _IMPLEMENT_PROMPT.format(
            view_task_command_subbed=view_subbed,
            close_task_command=backlog.close_task_command,
        ),
        "review-prompt.md": _REVIEW_PROMPT,
        "merge-prompt.md": _MERGE_PROMPT,
        "CODING_STANDARDS.md": _CODING_STANDARDS,
        "main.py": _MAIN_PY.format(
            sandbox=sandbox,
            image_arg=image_arg,
            agent_import=agent_import,
            agent_call=agent_call,
        ),
        ".env.example": env_example,
        ".gitignore": _GITIGNORE,
    }


__all__ = ["render_parallel_planner_with_review"]

"""parallel-planner template content.

A three-phase loop:
- Phase 1 (plan): a single planning agent reads the backlog, builds a
  dependency graph, and emits a ``<plan>`` JSON block listing unblocked
  tasks with their target branch names. Eden's ``Output.object`` extracts
  and validates the JSON.
- Phase 2 (execute): one implementer agent per task, run concurrently via
  ``concurrent.futures.ThreadPoolExecutor``. Each runs in its own sandbox
  on its own named branch.
- Phase 3 (merge): a single merger agent merges the branches that produced
  commits back into the target branch.

Adapted from sandcastle's parallel-planner template.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._env import render_env_example

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

Each task gets a unique short branch name like ``eden/p/<task-id>``.

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
  {{"id": "<task id>", "title": "<short title>", "branch": "eden/p/<task id>"}}
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


_MAIN_PY = """\
\"\"\"Entry point for this Eden parallel-planner project.

Run with: python .eden/main.py
\"\"\"

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict

from eden import (
    BranchStrategy,
    Output,
    StructuredOutputError,
    {agent_import},
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


def _execute_one(task: _Task):
    \"\"\"Run an implementer agent for one task, on its own branch.\"\"\"
    return run(
        name=f"impl-{{task['id']}}",
        agent=_agent(),
        sandbox=_sandbox(),
        branch_strategy=BranchStrategy.named(task["branch"]),
        prompt_file=".eden/implement-prompt.md",
        prompt_args={{
            "TASK_ID": task["id"],
            "TASK_TITLE": task["title"],
            "TASK_BRANCH": task["branch"],
        }},
        max_iterations=20,
    )


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

        # Phase 2: execute in parallel
        completed: list[_Task] = []
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            futures = {{pool.submit(_execute_one, t): t for t in tasks}}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    print(f"  X {{t['id']}} failed: {{exc}}")
                    continue
                if result.commits:
                    completed.append(t)
                else:
                    print(f"  - {{t['id']}} produced no commits")

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


def render_parallel_planner(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the parallel-planner template."""
    if agent not in _AGENT_IMPORT:
        raise ValueError(f"unsupported agent for parallel-planner: {agent!r}")
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)

    # Replace <ID> in view_task_command with the runtime substitution placeholder
    # so each implementer's prompt expands the right task body.
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
        "merge-prompt.md": _MERGE_PROMPT,
        "main.py": _MAIN_PY.format(
            sandbox=sandbox,
            image_arg=image_arg,
            agent_import=agent_import,
            agent_call=agent_call,
        ),
        ".env.example": env_example,
        ".gitignore": _GITIGNORE,
    }


__all__ = ["render_parallel_planner"]

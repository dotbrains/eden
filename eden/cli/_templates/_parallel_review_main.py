"""Generated main.py body for the parallel planner review template."""

from __future__ import annotations

MAIN_PY = """\
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

__all__ = ["MAIN_PY"]

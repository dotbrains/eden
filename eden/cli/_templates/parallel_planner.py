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
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._common import (
    GITIGNORE,
    render_agent_call,
    render_backlog_dockerfile,
    render_image_arg,
    render_task_view_command,
)
from eden.cli._templates._env import render_env_example
from eden.cli._templates._parallel_planner.main_py import MAIN_PY
from eden.cli._templates._parallel_prompts import (
    PARALLEL_IMPLEMENT_PROMPT,
    PARALLEL_MERGE_PROMPT,
    PARALLEL_PLAN_PROMPT,
)


def render_parallel_planner(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the parallel-planner template."""
    agent_import, agent_call = render_agent_call(
        template="parallel-planner",
        agent=agent,
        model=model,
    )
    image_arg = render_image_arg(sandbox=sandbox, image_name=image_name)
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)
    view_subbed = render_task_view_command(backlog)
    return {
        "Dockerfile": render_backlog_dockerfile(backlog, agent=agent),
        "plan-prompt.md": PARALLEL_PLAN_PROMPT.format(
            branch_prefix="eden/p",
            list_tasks_command=backlog.list_tasks_command,
        ),
        "implement-prompt.md": PARALLEL_IMPLEMENT_PROMPT.format(
            view_task_command_subbed=view_subbed,
            close_task_command=backlog.close_task_command,
        ),
        "merge-prompt.md": PARALLEL_MERGE_PROMPT,
        "main.py": MAIN_PY.format(
            sandbox=sandbox,
            image_arg=image_arg,
            agent_import=agent_import,
            agent_call=agent_call,
        ),
        ".env.example": env_example,
        ".gitignore": GITIGNORE,
    }


__all__ = ["render_parallel_planner"]

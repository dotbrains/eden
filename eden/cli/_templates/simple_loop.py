"""simple-loop template content for ``eden init --template simple-loop``.

The simple-loop template is a runnable Python entry point that calls
``eden.run()`` with a backlog-aware prompt. The prompt template embeds a
``!`<list-tasks-command>`` shell expression so the list of open tasks is
expanded inside the sandbox at iteration time, giving the agent fresh context
on every loop turn.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._common import render_agent_call
from eden.cli._templates._env import render_env_example
from eden.cli._templates._simple_loop.prompt import PROMPT_MD

_DOCKERFILE = """\
FROM python:3.13-slim

# Align in-container UID/GID with the host so files written into the
# bind-mounted worktree land with the host user as owner. Override at build
# time: --build-arg AGENT_UID=$(id -u) --build-arg AGENT_GID=$(id -g)
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


_MAIN_PY = """\
\"\"\"Entry point for this Eden simple-loop project.

Run with: python .eden/main.py
\"\"\"

from eden import run, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider


if __name__ == "__main__":
    result = run(
        name="worker",
        agent={agent_call},
        sandbox=sandbox_provider.provider({image_arg}),
        prompt_file=".eden/prompt.md",
        max_iterations=3,
    )
    print(f"Completion: {{result.completion_signal}}")
    print(f"Iterations: {{len(result.iterations)}}")
    print(f"Branch:     {{result.branch}}")
"""


_GITIGNORE = """\
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
"""


def render_simple_loop(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the simple-loop template files."""
    agent_import, agent_call = render_agent_call(
        template="simple-loop",
        agent=agent,
        model=model,
    )
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)

    return {
        "Dockerfile": _DOCKERFILE.format(backlog_install=backlog.dockerfile_install),
        "prompt.md": PROMPT_MD.format(
            list_tasks_command=backlog.list_tasks_command,
            view_task_command=backlog.view_task_command,
            close_task_command=backlog.close_task_command,
        ),
        "main.py": _MAIN_PY.format(
            agent_import=agent_import,
            agent_call=agent_call,
            sandbox=sandbox,
            image_arg=image_arg,
        ),
        ".env.example": env_example,
        ".gitignore": _GITIGNORE,
    }


def render_simple_loop_prompt(backlog: BacklogManager) -> str:
    """Return the simple-loop prompt as a string, without scaffolding files.

    Used by ``eden run --template simple-loop`` to feed the same prompt into
    an in-process ``eden.run()`` call. Mirrors the ``prompt.md`` produced by
    :func:`render_simple_loop`, so behaviour stays identical between the
    scaffolded and in-process forms.
    """
    return PROMPT_MD.format(
        list_tasks_command=backlog.list_tasks_command,
        view_task_command=backlog.view_task_command,
        close_task_command=backlog.close_task_command,
    )


__all__ = ["render_simple_loop", "render_simple_loop_prompt"]

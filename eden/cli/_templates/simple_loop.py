"""simple-loop template content for ``eden init --template simple-loop``.

The simple-loop template is a runnable Python entry point that calls
``eden.run()`` with a backlog-aware prompt. The prompt template embeds a
``!`<list-tasks-command>`` shell expression so the list of open tasks is
expanded inside the sandbox at iteration time, giving the agent fresh context
on every loop turn. The rendered files mirror sandcastle's simple-loop layout.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager

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


_PROMPT_MD = """\
# Context

## Open tasks

!`{list_tasks_command}`

## Recent eden commits (last 10)

!`git log --oneline --grep="eden:" -10`

# Task

You are an autonomous coding agent working through tasks one at a time.

## Priority order

Work on tasks in this order:

1. **Bug fixes** — broken behaviour affecting users
2. **Tracer bullets** — thin end-to-end slices that prove an approach works
3. **Polish** — error messages, UX, docs
4. **Refactors** — internal cleanups with no user-visible change

Pick the highest-priority open task that isn't blocked.

## Workflow

1. **Explore** — read the task carefully. Read the relevant source files and
   tests before writing any code. Use `{view_task_command}` if you need
   the full task body.
2. **Plan** — decide what to change and why. Keep the change small.
3. **Execute** — follow red/green/refactor: failing test first, then code.
4. **Verify** — run the project's test/typecheck commands before committing.
5. **Commit** — single git commit with an `eden:` prefix and a clear summary.
6. **Close** — mark the task done with `{close_task_command}`.

## Rules

- One task per iteration. Do not bundle multiple tasks.
- Do not close a task until the fix is committed and tests pass.
- If you are blocked, leave a comment on the task and stop — do not close it.

# Done

When all actionable tasks are complete (or all remaining are blocked), output
the completion signal:

<promise>COMPLETE</promise>
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


def render_simple_loop(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the simple-loop template files."""
    agent_import = _AGENT_IMPORT[agent]
    agent_call = _AGENT_CALL[agent].format(model=model)
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = (
        "# Copy this file to .env and fill in the values your agent needs.\n\n"
        f"{_BASE_ENV.get(agent, '')}"
    )
    if backlog.env_example_lines:
        env_example += "\n" + backlog.env_example_lines

    return {
        "Dockerfile": _DOCKERFILE.format(backlog_install=backlog.dockerfile_install),
        "prompt.md": _PROMPT_MD.format(
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
    return _PROMPT_MD.format(
        list_tasks_command=backlog.list_tasks_command,
        view_task_command=backlog.view_task_command,
        close_task_command=backlog.close_task_command,
    )


__all__ = ["render_simple_loop", "render_simple_loop_prompt"]

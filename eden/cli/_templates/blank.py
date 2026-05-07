"""Blank-template content for `eden init`."""

from __future__ import annotations

BLANK_DOCKERFILE = """\
FROM python:3.13-slim

# Align in-container UID/GID with the host so files written into the
# bind-mounted worktree land with the host user as owner. Override at build
# time: --build-arg AGENT_UID=$(id -u) --build-arg AGENT_GID=$(id -g)
ARG AGENT_UID=1000
ARG AGENT_GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${AGENT_GID} agent \\
    && useradd --uid ${AGENT_UID} --gid ${AGENT_GID} \\
       --create-home --home-dir /home/agent --shell /bin/sh agent

WORKDIR /workspace
USER ${AGENT_UID}:${AGENT_GID}

CMD ["sleep", "infinity"]
"""

BLANK_PROMPT_MD = """\
# Eden Prompt

Replace this content with your task description. The agent receives this
file's contents as the prompt at run time.

`{{SOURCE_BRANCH}}` and `{{TARGET_BRANCH}}` substitutions, and `` !`cmd` ``
shell-block expansion, are available — see the eden docs.
"""

BLANK_MAIN_PY = """\
\"\"\"Entry point for this Eden project.

Run with: python .eden/main.py
\"\"\"

from eden import run, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider


if __name__ == "__main__":
    result = run(
        agent={agent_call},
        sandbox=sandbox_provider.provider({image_arg}),
        prompt_file=".eden/prompt.md",
        max_iterations=5,
    )
    print(f"Completion: {{result.completion_signal}}")
"""

BLANK_ENV_EXAMPLE = """\
# Copy this file to .env and fill in the values your agent needs.

# Anthropic API key (required for claude-code)
# ANTHROPIC_API_KEY=sk-ant-...

# OpenAI API key (required for codex)
# OPENAI_API_KEY=sk-...
"""

BLANK_GITIGNORE = """\
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


def render_blank(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the 5 .eden/ files."""
    agent_import = _AGENT_IMPORT[agent]
    agent_call = _AGENT_CALL[agent].format(model=model)
    if sandbox in ("docker", "podman"):
        image_arg = f'image="{image_name}"'
    else:
        image_arg = ""
    return {
        "Dockerfile": BLANK_DOCKERFILE,
        "prompt.md": BLANK_PROMPT_MD,
        "main.py": BLANK_MAIN_PY.format(
            agent_import=agent_import,
            agent_call=agent_call,
            sandbox=sandbox,
            image_arg=image_arg,
        ),
        ".env.example": BLANK_ENV_EXAMPLE,
        ".gitignore": BLANK_GITIGNORE,
    }


__all__ = ["render_blank"]

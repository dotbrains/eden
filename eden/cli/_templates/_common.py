"""Shared scaffold fragments for Eden init templates."""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager

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

GITIGNORE = """\
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
"""

AGENT_IMPORT: dict[str, str] = {
    "claude-code": "claude_code",
    "codex": "codex",
    "opencode": "opencode",
    "pi": "pi",
}

AGENT_CALL: dict[str, str] = {
    "claude-code": 'claude_code("{model}")',
    "codex": 'codex("{model}")',
    "opencode": 'opencode("{model}")',
    "pi": 'pi("{model}")',
}


def render_agent_call(*, template: str, agent: str, model: str) -> tuple[str, str]:
    if agent not in AGENT_IMPORT:
        raise ValueError(f"unsupported agent for {template}: {agent!r}")
    return AGENT_IMPORT[agent], AGENT_CALL[agent].format(model=model)


def render_image_arg(*, sandbox: str, image_name: str) -> str:
    return f'image="{image_name}"' if sandbox in ("docker", "podman") else ""


def render_backlog_dockerfile(backlog: BacklogManager) -> str:
    return DOCKERFILE.format(backlog_install=backlog.dockerfile_install)


def render_task_view_command(backlog: BacklogManager) -> str:
    return backlog.view_task_command.replace("<ID>", "{{TASK_ID}}")


__all__ = [
    "AGENT_CALL",
    "AGENT_IMPORT",
    "DOCKERFILE",
    "GITIGNORE",
    "render_agent_call",
    "render_backlog_dockerfile",
    "render_image_arg",
    "render_task_view_command",
]

"""Backlog-manager registry — supplies the commands templates inject.

Each entry describes one backlog manager (issue tracker) and the commands a
template uses to list, view, and close tasks. Templates that ship with eden
substitute these into rendered ``prompt.md`` and ``main.py`` files at
``eden init`` time so users can switch tooling without changing the
template authoring contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BacklogName = Literal["github", "beads"]


@dataclass(frozen=True)
class BacklogManager:
    name: BacklogName
    label: str
    list_tasks_command: str
    view_task_command: str
    close_task_command: str
    dockerfile_install: str
    env_example_lines: str


_GH_KEYRING = "/usr/share/keyrings/githubcli-archive-keyring.gpg"
_GH_REPO_LINE = (
    f"deb [arch=$(dpkg --print-architecture) signed-by={_GH_KEYRING}] "
    "https://cli.github.com/packages stable main"
)
_GITHUB_DOCKERFILE = f"""\
# Install GitHub CLI for backlog management
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \\
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \\
       | gpg --dearmor -o {_GH_KEYRING} \\
    && echo "{_GH_REPO_LINE}" \\
       > /etc/apt/sources.list.d/github-cli.list \\
    && apt-get update && apt-get install -y gh \\
    && rm -rf /var/lib/apt/lists/*"""


_BEADS_DOCKERFILE = """\
# Install Beads (bd) CLI for backlog management
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \\
    && curl -fsSL https://github.com/steveyegge/beads/releases/latest/download/bd-linux-amd64 \\
       -o /usr/local/bin/bd \\
    && chmod +x /usr/local/bin/bd \\
    && rm -rf /var/lib/apt/lists/*"""


_REGISTRY: tuple[BacklogManager, ...] = (
    BacklogManager(
        name="github",
        label="GitHub Issues",
        list_tasks_command=(
            "gh issue list --state open --label eden "
            "--json number,title,body,labels,comments "
            "--jq '[.[] | {id: .number, title, body, "
            "labels: [.labels[].name], comments: [.comments[].body]}]'"
        ),
        view_task_command="gh issue view <ID>",
        close_task_command='gh issue close <ID> --comment "Completed by Eden"',
        dockerfile_install=_GITHUB_DOCKERFILE,
        env_example_lines="# GitHub personal access token\n# GH_TOKEN=\n",
    ),
    BacklogManager(
        name="beads",
        label="Beads",
        list_tasks_command="bd ready --json",
        view_task_command="bd show <ID>",
        close_task_command='bd close <ID> "Completed by Eden"',
        dockerfile_install=_BEADS_DOCKERFILE,
        env_example_lines="",
    ),
)


def get_backlog_manager(name: BacklogName) -> BacklogManager:
    """Return the registry entry matching ``name``.

    Raises ``KeyError`` for an unknown name — callers should validate against
    :func:`list_backlog_managers` first when accepting user input.
    """
    for entry in _REGISTRY:
        if entry.name == name:
            return entry
    raise KeyError(f"unknown backlog manager: {name!r}")


def list_backlog_managers() -> tuple[BacklogManager, ...]:
    return _REGISTRY


__all__ = [
    "BacklogManager",
    "BacklogName",
    "get_backlog_manager",
    "list_backlog_managers",
]

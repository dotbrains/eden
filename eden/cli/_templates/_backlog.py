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

from eden.cli._templates._backlog_installs import (
    BEADS_DOCKERFILE,
    GITHUB_DOCKERFILE,
    JIRA_DOCKERFILE,
    LINEAR_DOCKERFILE,
)

BacklogName = Literal["github", "beads", "linear", "jira", "custom"]


@dataclass(frozen=True)
class BacklogManager:
    name: BacklogName
    label: str
    list_tasks_command: str
    view_task_command: str
    close_task_command: str
    dockerfile_install: str
    env_example_lines: str


_REGISTRY: tuple[BacklogManager, ...] = (
    BacklogManager(
        name="github",
        label="GitHub Issues",
        list_tasks_command=(
            # --limit 100 ensures the parallel-planner sees the full dependency
            # graph; gh defaults to 30 results and silently truncates.
            "gh issue list --state open --label eden --limit 100 "
            "--json number,title,body,labels,comments "
            "--jq '[.[] | {id: .number, title, body, "
            "labels: [.labels[].name], comments: [.comments[].body]}]'"
        ),
        view_task_command="gh issue view <ID>",
        close_task_command='gh issue close <ID> --comment "Completed by Eden"',
        dockerfile_install=GITHUB_DOCKERFILE,
        env_example_lines=(
            "# GitHub personal access token. Create at\n"
            "# https://github.com/settings/personal-access-tokens with these scopes:\n"
            "#   - Repository: Issues (Read and write), Metadata (Read)\n"
            "# GH_TOKEN=\n"
        ),
    ),
    BacklogManager(
        name="beads",
        label="Beads",
        list_tasks_command="bd ready --json",
        view_task_command="bd show <ID>",
        # bd expects --reason=<text> as a flag, not a positional arg; the
        # positional form silently fails on current beads releases.
        close_task_command='bd close <ID> --reason="Completed by Eden"',
        dockerfile_install=BEADS_DOCKERFILE,
        env_example_lines="",
    ),
    BacklogManager(
        name="linear",
        label="Linear",
        list_tasks_command="linear-list",
        view_task_command="linear-view <ID>",
        close_task_command="linear-close <ID>",
        dockerfile_install=LINEAR_DOCKERFILE,
        env_example_lines=(
            "# Linear personal API key (Settings > Account > Security & access > "
            "Personal API keys)\n# LINEAR_API_KEY=lin_api_...\n"
        ),
    ),
    BacklogManager(
        name="jira",
        label="Jira",
        list_tasks_command=(
            'jira issue list -q "assignee = currentUser() AND '
            'status not in (Done, Closed, Resolved)" --plain '
            "--columns key,summary,status"
        ),
        view_task_command="jira issue view <ID>",
        close_task_command='jira issue move <ID> "Done"',
        dockerfile_install=JIRA_DOCKERFILE,
        env_example_lines=(
            "# Jira authentication — see https://github.com/ankitpokhrel/jira-cli\n"
            "# JIRA_API_TOKEN=\n# JIRA_AUTH_TYPE=basic\n"
            "# Set JIRA_AUTH_TYPE=bearer for Jira Server / Data Center.\n"
            "# Run `jira init` once to write ~/.config/.jira/.config.yml.\n"
        ),
    ),
    # The "custom" entry is intentionally broken-until-configured: every
    # command is a `<TODO ...>` marker the agent is expected to replace on
    # first run after reading the scaffolded README. Pick this when your
    # tracker isn't one of the four shipped above (e.g. Shortcut, Asana,
    # in-house REST). The agent's first task is to wire these in.
    BacklogManager(
        name="custom",
        label="Custom (agent wires it up)",
        list_tasks_command=(
            "<TODO: replace with a shell one-liner that prints open tasks as JSON "
            '[{"id": "...", "title": "...", "body": "...", "status": "..."}]>'
        ),
        view_task_command=("<TODO: replace with the command that prints details for issue <ID>>"),
        close_task_command=("<TODO: replace with the command that closes issue <ID>>"),
        dockerfile_install=(
            "# <TODO: install your tracker's CLI here. Examples: shortcut-cli,\n"
            "# asana-cli, a curl-driven helper script for an in-house REST API.>\n"
            "# RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
            "#     <your-cli-package> && rm -rf /var/lib/apt/lists/*"
        ),
        env_example_lines=(
            "# <TODO: list any credentials your custom tracker needs and uncomment.>\n"
            "# YOUR_TRACKER_TOKEN=\n"
        ),
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

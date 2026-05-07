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

BacklogName = Literal["github", "beads", "linear", "jira"]


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


# Linear has no first-party CLI. We install ``curl`` + ``jq`` and bake three
# small helper scripts (``linear-list``, ``linear-view``, ``linear-close``)
# that wrap the GraphQL API. The prompt-side commands stay one-liners.
_LINEAR_DOCKERFILE = """\
# Install curl + jq + helper scripts for Linear backlog management.
# Linear has no first-party CLI, so the helpers wrap the GraphQL API.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates jq \\
    && rm -rf /var/lib/apt/lists/*

RUN cat > /usr/local/bin/linear-list <<'EOF' \\
 && chmod +x /usr/local/bin/linear-list
#!/bin/sh
# List unblocked open issues assigned to the current user as JSON
# [{id, title, body, status}]. Requires LINEAR_API_KEY in env.
set -e
QUERY='query { viewer { assignedIssues(filter: {state: {type: {nin: ["completed","canceled"]}}}) { nodes { identifier title description state { name } } } } }'
curl -fsSL -H "Authorization: $LINEAR_API_KEY" -H "Content-Type: application/json" \\
    -d "$(jq -nc --arg q "$QUERY" '{query: $q}')" \\
    https://api.linear.app/graphql \\
  | jq '[.data.viewer.assignedIssues.nodes[] | {id: .identifier, title, body: .description, status: .state.name}]'
EOF

RUN cat > /usr/local/bin/linear-view <<'EOF' \\
 && chmod +x /usr/local/bin/linear-view
#!/bin/sh
# Show one Linear issue by identifier (e.g. ABC-123). Requires LINEAR_API_KEY.
set -e
[ -z "$1" ] && { echo "usage: linear-view <ID>" >&2; exit 2; }
QUERY='query($id:String!){ issue(id:$id){ identifier title description state{name} team{key} } }'
curl -fsSL -H "Authorization: $LINEAR_API_KEY" -H "Content-Type: application/json" \\
    -d "$(jq -nc --arg q "$QUERY" --arg id "$1" '{query: $q, variables: {id: $id}}')" \\
    https://api.linear.app/graphql \\
  | jq .data.issue
EOF

RUN cat > /usr/local/bin/linear-close <<'EOF' \\
 && chmod +x /usr/local/bin/linear-close
#!/bin/sh
# Transition a Linear issue to the team's first 'completed'-type state.
# Requires LINEAR_API_KEY in env.
set -e
[ -z "$1" ] && { echo "usage: linear-close <ID>" >&2; exit 2; }
ID="$1"
TEAM_QUERY='query($id:String!){ issue(id:$id){ team{ id } } }'
TEAM_ID=$(curl -fsSL -H "Authorization: $LINEAR_API_KEY" -H "Content-Type: application/json" \\
    -d "$(jq -nc --arg q "$TEAM_QUERY" --arg id "$ID" '{query: $q, variables: {id: $id}}')" \\
    https://api.linear.app/graphql | jq -r .data.issue.team.id)
STATE_QUERY='query($team:String!){ workflowStates(filter:{team:{id:{eq:$team}},type:{eq:"completed"}}){ nodes{ id } } }'
STATE_ID=$(curl -fsSL -H "Authorization: $LINEAR_API_KEY" -H "Content-Type: application/json" \\
    -d "$(jq -nc --arg q "$STATE_QUERY" --arg team "$TEAM_ID" '{query: $q, variables: {team: $team}}')" \\
    https://api.linear.app/graphql | jq -r .data.workflowStates.nodes[0].id)
MUTATION='mutation($id:String!,$state:String!){ issueUpdate(id:$id, input:{stateId:$state}){ success } }'
curl -fsSL -H "Authorization: $LINEAR_API_KEY" -H "Content-Type: application/json" \\
    -d "$(jq -nc --arg q "$MUTATION" --arg id "$ID" --arg state "$STATE_ID" '{query: $q, variables: {id: $id, state: $state}}')" \\
    https://api.linear.app/graphql | jq -e .data.issueUpdate.success > /dev/null
EOF
"""


# jira-cli (ankitpokhrel/jira-cli) is the most-maintained third-party Jira CLI.
# Eden installs the linux-amd64 release tarball at image-build time. Users on
# arm64 should adjust the asset suffix — upstream takes the same shortcut.
_JIRA_DOCKERFILE = """\
# Install jira-cli (ankitpokhrel/jira-cli) for backlog management.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \\
    && rm -rf /var/lib/apt/lists/* \\
    && JIRA_VERSION="$(curl -fsSL -o /dev/null -w '%{redirect_url}' \\
         https://github.com/ankitpokhrel/jira-cli/releases/latest \\
         | grep -oE 'v[0-9]+\\.[0-9]+\\.[0-9]+' | sed 's/^v//')" \\
    && curl -fsSL "https://github.com/ankitpokhrel/jira-cli/releases/download/v${JIRA_VERSION}/jira_${JIRA_VERSION}_linux_x86_64.tar.gz" \\
       | tar -xz -C /tmp \\
    && find /tmp -name jira -type f -executable -exec mv {} /usr/local/bin/jira \\; \\
    && chmod +x /usr/local/bin/jira"""


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
    BacklogManager(
        name="linear",
        label="Linear",
        list_tasks_command="linear-list",
        view_task_command="linear-view <ID>",
        close_task_command="linear-close <ID>",
        dockerfile_install=_LINEAR_DOCKERFILE,
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
        dockerfile_install=_JIRA_DOCKERFILE,
        env_example_lines=(
            "# Jira authentication — see https://github.com/ankitpokhrel/jira-cli\n"
            "# JIRA_API_TOKEN=\n# JIRA_AUTH_TYPE=basic\n"
            "# Set JIRA_AUTH_TYPE=bearer for Jira Server / Data Center.\n"
            "# Run `jira init` once to write ~/.config/.jira/.config.yml.\n"
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

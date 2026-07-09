"""Backlog-manager Dockerfile install snippets."""

# ruff: noqa: E501

from __future__ import annotations

_GH_KEYRING = "/usr/share/keyrings/githubcli-archive-keyring.gpg"
_GH_REPO_LINE = (
    f"deb [arch=$(dpkg --print-architecture) signed-by={_GH_KEYRING}] "
    "https://cli.github.com/packages stable main"
)
GITHUB_DOCKERFILE = f"""\
# Install GitHub CLI for backlog management
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \\
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \\
       | gpg --dearmor -o {_GH_KEYRING} \\
    && echo "{_GH_REPO_LINE}" \\
       > /etc/apt/sources.list.d/github-cli.list \\
    && apt-get update && apt-get install -y gh \\
    && rm -rf /var/lib/apt/lists/*"""


BEADS_DOCKERFILE = """\
# Install Beads (bd) CLI for backlog management. Detect host arch so the
# image builds on both amd64 and arm64 Linux hosts.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \\
    && ARCH="$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')" \\
    && curl -fsSL "https://github.com/steveyegge/beads/releases/latest/download/bd-linux-${ARCH}" \\
       -o /usr/local/bin/bd \\
    && chmod +x /usr/local/bin/bd \\
    && rm -rf /var/lib/apt/lists/*"""


# Linear has no first-party CLI. We install ``curl`` + ``jq`` and bake three
# small helper scripts (``linear-list``, ``linear-view``, ``linear-close``)
# that wrap the GraphQL API. The prompt-side commands stay one-liners.
LINEAR_DOCKERFILE = """\
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
# arm64 should adjust the asset suffix.
JIRA_DOCKERFILE = """\
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


__all__ = [
    "BEADS_DOCKERFILE",
    "GITHUB_DOCKERFILE",
    "JIRA_DOCKERFILE",
    "LINEAR_DOCKERFILE",
]

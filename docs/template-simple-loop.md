# Simple-loop template

Detailed reference for the `simple-loop` scaffold. See [Templates](templates.md)
for the other project templates.

## `simple-loop`

A runnable worker that picks open tasks from a backlog manager and processes
them one per iteration.

```bash
# GitHub Issues backed (default)
eden init --template simple-loop --sandbox docker --agent claude-code --backlog github --yes

# Other backlog managers
eden init --template simple-loop --backlog beads --yes
eden init --template simple-loop --backlog linear --yes
eden init --template simple-loop --backlog jira --yes
```

## `--backlog` flag

`--backlog` selects which backlog manager the rendered `prompt.md` expects.
Eden ships four:

| Name     | List command                                                                                | View command           | Close command                                            |
|----------|---------------------------------------------------------------------------------------------|------------------------|----------------------------------------------------------|
| `github` | `gh issue list --state open --label eden --json ... --jq '[.[] \| {id, title, body, ...}]'` | `gh issue view <ID>`   | `gh issue close <ID> --comment "Completed by Eden"`      |
| `beads`  | `bd ready --json`                                                                            | `bd show <ID>`         | `bd close <ID> --reason="Completed by Eden"`             |
| `linear` | `linear-list` (helper script — wraps the Linear GraphQL API, returns JSON)                  | `linear-view <ID>`     | `linear-close <ID>` (transitions to the team's "completed" state) |
| `jira`   | `jira issue list -q "assignee = currentUser() AND status not in (Done, Closed, Resolved)"` | `jira issue view <ID>` | `jira issue move <ID> "Done"`                            |

The selection wires three things:

1. The list-tasks command goes inside a `` !`...` `` shell block in `prompt.md` so the open-task list is expanded fresh each iteration.
2. The Dockerfile gains the install steps for the chosen tooling: `gh` from the GitHub apt repo, `bd` from the Beads release page, `curl + jq + linear-* helper scripts` baked into the image, or `jira-cli` from `ankitpokhrel/jira-cli`'s GitHub releases.
3. `.env.example` gains any backlog-manager-specific keys (`GH_TOKEN` for `github`, `LINEAR_API_KEY` for `linear`, `JIRA_API_TOKEN` plus auth-type for `jira`; nothing for `beads`).

## Files produced

The same five filenames as `blank` (`Dockerfile`, `prompt.md`, `main.py`,
`.env.example`, `.gitignore`) but with simple-loop content:

- **`Dockerfile`** — `python:3.13-slim` with `git`, Node/npm, the selected agent CLI, the chosen backlog CLI, and a non-root `agent` user (`AGENT_UID`/`AGENT_GID` build args default 1000; eden init's "Next steps" command auto-aligns to your host UID/GID and tolerates IDs already present in the base image).
- **`prompt.md`** — RALPH-style autonomous-agent instructions: explore → plan → execute → verify → commit → close. The "Open tasks" section embeds the list-tasks command. The agent emits `<promise>COMPLETE</promise>` when the queue is empty.
- **`main.py`** — calls `eden.run(name="worker", agent=..., sandbox=..., prompt_file=".eden/prompt.md", max_iterations=3)`.
- **`.env.example`** — agent API keys plus backlog manager env vars.
- **`.gitignore`** — same as `blank`.

## Customizing

The template is a starting point — edit `prompt.md` to change the agent's
working rules, bump `max_iterations` in `main.py` for longer sessions, or swap
in a different sandbox.

Read source: `eden/cli/_templates/simple_loop.py`,
`eden/cli/_templates/_backlog.py`.

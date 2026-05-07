# Templates

`eden init` scaffolds a project from a template. Two templates ship today: `blank` (minimal) and `simple-loop` (an iteration-driven worker that picks tasks from a backlog manager).

---

## `blank`

The minimal scaffold: just the moving parts wired up. Edit `.eden/prompt.md`, then run `python .eden/main.py`.

```bash
eden init --template blank --sandbox docker --agent claude-code --yes
```

### Files produced

The blank template writes five files into `.eden/`. The exact contents of `main.py` depend on `--sandbox`, `--agent`, `--model`, and `--image-name`; the other four files are static.

#### `.eden/Dockerfile`

Python 3.13-slim base with `git` installed and `/workspace` as the working directory:

```dockerfile
FROM python:3.13-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
```

#### `.eden/prompt.md`

A placeholder describing the prompt template's substitution rules. Replace the body with your actual task description; the agent receives this file's contents as the prompt at run time.

`{{SOURCE_BRANCH}}` and `{{TARGET_BRANCH}}` substitutions, and `` !`cmd` `` shell-block expansion, are available — see [prompts.md](prompts.md).

#### `.eden/main.py`

A runnable entry point that imports the chosen agent factory and sandbox provider, then calls `eden.run(...)` with `prompt_file=".eden/prompt.md"` and `max_iterations=5`. The rendered file picks the agent factory and sandbox module based on the flags passed to `eden init`. For `--sandbox docker --agent claude-code --model claude-opus-4-7 --image-name eden:demo`, you get:

```python
"""Entry point for this Eden project.

Run with: python .eden/main.py
"""

from eden import run, claude_code
from eden.sandboxes import docker as sandbox_provider


if __name__ == "__main__":
    result = run(
        agent=claude_code("claude-opus-4-7"),
        sandbox=sandbox_provider.provider(image="eden:demo"),
        prompt_file=".eden/prompt.md",
        max_iterations=5,
    )
    print(f"Completion: {result.completion_signal}")
```

Other agents substitute their factory name (`codex`, `opencode`, `pi`); `--sandbox podman` substitutes the corresponding module.

#### `.eden/.env.example`

A starter `.env` template with commented-out keys for the agent CLIs Eden orchestrates:

```bash
# Copy this file to .env and fill in the values your agent needs.

# Anthropic API key (required for claude-code)
# ANTHROPIC_API_KEY=sk-ant-...

# OpenAI API key (required for codex)
# OPENAI_API_KEY=sk-...
```

These keys are read by the agent CLIs themselves, not by Eden. See [configuration.md](configuration.md) for the env vars Eden itself reads.

#### `.eden/.gitignore`

Excludes runtime artifacts (so committed scaffolds stay clean):

```gitignore
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
```

### Customizing

`.eden/main.py` is a plain Python file — edit it to add [lifecycle hooks](python-api.md#lifecycle-hooks), change `max_iterations`, swap providers, plug in your own [`Logging`](python-api.md#configuration-types) sink, or wrap `eden.run(...)` in your own logic.

Read source: `eden/cli/_templates/blank.py`.

---

## `simple-loop`

A runnable worker that picks open tasks from a backlog manager (GitHub Issues or Beads) and processes them one per iteration. Adapted from sandcastle's `simple-loop` template.

```bash
# GitHub Issues backed (default)
eden init --template simple-loop --sandbox docker --agent claude-code --backlog github --yes

# Beads backed
eden init --template simple-loop --sandbox docker --agent claude-code --backlog beads --yes
```

### `--backlog` flag

`--backlog` selects which backlog manager the rendered `prompt.md` expects. Eden ships two:

| Name     | List command                                                                                       | View command           | Close command                                            |
|----------|----------------------------------------------------------------------------------------------------|------------------------|----------------------------------------------------------|
| `github` | `gh issue list --state open --label eden --json number,title,body,labels,comments --jq '...'`     | `gh issue view <ID>`   | `gh issue close <ID> --comment "Completed by Eden"`      |
| `beads`  | `bd ready --json`                                                                                  | `bd show <ID>`         | `bd close <ID> "Completed by Eden"`                      |

The selection wires three things:

1. The list-tasks command goes inside a `` !`...` `` shell block in `prompt.md` so the open-task list is expanded fresh each iteration.
2. The Dockerfile gains the install steps for the chosen CLI (`gh` from the GitHub apt repo, or `bd` from the Beads release page).
3. `.env.example` gains any backlog-manager-specific keys (`GH_TOKEN` for `github`; nothing for `beads`).

### Files produced

The same five filenames as `blank` (`Dockerfile`, `prompt.md`, `main.py`, `.env.example`, `.gitignore`) but with simple-loop content:

- **`Dockerfile`** — `python:3.13-slim` with `git`, the chosen backlog CLI, and a non-root `agent` user (`AGENT_UID`/`AGENT_GID` build-args default 1000; eden init's "Next steps" command auto-aligns to your host UID/GID).
- **`prompt.md`** — RALPH-style autonomous-agent instructions: explore → plan → execute → verify → commit → close. The "Open tasks" section embeds the list-tasks command. The agent emits `<promise>COMPLETE</promise>` when the queue is empty.
- **`main.py`** — calls `eden.run(name="worker", agent=..., sandbox=..., prompt_file=".eden/prompt.md", max_iterations=3)`.
- **`.env.example`** — agent API keys plus backlog manager env vars.
- **`.gitignore`** — same as `blank`.

### Customizing

The template is a starting point — edit `prompt.md` to change the agent's working rules, bump `max_iterations` in `main.py` for longer sessions, or swap in a different sandbox.

Read source: `eden/cli/_templates/simple_loop.py`, `eden/cli/_templates/_backlog.py`.

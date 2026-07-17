# CLI

Eden ships a small CLI primarily for project scaffolding. The orchestrator itself is invoked from Python — see [python-api.md](python-api.md).

## `eden init`

Scaffold a fresh `.eden/` directory in the current working directory. Refuses to overwrite an existing `.eden/`.

```bash
eden init --sandbox docker --agent claude-code --yes
```

On an interactive terminal, any flag you omit is collected via a prompt (with sensible defaults). With `--yes`, omitted flags fall back to defaults non-interactively. When stdin is **not** a TTY (CI, pipes) and you pass neither the flag nor `--yes`, init fails fast naming the missing flag rather than hanging on the prompt — so pass every flag, or `--yes`.

### Flags

| Flag | Default | Valid values | Description |
|---|---|---|---|
| `--sandbox` | `docker` (interactive prompt default) | `docker`, `podman` | Container runtime for the generated `.eden/main.py`. |
| `--agent` | `claude-code` (interactive prompt default) | `claude-code`, `codex`, `opencode`, `pi`, `cursor`, `copilot` | Agent factory imported in the generated `.eden/main.py`. |
| `--model` | per-agent default (see below) | any string | Model identifier passed to the agent factory. |
| `--template` | `blank` | `blank`, `simple-loop`, `sequential-reviewer`, `parallel-planner` | Scaffold template — see [templates.md](templates.md). |
| `--backlog` | `github` (when template needs one) | `github`, `beads`, `linear`, `jira` | Backlog manager that the tracker-aware templates target; ignored for `blank`. |
| `--image-name` | `eden:<cwd-basename-lowercase>` | any string | Container image tag referenced from the generated `.eden/main.py` and the suggested `docker build` command. |
| `--build-image` | `false` | flag | Build the scaffolded container image after writing `.eden/`. |
| `--create-label` | `false` | flag | Create or update the GitHub Issues `eden` label for GitHub-backed templates. |
| `--yes` | `false` | flag | Accept all defaults; skip interactive prompts. |

### Per-agent default models

When `--model` is omitted, the default depends on `--agent`:

| Agent | Default model |
|---|---|
| `claude-code` | `claude-opus-4-8` |
| `codex` | `gpt-5.4` |
| `opencode` | `claude-opus-4` |
| `pi` | `pi-3.5` |
| `cursor` | `claude-sonnet-4-6` |
| `copilot` | `claude-sonnet-4` |

### Files written

`eden init` creates `.eden/` with five files (see [templates.md](templates.md) for the literal contents):

- `.eden/Dockerfile` or `.eden/Containerfile` for `--sandbox podman` — minimal Python 3.13-slim image with `git`.
- `.eden/prompt.md` — placeholder prompt body. Edit this for your task.
- `.eden/main.py` — entry point that calls `eden.run(...)` with the chosen sandbox and agent factory.
- `.eden/.env.example` — sample environment variables for the chosen agent (e.g. `ANTHROPIC_API_KEY`).
- `.eden/.gitignore` — excludes `.env` and runtime artifacts (`logs/`, `sessions/`, `worktrees/`, `isolated/`).

After scaffolding, `eden init` prints the next steps it expects you to run:

```bash
cp .eden/.env.example .env  # then fill in your API keys
docker build -t <image-name> -f .eden/Dockerfile .
python .eden/main.py
```

Read source: `eden/cli/init.py`, `eden/cli/_templates/blank.py`, `eden/cli/_templates/simple_loop.py`, `eden/cli/_templates/_backlog.py`.

## Image Commands

Build or remove the container image referenced by scaffolded `.eden/main.py`.
Docker builds default to `.eden/Dockerfile`; Podman builds default to
`.eden/Containerfile`. Both pass UID/GID build args for the scaffolded `agent`
user and use the current directory as context for custom build files.

```bash
eden docker build-image
eden docker build-image --dockerfile Dockerfile.agent --image-name eden:agent
eden docker remove-image --image-name eden:agent
eden podman build-image
eden podman build-image --containerfile Containerfile.agent
eden podman remove-image
```

Read source: `eden/cli/_image.py`.

## `eden run`

Run a template's iteration loop **in-process** via `eden.run()` — no files scaffolded. Useful for quick experiments and CI pipelines where committing a generated `.eden/` directory adds no value.

```bash
eden run --template simple-loop --sandbox no-sandbox --agent claude-code --backlog github
```

For docker/podman sandboxes, supply `--image-name` (the image must already be built and align with your host UID/GID — same constraints as the scaffolded `eden init` flow).

### Flags

| Flag | Default | Valid values | Description |
|---|---|---|---|
| `--template` | `simple-loop` | `simple-loop` | Template to run. Currently only `simple-loop` is supported in-process. |
| `--sandbox` | `docker` | `docker`, `podman`, `no-sandbox` | Sandbox provider. `no-sandbox` runs commands directly on the host. |
| `--agent` | `claude-code` | `claude-code`, `codex`, `opencode`, `pi`, `cursor`, `copilot` | Agent factory. |
| `--model` | per-agent default | any string | Model identifier passed to the agent factory. |
| `--backlog` | `github` | `github`, `beads`, `linear`, `jira` | Backlog manager whose `list-tasks`/`view-task`/`close-task` commands get embedded in the prompt. |
| `--image-name` | _(none)_ | any string | Container image tag — required for `--sandbox docker` / `podman`. |
| `--max-iterations` | `3` | positive int | Max iteration loop turns. |
| `--idle-timeout` | `600.0` | seconds | Bail when the agent's stdout has been silent this long. |
| `--completion-timeout` | `60.0` | seconds | Grace window after the completion signal before terminating a still-open agent process. |
| `--cwd` | current dir | path | Repo to run against. |

The simple-loop prompt is identical to the one written by `eden init --template simple-loop` — see [templates.md](templates.md).

Read source: `eden/cli/run.py`.

## Session and cleanup commands

See [CLI session tools](cli-session-tools.md) for `eden cost`, `eden clean`, and `eden replay`.

## `eden version`

Print the installed Eden version and exit.

```bash
eden version
```

Equivalent to `python -c "import eden; print(eden.__version__)"`. Read source: `eden/cli/main.py`.

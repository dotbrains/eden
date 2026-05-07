# CLI

Eden ships a small CLI primarily for project scaffolding. The orchestrator itself is invoked from Python — see [python-api.md](python-api.md).

---

## `eden init`

Scaffold a fresh `.eden/` directory in the current working directory. Refuses to overwrite an existing `.eden/`.

```bash
eden init --sandbox docker --agent claude-code --yes
```

Without `--yes`, any flag you omit is collected interactively (with sensible defaults). With `--yes`, omitted flags fall back to defaults non-interactively.

### Flags

| Flag | Default | Valid values | Description |
|---|---|---|---|
| `--sandbox` | `docker` (interactive prompt default) | `docker`, `podman` | Container runtime for the generated `.eden/main.py`. |
| `--agent` | `claude-code` (interactive prompt default) | `claude-code`, `codex`, `opencode`, `pi` | Agent factory imported in the generated `.eden/main.py`. |
| `--model` | per-agent default (see below) | any string | Model identifier passed to the agent factory. |
| `--template` | `blank` | `blank`, `simple-loop`, `sequential-reviewer`, `parallel-planner` | Scaffold template — see [templates.md](templates.md). |
| `--backlog` | `github` (when template needs one) | `github`, `beads` | Backlog manager that the tracker-aware templates target; ignored for `blank`. |
| `--image-name` | `eden:<cwd-basename-lowercase>` | any string | Container image tag referenced from the generated `.eden/main.py` and the suggested `docker build` command. |
| `--yes` | `false` | flag | Accept all defaults; skip interactive prompts. |

### Per-agent default models

When `--model` is omitted, the default depends on `--agent`:

| Agent | Default model |
|---|---|
| `claude-code` | `claude-opus-4-7` |
| `codex` | `gpt-5` |
| `opencode` | `claude-opus-4` |
| `pi` | `pi-3.5` |

### Files written

`eden init` creates `.eden/` with five files (see [templates.md](templates.md) for the literal contents):

- `.eden/Dockerfile` — minimal Python 3.13-slim image with `git`.
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

## `eden version`

Print the installed Eden version and exit.

```bash
eden version
```

Equivalent to `python -c "import eden; print(eden.__version__)"`. Read source: `eden/cli/main.py`.

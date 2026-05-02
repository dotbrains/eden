# Templates

`eden init` scaffolds a project from a template. v0.1 ships one template (`blank`); more land in v0.2+.

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

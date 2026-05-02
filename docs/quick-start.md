# Quick start

Get from zero to a verified Eden run in under five minutes.

---

## Install

```bash
pip install eden-agent
```

Eden requires Python 3.11+.

## Run the simulated agent (no external CLI needed)

The `simulated_agent` emits a fixed output stream so you can verify the orchestrator works without installing a real agent CLI. The default output ends with the `<promise>COMPLETE</promise>` completion signal that `run()` watches for.

Run this from inside any git repository (the orchestrator carves a fresh worktree off the current branch). Save as `eden_smoke.py`:

```python
from pathlib import Path

from eden import run, simulated_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox

result = run(
    cwd=Path.cwd(),
    sandbox=no_sandbox(),
    agent=simulated_agent(
        output="hello from the simulated agent\n<promise>COMPLETE</promise>\n",
    ),
    prompt="ignored by the simulated agent",
    max_iterations=1,
)

print(f"branch: {result.branch}")
print(f"iterations: {len(result.iterations)}")
print(f"commits: {len(result.commits)}")
if result.commits:
    print(f"final sha: {result.commits[-1].sha}")
```

Run it:

```bash
python eden_smoke.py
```

You should see a generated branch name like `eden/20260502124551-548ac339` and one iteration. The simulated agent does not write files, so `commits` is `0`; switch to a real agent (next section) to produce committable changes.

## Scaffold a real project

Make sure your agent CLI (`claude`, `codex`, `opencode`, `pi`) is installed and authenticated, and that Docker (or your chosen sandbox) is running on the host first.

```bash
eden init --sandbox docker --agent claude-code --yes
```

This writes `.eden/Dockerfile`, `.eden/prompt.md`, `.eden/main.py`, `.eden/.env.example`, and `.eden/.gitignore`. Edit `prompt.md` for your task, then follow the next steps `eden init` prints:

```bash
cp .eden/.env.example .env  # then fill in your API keys (e.g. ANTHROPIC_API_KEY)
docker build -t eden:<repo-name> -f .eden/Dockerfile .
python .eden/main.py
```

Replace `<repo-name>` with the lowercased name of the current directory — that's the default tag `eden init` chose (override with `--image-name` at scaffold time). The docker provider expects the image to already exist; it does not auto-build.

## Where to go next

- [Python API](python-api.md) — full reference for `run(...)` and friends.
- [Sandbox providers](sandbox-providers.md) *(forthcoming)* — pick the right sandbox for your workload.
- [Agents](agents.md) *(forthcoming)* — choose between `claude_code`, `codex`, `opencode`, `pi`.
- [Prompts](prompts.md) *(forthcoming)* — beyond a literal string: shell blocks, args, file sources.

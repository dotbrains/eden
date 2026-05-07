# Tutorial: build your first agent loop in 10 minutes

This walks you from an empty repo to a running agent loop that fixes a real bug. By the end you'll have a working `simple-loop` template, understand how the iteration loop terminates, and know where to look when things go wrong.

If you just want a one-liner, skip to the [Quick start](quick-start.md).

---

## Prerequisites

- Python 3.11+
- Docker or Podman (skip if you want to run the agent directly on the host with `no_sandbox`)
- An Anthropic API key with credits (`ANTHROPIC_API_KEY`)
- `claude` CLI installed locally (or an agent of your choice — the tutorial uses `claude-code`)

---

## 1. Create a sandbox repo

We need a git repo with an actual bug for the agent to fix. The smaller, the faster the demo.

```bash
mkdir eden-tutorial && cd eden-tutorial
git init -q
cat > calc.py <<'EOF'
def add(a, b):
    return a - b   # wrong: should be a + b
EOF
cat > test_calc.py <<'EOF'
from calc import add

def test_add():
    assert add(2, 3) == 5
EOF
git add . && git commit -qm "initial buggy calc"
```

Sanity-check the bug exists:

```bash
python -m pytest test_calc.py
# 1 failed, 0 passed
```

---

## 2. Install eden

```bash
python -m venv .venv && . .venv/bin/activate
pip install eden-agent
eden version    # confirms it's installed
```

---

## 3. Scaffold a simple-loop project

```bash
eden init \
  --sandbox no-sandbox \
  --agent claude-code \
  --backlog github \
  --template simple-loop \
  --yes
```

`eden init` writes a `.eden/` directory: `Dockerfile`, `prompt.md`, `main.py`, `.env.example`, `.gitignore`. We won't use the Dockerfile because we picked `no-sandbox` (the agent runs directly on the host), but it's there if you switch later.

---

## 4. Replace the prompt with something specific

The default `prompt.md` reaches for a backlog tracker. For the tutorial we want a single hard-coded task. Overwrite it:

```bash
cat > .eden/prompt.md <<'EOF'
# Task

There's a failing test in test_calc.py. Run pytest, look at the output,
fix the bug in calc.py, then re-run pytest until it passes.

Commit the fix with the message "fix: add returns sum, not difference".

When the tests pass and the commit is made, output:

<promise>COMPLETE</promise>
EOF
```

The `<promise>COMPLETE</promise>` line is the **completion signal**. Eden's iteration loop watches the agent's stdout for this string and stops when it appears. Without it, the loop runs until `max_iterations` or `idle_timeout`.

---

## 5. Edit `main.py` to run with no-sandbox

`eden init` defaulted to docker. Switch to no-sandbox:

```python
from eden import claude_code, run
from eden.sandboxes import no_sandbox as sandbox_provider

if __name__ == "__main__":
    result = run(
        agent=claude_code("claude-opus-4-7"),
        sandbox=sandbox_provider.provider(),
        prompt_file=".eden/prompt.md",
        max_iterations=3,
    )
    print(f"Completion: {result.completion_signal}")
    print(f"Iterations: {len(result.iterations)}")
    print(f"Branch:     {result.branch}")
```

---

## 6. Run it

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python .eden/main.py
```

What happens, in order:

1. Eden creates a worktree under `.eden/worktrees/eden/<branch>` so the agent works on an isolated branch.
2. The agent starts; eden tails its stdout in real time.
3. The agent reads `test_calc.py`, runs pytest, sees the failure.
4. The agent edits `calc.py`, re-runs pytest, sees green.
5. The agent commits.
6. The agent prints `<promise>COMPLETE</promise>`.
7. The loop terminates and merges the branch back to `main`.

The whole run usually takes 30-60 seconds.

---

## 7. Inspect what happened

After the run finishes:

```bash
# What did the run cost?
eden cost

# Replay the agent's transcript without re-running it.
eden replay $(ls .eden/sessions/*/iter-0-*.jsonl | head -1)

# Bug fixed?
git log --oneline -3
python -m pytest test_calc.py   # passes
```

---

## What to read next

- **The loop terminated unexpectedly** — read [Errors](errors.md). The most common bug-shape is `IdleTimeout` (your agent went silent because the prompt didn't make completion criteria obvious).
- **Want to wire this into CI** — see the [GitHub Action](github-action.md). One step replaces step 6.
- **Want a more interesting workflow** — try `eden init --template plan-implement-review`. Three sequential agents (planner, implementer, reviewer) on one shared sandbox per task. See [Templates](templates.md).
- **Want to understand how the loop works under the hood** — read [How it works](how-it-works.md). It walks through worktree creation, sandbox lifecycle, the iteration state machine, and how completion signals are matched.
- **Want to see what's happening live** — wire up [tracing](python-api.md#tracing) to a local Jaeger or Honeycomb. Every iteration shows up as a span tree with `eden.run > eden.iteration > eden.agent.exec`.

---

## Common gotchas

- **`max_iterations: 1`** — the simple-loop default in older docs is 1, which means the loop runs once and stops regardless of completion. Use `max_iterations: 3` (or higher) so the agent gets a chance to react to test failures across iterations.
- **The agent never terminates** — confirm your prompt asks for the completion signal explicitly, and that the signal is unique enough that intermediate text won't false-match.
- **Branch already exists** — eden refuses to overwrite. Either pass `branch_strategy=BranchStrategy.named(...)` with a fresh name, or delete the leftover branch with `git branch -D <name>`.
- **Agent sees stale files** — when running with `no-sandbox`, the agent has direct access to your current worktree. If you have uncommitted changes in the host repo, the agent sees them. Use `docker` or `podman` for isolation.

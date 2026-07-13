# Templates

`eden init` scaffolds a project from a template. Seven templates ship today: `blank` (minimal), `simple-loop` (an iteration-driven worker over a backlog manager), `sequential-reviewer` (implement-then-review per task on a shared sandbox), `parallel-planner` (plan + parallel-execute + merge over the unblocked backlog), `parallel-planner-with-review` (parallel execution with per-branch review), `plan-implement-review` (three sequential agents: planner produces a structured plan, implementer executes it, reviewer audits the diff), and `github-agent-workflows` (label-driven GitHub Actions for issue implementation and PR review).

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

A runnable entry point that imports the chosen agent factory and sandbox provider, then calls `eden.run(...)` with `prompt_file=".eden/prompt.md"` and `max_iterations=5`. The rendered file picks the agent factory and sandbox module based on the flags passed to `eden init`. For `--sandbox docker --agent claude-code --model claude-opus-4-8 --image-name eden:demo`, you get:

```python
"""Entry point for this Eden project.

Run with: python .eden/main.py
"""

from eden import run, claude_code
from eden.sandboxes import docker as sandbox_provider


if __name__ == "__main__":
    result = run(
        agent=claude_code("claude-opus-4-8"),
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

A runnable worker that picks open tasks from a backlog manager and processes them one per iteration.

```bash
# GitHub Issues backed (default)
eden init --template simple-loop --sandbox docker --agent claude-code --backlog github --yes

# Other backlog managers
eden init --template simple-loop --backlog beads --yes
eden init --template simple-loop --backlog linear --yes
eden init --template simple-loop --backlog jira --yes
```

### `--backlog` flag

`--backlog` selects which backlog manager the rendered `prompt.md` expects. Eden ships four:

| Name     | List command                                                                                | View command           | Close command                                            |
|----------|---------------------------------------------------------------------------------------------|------------------------|----------------------------------------------------------|
| `github` | `gh issue list --state open --label eden --json ... --jq '[.[] \| {id, title, body, ...}]'` | `gh issue view <ID>`   | `gh issue close <ID> --comment "Completed by Eden"`      |
| `beads`  | `bd ready --json`                                                                            | `bd show <ID>`         | `bd close <ID> "Completed by Eden"`                      |
| `linear` | `linear-list` (helper script — wraps the Linear GraphQL API, returns JSON)                  | `linear-view <ID>`     | `linear-close <ID>` (transitions to the team's "completed" state) |
| `jira`   | `jira issue list -q "assignee = currentUser() AND status not in (Done, Closed, Resolved)"` | `jira issue view <ID>` | `jira issue move <ID> "Done"`                            |

The selection wires three things:

1. The list-tasks command goes inside a `` !`...` `` shell block in `prompt.md` so the open-task list is expanded fresh each iteration.
2. The Dockerfile gains the install steps for the chosen tooling: `gh` from the GitHub apt repo, `bd` from the Beads release page, `curl + jq + linear-* helper scripts` baked into the image, or `jira-cli` from `ankitpokhrel/jira-cli`'s GitHub releases.
3. `.env.example` gains any backlog-manager-specific keys (`GH_TOKEN` for `github`, `LINEAR_API_KEY` for `linear`, `JIRA_API_TOKEN` plus auth-type for `jira`; nothing for `beads`).

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

---

## `sequential-reviewer`

A two-phase loop: per task, an *implementer* agent commits a change on a fresh named branch, then a *reviewer* agent inspects the diff and either approves it or commits a follow-up cleanup. Both agents share one [`Sandbox`](python-api.md#sandboxrun) so the second run sees the implementer's working tree directly — no extra container, no extra branch carve.

```bash
eden init --template sequential-reviewer --backlog github --yes
```

Same `--backlog` flag as `simple-loop` (defaults to `github`; `beads` also supported).

### Files produced

| File                         | Role                                                                                              |
|------------------------------|---------------------------------------------------------------------------------------------------|
| `Dockerfile`                 | Same shape as `simple-loop`: python:3.13-slim, the chosen backlog CLI, non-root `agent` user.    |
| `implement-prompt.md`        | Pick the highest-priority open task and commit its implementation. Emits `<promise>COMPLETE</promise>` when done. |
| `review-prompt.md`           | Reads `git diff {{TARGET_BRANCH}}...{{SOURCE_BRANCH}}`, suggests cleanups, commits any.           |
| `CODING_STANDARDS.md`        | A short, editable list of standards the reviewer enforces.                                        |
| `main.py`                    | Outer loop carving a named branch per iteration and running implementer + reviewer in sequence.   |
| `.env.example`, `.gitignore` | Same as the other templates.                                                                       |

### Customizing

Drop in your own `CODING_STANDARDS.md`. Tighten the implementer prompt to your codebase's testing conventions. Crank `MAX_ITERATIONS` in `main.py` for longer sessions.

Read source: `eden/cli/_templates/sequential_reviewer.py`.

---

## `parallel-planner`

Three-phase orchestration for parallel-friendly backlogs:

1. **Plan** — a single planner agent reads the backlog, builds a dependency graph, and emits a `<plan>...</plan>` JSON block listing unblocked tasks. Eden's [`Output.object`](python-api.md#output) extracts and validates the JSON, so a malformed plan surfaces as a `StructuredOutputError` with the raw match preserved.
2. **Execute** — one implementer agent per task, run concurrently via `concurrent.futures.ThreadPoolExecutor`. Each agent gets its own sandbox on its own named branch.
3. **Merge** — a single merger agent consolidates the branches that produced commits back into the target branch.

```bash
eden init --template parallel-planner --backlog github --yes
```

### Files produced

| File                  | Role                                                                                                  |
|-----------------------|-------------------------------------------------------------------------------------------------------|
| `Dockerfile`          | Same shape as the other tracker-aware templates.                                                      |
| `plan-prompt.md`      | Builds the plan; outputs JSON inside `<plan>...</plan>`.                                              |
| `implement-prompt.md` | Per-task work prompt; templated with `{{TASK_ID}}`, `{{TASK_TITLE}}`, `{{TASK_BRANCH}}`.              |
| `merge-prompt.md`     | Merges the listed branches; templated with `{{BRANCHES}}` and `{{TASKS}}`.                            |
| `main.py`             | Outer loop with three `eden.run()` calls per cycle (plan, execute parallel, merge).                  |
| `.env.example`, `.gitignore` | Same as the other templates.                                                                   |

### Customizing

- Tune `MAX_PARALLEL` in `main.py` to your CPU/IO budget.
- Swap the planner agent for an opus-class model (`MAX_ITERATIONS=1`, deeper reasoning) and the implementers for a faster sonnet — most users will edit `_agent()` to dispatch by phase.
- Adjust the planner prompt's "4-6 tasks per cycle" hint to suit your backlog density.

Read source: `eden/cli/_templates/parallel_planner.py`.

---

## `plan-implement-review`

Three sequential agents on **one** sandbox per task, each with a distinct role and prompt:

1. **Planner** — reads the backlog, picks the highest-priority task, produces a numbered, executable plan wrapped in `<plan>...</plan>`. `max_iterations=1`, plan extracted via `Output.string(tag="plan")`.
2. **Implementer** — receives the plan via `prompt_args={"PLAN": plan.output}` and executes it on a named branch. Stays within the planner's scope; if the plan is wrong, leaves a comment and stops rather than improvising.
3. **Reviewer** — sees the same plan plus the diff, either approves with `<promise>APPROVED</promise>` or appends a `review:` follow-up commit.

```bash
eden init --template plan-implement-review --backlog github --yes
```

### Why a separate planner

Splitting "decide what to do" from "do it" gives the planner a chance to think about scope and risks under a stricter context window before the implementer commits to file edits. The plan is human-inspectable in the run summary; if the implementer drifts, the reviewer catches it because both are anchored on the same plan text.

### Files produced

| File                    | Role                                                            |
|-------------------------|-----------------------------------------------------------------|
| `Dockerfile`            | Same shape as the other tracker-aware templates.                |
| `plan-prompt.md`        | Reads backlog; outputs `<plan>...</plan>`. No code changes.     |
| `implement-prompt.md`   | Receives `{{PLAN}}`; executes on the branch, commits, closes.   |
| `review-prompt.md`      | Receives `{{PLAN}}` + diff; approves or applies `review:` fix.  |
| `CODING_STANDARDS.md`   | Project-tunable rubric the reviewer enforces.                   |
| `main.py`               | Three sequential `sandbox.run()` calls (planner / impl / review).|
| `.env.example`, `.gitignore` | Same as the other templates.                                |

### Customizing

- Tighten `MAX_TASKS` in `main.py`.
- Use a larger model for the planner (`claude-opus-4-8`) and a faster one for the implementer/reviewer (`claude-sonnet-4-6`) — edit `_AGENT_CALL` and the call sites.
- The reviewer is intentionally idempotent: if the diff is clean it approves. Tune `CODING_STANDARDS.md` to project taste.

Read source: `eden/cli/_templates/plan_implement_review.py`.

---

## `github-agent-workflows`

Moved to [GitHub agent workflow template](github-agent-workflow-template.md#github-agent-workflows).

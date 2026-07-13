# Templates

`eden init` scaffolds a project from a template. Seven templates ship today:
`blank` (minimal), `simple-loop` (an iteration-driven worker over a backlog
manager), `sequential-reviewer` (implement-then-review per task on a shared
sandbox), `parallel-planner` (plan + parallel-execute + merge over the
unblocked backlog), `parallel-planner-with-review` (parallel execution with
per-branch review), `plan-implement-review` (three sequential agents), and
`github-agent-workflows` (label-driven GitHub Actions for issue implementation
and PR review).

---

## `blank`

The minimal scaffold: just the moving parts wired up. Edit `.eden/prompt.md`, then run `python .eden/main.py`. See [Blank template](template-blank.md) for the full file-by-file reference.

```bash
eden init --template blank --sandbox docker --agent claude-code --yes
```

---

## `simple-loop`

Moved to [Simple-loop template](template-simple-loop.md#simple-loop).

### `--backlog` flag

Moved to [Simple-loop backlog flag](template-simple-loop.md#--backlog-flag).

### Files produced

Moved to [Simple-loop files produced](template-simple-loop.md#files-produced).

### Customizing

Moved to [Simple-loop customization](template-simple-loop.md#customizing).

Compatibility anchor:

<a id="simple-loop"></a>

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

Moved to [Plan/implement/review template](template-plan-implement-review.md#plan-implement-review).

Compatibility anchor:

<a id="plan-implement-review"></a>

---

## `github-agent-workflows`

Moved to [GitHub agent workflow template](github-agent-workflow-template.md#github-agent-workflows).

# Plan/Implement/Review Template

Detailed reference for the `plan-implement-review` template. See
[Templates](templates.md) for the other local run templates.

---

## `plan-implement-review`

Three sequential agents on **one** sandbox per task, each with a distinct role
and prompt:

1. **Planner** — reads the backlog, picks the highest-priority task, produces a
   numbered, executable plan wrapped in `<plan>...</plan>`. `max_iterations=1`,
   plan extracted via `Output.string(tag="plan")`.
2. **Implementer** — receives the plan via `prompt_args={"PLAN": plan.output}`
   and executes it on a named branch. Stays within the planner's scope; if the
   plan is wrong, leaves a comment and stops rather than improvising.
3. **Reviewer** — sees the same plan plus the diff, either approves with
   `<promise>APPROVED</promise>` or appends a `review:` follow-up commit.

```bash
eden init --template plan-implement-review --backlog github --yes
```

### Why a separate planner

Splitting "decide what to do" from "do it" gives the planner a chance to think
about scope and risks under a stricter context window before the implementer
commits to file edits. The plan is human-inspectable in the run summary; if the
implementer drifts, the reviewer catches it because both are anchored on the
same plan text.

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
- Use a larger model for the planner (`claude-opus-4-8`) and a faster one for
  the implementer/reviewer (`claude-sonnet-4-6`) — edit `_AGENT_CALL` and the
  call sites.
- The reviewer is intentionally idempotent: if the diff is clean it approves.
  Tune `CODING_STANDARDS.md` to project taste.

Read source: `eden/cli/_templates/plan_implement_review.py`.

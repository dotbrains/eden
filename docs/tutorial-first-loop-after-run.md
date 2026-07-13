# After your first loop

Inspect the output from [Tutorial: build your first agent loop](tutorial-first-loop.md)
after the run finishes.

<a id="7-inspect-what-happened"></a>

## Inspect what happened

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

<a id="what-to-read-next"></a>

## What to read next

- **The loop terminated unexpectedly** — read [Errors](errors.md). The most common bug-shape is `IdleTimeout` (your agent went silent because the prompt didn't make completion criteria obvious).
- **Want to wire this into CI** — see the [GitHub Action](github-action.md). One step replaces step 6.
- **Want a more interesting workflow** — try `eden init --template plan-implement-review`. Three sequential agents (planner, implementer, reviewer) on one shared sandbox per task. See [Templates](templates.md).
- **Want to understand how the loop works under the hood** — read [How it works](how-it-works.md). It walks through worktree creation, sandbox lifecycle, the iteration state machine, and how completion signals are matched.
- **Want to see what's happening live** — wire up [tracing](python-api.md#tracing) to a local Jaeger or Honeycomb. Every iteration shows up as a span tree with `eden.run > eden.iteration > eden.agent.exec`.
- **Hit a setup snag** — see [Tutorial first-loop troubleshooting](tutorial-first-loop-troubleshooting.md).

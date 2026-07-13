# CLI session tools

`eden cost`, `eden clean`, and `eden replay` inspect or prune runtime artifacts after an Eden run. See [cli.md](cli.md) for scaffolding and execution commands.

---

## `eden cost`

Aggregate token usage from captured session JSONLs under `.eden/sessions/`.

```bash
eden cost                  # all branches, table view
eden cost --branch feat-x  # filter to one sanitized branch dir
eden cost --cwd ../other-repo
```

Reads each session's terminal `result` line and sums `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens`. The table breaks down per-branch with sessions, iterations, and totals.

Read source: `eden/cli/cost.py`.

## `eden clean`

Delete stale runtime artifacts under `.eden/{logs,sessions,worktrees,isolated}`. Refuses to touch the scaffolded files (`Dockerfile`, `prompt.md`, `main.py`, `.env.example`, `.gitignore`).

```bash
eden clean                 # delete artifacts older than 7 days
eden clean --days 30       # custom age cutoff
eden clean --all           # purge everything regardless of age
eden clean --cwd ../other-repo
```

Read source: `eden/cli/clean.py`.

## `eden replay`

Pretty-print a captured session JSONL as a human-readable transcript: system messages, user turns, assistant text, and tool uses. Useful for after-the-fact debugging without re-executing the run.

```bash
eden replay path/to/iter-0-abc.jsonl       # explicit path
eden replay feat-x/2 --cwd .               # <branch>/<iter> shorthand
eden replay abc123 --cwd .                 # match by session id substring
eden replay feat-x/2 --no-tools            # hide tool_use blocks
```

Resolution order:
1. Argument is a path on disk -> use as-is.
2. Contains `/` -> treated as `<branch>/<iter>` and globbed under `.eden/sessions/<branch>/iter-<iter>-*.jsonl`.
3. Otherwise -> globbed under `.eden/sessions/**/iter-*-<arg>.jsonl`.

Ambiguous matches fail with the list of candidates so you can pick a specific path.

Read source: `eden/cli/replay.py`.

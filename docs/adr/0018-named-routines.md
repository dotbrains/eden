# ADR 0018 — Named routines (`eden routine`)

**Status:** Accepted (2026-08-17).

## Context

Every `eden run` invocation re-types the full flag set (`--sandbox`,
`--agent`, `--model`, `--template`, `--backlog`, `--image-name`,
`--max-iterations`, `--idle-timeout`, `--completion-timeout`). There was no
way to save a specific combination and invoke it again by name.

Prompted by a feature-gap comparison against
[owainlewis/factory](https://github.com/owainlewis/factory), a Go control
plane that coordinates AI coding agents across many repos. Factory's core
abstraction is a "Routine": a durable, versioned prompt-and-settings bundle
admitted to run manually or on a schedule. Most of Factory's surface —
a browser UI, a polling worker pool, a scheduler, a multi-repo catalog —
doesn't fit eden's model of a one-shot library call in a single repo, and
Factory's own README concedes its unified CLI and elastic backend are
"designed but not implemented." The one idea that transplants cleanly is
the naming primitive itself: save a reusable config, run it by name.

## Decision

Add `eden routine save|list|show|remove|run`, a thin CLI layer over the
same in-process path `eden run` already uses — no daemon, no scheduler, no
control plane.

- **Storage:** `.eden/routines/<name>.json`, one file per routine
  (`eden/cli/routine/_store.py`). Plain JSON rather than Factory's TOML —
  eden already writes session artifacts as JSON/JSONL and this needs no new
  dependency. Routine names are restricted to `[A-Za-z0-9][A-Za-z0-9._-]*`
  to keep the filename derivation injection-safe (no `/`, no leading `.`).
- **No custom versioning.** Factory's control plane persists routine
  version history in SQLite. Eden's routine files live under `.eden/`,
  which is already git-tracked (unlike `.eden/{logs,sessions,worktrees,
  isolated}`, which `eden clean` prunes and the scaffolded `.gitignore`
  excludes) — `eden clean` and `.gitignore` were deliberately left
  untouched by this change, so a saved routine's history is just its git
  log. Building a bespoke version store would duplicate what git already
  gives every other file under `.eden/`.
- **`eden routine save`** re-validates against the same `_VALID_SANDBOXES`/
  `_VALID_AGENTS`/`_VALID_TEMPLATES`/`_VALID_BACKLOGS` tuples `eden run`
  uses (`eden/cli/run.py`), and resolves an omitted `--model` through the
  same `_DEFAULT_MODELS` table — hoisted from a local dict to a module
  constant so both commands share one source of truth. A routine always
  stores a concrete model, so it stays reproducible even if eden's defaults
  change later. Saving over an existing name requires `--force`, matching
  `eden init`'s refuse-to-overwrite convention.
- **`eden routine run`** re-validates the loaded config's sandbox/agent/
  backlog before building anything, in case the JSON was hand-edited or
  written by a different eden version whose supported values have since
  changed — it fails with a clear `BadParameter` instead of a confusing
  error deep in agent/sandbox construction.
- **No scheduling.** Factory's scheduler needs a persistent daemon; eden
  has none and this ADR doesn't add one. A routine still runs once, at
  invocation time — the same semantics as `eden run`. Recurring execution
  is left to the caller's own scheduler (cron, launchd, CI) invoking
  `eden routine run <name>`, exactly as it would invoke `eden run` today.
- **No cross-repo catalog.** A routine is scoped to the repo it's saved
  in (`--cwd`), matching every other stateful `eden` command (`cost`,
  `clean`, `replay`).

## Consequences

- `eden run` and `eden routine run` share validation/build helpers
  (`_build_agent`, `_build_sandbox`, `_completion_summary`,
  `_DEFAULT_MODELS`) imported from `eden/cli/run.py`; the thin
  orchestration glue (render prompt, call `eden.run()`, print the summary)
  is duplicated once between the two call sites rather than introducing a
  shared executor — `eden/cli/run.py` sits four lines under its 168-line
  budget, so extracting a new abstraction there wasn't worth the churn for
  two call sites.
- `eden/cli/` was already at its 15-file directory budget
  (`scripts/check_loc_budget.py`), so the new commands live under a new
  `eden/cli/routine/` subpackage rather than as top-level files, mirroring
  the existing `eden/cli/cleaning/` and `eden/cli/_templates/` split.
- No new public API surface — routines are CLI-only, like `cost`, `clean`,
  and `replay`. Nothing changes in `eden/__init__.py` or
  `docs/python-api.md`.

## See also

- `eden/cli/routine/` — command implementations.
- `eden/cli/run.py` — shared validation/build helpers and `_DEFAULT_MODELS`.
- [`docs/cli.md`](../cli.md) — user-facing `eden routine` reference.

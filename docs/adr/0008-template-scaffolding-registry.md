# ADR 0008 — Template scaffolding registry

**Status:** Accepted (2026-05-07).

## Context

Eden ships four templates today (`blank`, `simple-loop`, `sequential-reviewer`, `parallel-planner`) and three of them want the same backlog-manager wiring: a list-tasks shell command embedded in the prompt, a view-task command for per-task expansion, a close command to mark work done, and a Dockerfile snippet that installs the corresponding CLI (`gh` or `bd`).

Two choices for how the templates pull this wiring:

1. **Per-template hardcoding.** Each template renders its own Dockerfile and prompt with the GitHub commands inlined. Adding Beads support means duplicating every template; adding a third backlog manager means tripling.
2. **A registry of `BacklogManager` entries.** Each entry encapsulates `list_tasks_command`, `view_task_command`, `close_task_command`, `dockerfile_install`, and `env_example_lines`. Templates take a `BacklogManager` argument; the renderer substitutes commands into format strings. `eden init --backlog github|beads` selects the entry; `simple-loop`, `sequential-reviewer`, and `parallel-planner` all consume the same registry.

## Decision

Adopt option 2. `eden/cli/_templates/_backlog.py` defines `BacklogManager` (a frozen dataclass) and a tuple of two registry entries: `github` and `beads`. Two helpers — `get_backlog_manager(name)` and `list_backlog_managers()` — gate access. Templates declare their backlog dependency by accepting a `backlog: BacklogManager` argument in their `render_*()` function.

`eden init` validates the `--backlog` flag against the registry's names and routes the chosen entry into whichever template renderer matches `--template`. Templates that don't need backlog wiring (`blank`) skip the parameter and the validation; the `_TEMPLATES_REQUIRING_BACKLOG` set in `eden/cli/init.py` carries the policy.

The registry deliberately stays small. Each entry is data — five fields, no behaviour. New backlog managers (Linear, Jira, Asana, an internal queue) are five-line additions.

## Consequences

- A new template that needs backlog wiring picks up GitHub and Beads support for free. Adding it is a `render_*()` function plus a wiring stanza in `eden/cli/init.py`.
- A new backlog manager (e.g. Linear) gets full template fan-out for free. It's one entry in `_REGISTRY` plus an entry in the docs table.
- The `dockerfile_install` field carries the install snippet rather than inlining it in every template. Each template pastes the snippet into a `{backlog_install}` placeholder; the format-string mechanism is the only coupling between registry and templates.
- The registry doesn't try to abstract over backlog-manager semantics (e.g. "is this issue blocked?"). Templates that need that level of reasoning ask the agent to figure it out from the JSON the list command returns. Avoids speculative generalization.
- `env_example_lines` is registry-data, not a separate code path. GitHub templates get `GH_TOKEN=`; Beads gets nothing because `bd` reads no env. Future managers add their own lines without touching templates.
- The four template renderers remain independent — each owns its prompt content and main.py shape, but pulls backlog commands and the Docker install snippet from the same source. No template inherits from another; duplication is bounded to per-template prose, which is what users want to customize anyway.

## See also

- `eden/cli/_templates/_backlog.py` — registry definition.
- `eden/cli/_templates/{simple_loop,sequential_reviewer,parallel_planner}.py` — consumers.
- [`docs/templates.md`](../templates.md) — user-facing documentation of each template + the `--backlog` matrix.
- Upstream 0.4.6 introduced its equivalent backlog-manager registry with two entries; eden's registry now ships four (`github`, `beads`, `linear`, `jira`) using the same shape.

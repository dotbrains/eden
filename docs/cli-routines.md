# CLI routine commands

`eden routine` saves a specific `eden run` flag combination under a name so
you can re-run it later without re-typing every flag. See
[cli.md](cli.md#eden-run) for what each underlying flag does.

A routine is a JSON file at `.eden/routines/<name>.json`. It's meant to be
committed alongside the rest of a scaffolded `.eden/` directory — `eden
clean` never touches `.eden/routines/`, and the scaffolded `.gitignore`
doesn't exclude it — so history comes from `git log`, not a bespoke version
scheme.

## `eden routine save`

```bash
eden routine save nightly-lint-fix \
  --sandbox docker --agent claude-code --image-name eden:agent \
  --backlog github --max-iterations 5
```

Validates flags the same way `eden run` does and resolves an omitted
`--model` to the same per-agent default. Refuses to overwrite an existing
routine unless you pass `--force`.

| Flag | Default | Description |
|---|---|---|
| `--sandbox` | `docker` | `docker`, `podman`, or `no-sandbox`. |
| `--agent` | `claude-code` | `claude-code`, `codex`, `opencode`, `pi`, `cursor`, `copilot`. |
| `--model` | per-agent default | Resolved and stored concretely, so the routine stays reproducible even if eden's defaults change later. |
| `--template` | `simple-loop` | Currently only `simple-loop`. |
| `--backlog` | `github` | `github`, `beads`, `linear`, `jira`. |
| `--image-name` | _(none)_ | Required when `--sandbox` is `docker`/`podman`. |
| `--max-iterations` | `3` | Maximum iteration loop turns. |
| `--idle-timeout` | `600.0` | Seconds of silence before bailing. |
| `--completion-timeout` | `60.0` | Grace window after the completion signal. |
| `--force` | `false` | Overwrite an existing routine of the same name. |
| `--cwd` | current dir | Repo to save the routine in. |

Read source: `eden/cli/routine/_save.py`.

## `eden routine list`

```bash
eden routine list
eden routine list --cwd ../other-repo
```

Prints a table of every routine saved under `.eden/routines/` in the target
repo: name, sandbox, agent, model, template, backlog.

## `eden routine show`

```bash
eden routine show nightly-lint-fix
```

Prints a saved routine's full stored configuration, one field per line.

## `eden routine remove`

```bash
eden routine remove nightly-lint-fix
```

Deletes the routine's JSON file. Fails if no routine with that name exists.

## `eden routine run`

```bash
eden routine run nightly-lint-fix
eden routine run nightly-lint-fix --cwd ../other-repo
```

Loads the named routine and runs it exactly like `eden run` would with the
same flags — same in-process `eden.run()` call, same completion/iteration/
branch summary on exit. Re-validates the stored sandbox/agent/backlog
before building anything, so a hand-edited or stale routine file fails with
a clear error instead of a confusing one deep in agent/sandbox setup.

`eden routine run` takes no flags of its own beyond `--cwd` — it replays
exactly what was saved. To change a setting, `eden routine save` the name
again (with `--force`).

Routine names are restricted to `[A-Za-z0-9][A-Za-z0-9._-]*` (no `/`, no
leading `.`), since the name is used directly as a filename.

Read source: `eden/cli/routine/_run.py`, `eden/cli/routine/_store.py`.

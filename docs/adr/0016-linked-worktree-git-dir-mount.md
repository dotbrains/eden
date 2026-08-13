# ADR 0016 — Bind-mount the git common dir for linked worktrees

**Status:** Accepted (2026-08-12).

## Context

`docker`/`podman` are bind-mount providers: they bind-mount `worktree_path`
at `/workspace` and run `handle.exec(cmd)` against that container. Nothing
else about the host repository is mounted.

`merge_to_head` and `named` — the default branch strategies for bind-mount
providers (`eden/orchestrator/_setup.py`) — carve the worktree with
`git worktree add`. A linked worktree's `.git` is not a directory; it is a
*file* holding an absolute host path to the main repository's private
worktree metadata dir:

```
gitdir: /host/repo/.git/worktrees/<branch>
```

That metadata dir in turn has a `commondir` file pointing at the main
repository's shared object store, typically `/host/repo/.git`. Mounting only
`worktree_path` leaves both paths unreachable inside the container — the
`.git` file's pointer resolves to nothing there — so every git command
against the mounted worktree fails:

```
fatal: not a git repository: /host/repo/.git/worktrees/<branch>
```

This affects the *default* configuration for both providers, verified with a
real `git worktree add` + `docker run -v <worktree>:/workspace` reproduction:
`git status` inside the container fails outright. `head`-strategy sandboxes
are unaffected — there `worktree_path` equals `host_repo_path`, so `.git` is
already a real directory inside the mount. Sandcastle (a TypeScript analogue
of eden with the same bind-mount + linked-worktree design) hit and fixed the
same base problem — see its ADR `0006-git-worktree-mounts-on-windows.md`,
which also covers a Windows-specific extension of the same fix.

## Decision

Bind-mount the git common dir the worktree's `.git` file resolves to,
**at its own absolute host path** (an identity mount), so the pointer
resolves inside the container exactly as it does on the host. This mirrors
how eden already treats every other mount: `Mount.host` and `Mount.sandbox`
are independent, but for this one Eden computes both as the same path.

`eden/providers/_impl/container_git_mount.py` (`resolve_git_common_dir`)
reads `worktree_path/.git`, follows the `gitdir:` pointer, and follows
`commondir` if present, to find the directory to mount. It returns `None`
(no extra mount) when:

- `.git` is already a real directory (the `head` strategy).
- The resolved common dir doesn't exist.
- The resolved common dir is a Windows-shaped path (`C:\...`). On Windows the
  `.git` file's *own* `gitdir:` content is a Windows path a Linux container
  can't parse regardless of mount layout, and a mount target in that shape
  would fail container startup outright — trading a git-command failure for
  a container-start failure is a regression, not a fix. Docker/Podman are
  documented as Linux/macOS providers (`docs/sandbox-providers.md`), so this
  is out of scope here rather than a gap; fixing it would need the same
  `.git`-file-rewrite Sandcastle's ADR 0006 describes for its Windows case.

`container_run_args.build_mount_map` adds this mount first (lowest
precedence), before `/workspace` and any user/provider mounts, so an explicit
mount at the same target — vanishingly unlikely in practice — still wins.

## Consequences

- `docker`/`podman` sandboxes using the default `merge_to_head` strategy (or
  an explicit `named` strategy) can run `git status`/`git add`/`git commit`
  inside the container, matching the behavior the docs already promised
  ("lets agents commit without manual Git setup" in
  `docs/sandbox-providers.md`).
- The common dir mounts read-write (git needs to write objects and update
  the worktree-private `HEAD`/index under it), with the same UID/SELinux
  treatment as every other mount.
- Windows hosts running `docker`/`podman` with `merge_to_head`/`named` remain
  unfixed by this ADR; `head` strategy (or `isolated`, which doesn't use
  linked worktrees) still works there today.

## See also

- [`docs/container-sandbox-providers.md`](../container-sandbox-providers.md) — Docker/Podman mount behavior.
- `eden/providers/_impl/container_git_mount.py` — `resolve_git_common_dir`.
- `eden/providers/_impl/container_run_args.py` — `build_mount_map`.

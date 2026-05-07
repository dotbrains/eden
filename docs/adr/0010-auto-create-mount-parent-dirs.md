# ADR 0010 — Auto-create parent directories for file mounts

**Status:** Accepted (2026-05-07).

## Context

ADR 0005 added tilde expansion for `Mount(sandbox=Path("~/.npm"))` so users can target the agent user's home directly. A subtle gap remains for *file* mounts (host file → in-container file) when the in-container parent directory doesn't exist:

- `Mount(host=cache/.npmrc, sandbox=Path("/home/agent/.npmrc"))` works because `/home/agent` exists in the eden Dockerfile.
- `Mount(host=cache/gh-config.yml, sandbox=Path("~/.config/gh/hosts.yml"))` expands to `/home/agent/.config/gh/hosts.yml`. Docker's bind-mount creates the chain `/.config/gh/` as **root-owned**. The agent user (UID 1000) can't write further into it; `gh auth login` fails inside the container with EACCES.

Two options were considered:

1. **Document the limitation** — tell users to mount the parent directory instead of the file, or to bake the parent into their Dockerfile. Pushes the work onto every user.
2. **Auto-create the parent dir at container start, owned by the configured `container_uid:container_gid`.** Eden runs `<binary> exec --user 0:0 <container_id> mkdir -p <parent> && chown <uid>:<gid> <parent>` after `<binary> run` succeeds, for every file mount whose parent doesn't already match those attributes. One-time cost per container start; invisible to users.

## Decision

Adopt option 2.

- After the container is started and before `OnSandboxReady` hooks run, eden walks the configured mounts (provider's plus per-call) and identifies file mounts — those where the host path is a regular file. For each, eden computes the in-container parent (after tilde expansion).
- For each parent path that lives **under** `SANDBOX_HOMEDIR` (i.e. a path the agent user is supposed to own) and that isn't already accounted for, eden runs:
  ```
  <binary> exec --user 0:0 <container_id> sh -c 'mkdir -p "$1" && chown "$2:$3" "$1"' -- <parent> <uid> <gid>
  ```
  The `--user 0:0` override runs the helper as root regardless of the container's default user; the `chown` then transfers ownership to the configured agent user.
- Parents outside `SANDBOX_HOMEDIR` (e.g. `/etc/...`) are not auto-created. Mounting somewhere outside the agent's home is a deliberate signal that the user knows what they're doing; eden won't `mkdir -p /etc/foo` on their behalf.
- Failures to create / chown a parent surface as `ContainerStartFailed` with the helper's stderr, after the run-and-mounts phase but before any user code runs. Users see "you tried to mount a file at `/home/agent/.config/gh/hosts.yml` but eden couldn't prepare its parent dir" rather than a confused EACCES from the agent five seconds in.

## Consequences

- File mounts under `~/...` "just work" without users needing to bake the directory chain into their Dockerfile.
- The parent-prep step adds one `<binary> exec` call per file mount, executed at container start. For typical setups (0–3 file mounts) the cost is well under 100ms total. Directory mounts skip the step entirely (docker handles their parent creation cleanly because the mount target is the directory itself).
- The check uses `host.is_file()`, not the mount kind in eden's API (eden's `Mount` doesn't currently distinguish file vs directory). False positives would only happen if a host file shares a name with a directory the user expected; that would also be a configuration bug.
- The `--user 0:0` override is a strict requirement of the design. Containers built with a non-root USER directive still need root for the `mkdir`. Eden already runs `--user uid:gid` for the main process; this is a one-shot helper that doesn't affect the agent.
- The chown target is the configured `container_uid:container_gid` from ADR 0005. If a user passes mismatched values (e.g. `container_uid=1000` but the image's USER UID is 1500 with no override), eden's pre-flight check from ADR 0005 catches it first.
- Edge case: if a parent directory exists in the image with non-root ownership but a different UID, the chown silently corrects it. Acceptable trade — the configured UID is the source of truth.

## See also

- ADR 0005 — UID alignment + tilde expansion this depends on.
- Upstream 9bf43df (the "auto-create parent dirs for file mounts under /home/agent" commit).
- `eden/providers/_impl/container.py` — `_create()` is the implementation site.

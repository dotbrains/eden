# ADR 0005 — Container UX hygiene: UID alignment, SELinux, tilde mounts

**Status:** Accepted (2026-05-07).

## Context

Eden's `docker` and `podman` providers bind-mount the host worktree into the container. Three independent papercuts surfaced once eden moved beyond root-only Linux setups:

- **File-ownership mismatch** — when the agent runs as the image's default user (often UID 1000) but the host user is a different UID (501 on macOS, 1000+N on multi-user Linux boxes), files written through the bind mount land owned by an in-container user that doesn't exist on the host. The host user can read them but can't `git add`.
- **SELinux relabel** — Fedora / RHEL / CentOS hosts enforce SELinux by default. Bind mounts without a `:z` (shared) or `:Z` (private) label suffix get the `system_u:object_r:default_t` context, which the container's domain isn't allowed to write. The agent's first `mkdir` fails with EACCES, with no obvious clue why.
- **In-container path ergonomics** — agent caches (`~/.npm`, `~/.cache/pip`, `~/.config/gh`) live under the in-container home directory. Asking users to spell `/home/agent/.npm` in their `Mount(sandbox=...)` couples the user's call site to eden's internal `useradd` choice.

Three options for each were considered. For UID specifically:

1. Pre-flight `image inspect` and refuse to start if the image's USER UID disagrees with the configured UID. Surfaces the misconfiguration before any side effect.
2. Recursive `chown` on container start. Fixes the symptom but slow on large worktrees and silent about the root cause.
3. Punt entirely and document the build-arg dance.

## Decision

Adopt option 1 for UID. Add `container_uid` / `container_gid` to `docker()` and `podman()`; default to the host's `os.getuid()` / `os.getgid()`. A pre-flight `<binary> image inspect --format '{{.Config.User}}'` raises `ImageUidMismatch` on numeric divergence (with a hint to rebuild with `--build-arg AGENT_UID=...`). Non-numeric or empty USER directives silently skip the check — `--user` still wins at runtime.

For SELinux: append a relabel suffix to **every** bind-mount spec. Default `selinux_label="z"` (shared); `"Z"` for private; `None` to disable. Linux without SELinux ignores the suffix; macOS and Windows treat it as a no-op. This is the right cost/benefit balance: zero overhead when not needed, prevents a class of mystery-EACCES bug when needed.

For tilde mounts: `Mount(sandbox=Path("~/.npm"))` expands using the provider's `SANDBOX_HOMEDIR` (default `Path("/home/agent")`). Providers without a homedir raise `ValueError` at mount-resolution time so the failure surfaces at start, not as a confused `mkdir` later.

The blank Dockerfile template is updated to declare `ARG AGENT_UID=1000 AGENT_GID=1000` and `useradd` an `agent` user; `eden init` prints a `--build-arg AGENT_UID=$(id -u)` invocation that aligns to the host.

## Consequences

- New eden setups work out of the box on any UID layout. `docker run --user 1000:1000` against a stock image without a USER directive still works (Linux runs the process under the unmapped UID; bind-mount writes land with the right owner).
- Existing eden setups that built images without the build-arg get a clear `ImageUidMismatch` error pointing at the fix instead of a silent permission drift.
- The SELinux relabel applies to every bind, including the implicit `/workspace` mount and any user-supplied caches. On non-SELinux hosts the suffix is harmless.
- Tilde expansion couples the API to the convention "the agent user's home is `/home/agent`". This is enforced by the blank template; users with custom Dockerfiles that pick a different homedir need to either pass absolute paths or override `SANDBOX_HOMEDIR`. Acceptable trade for the ergonomics gain.
- File mounts whose tilde-expanded parent didn't exist in the image (e.g. `~/.config/gh/hosts.yml` when `/home/agent/.config` is empty) used to land with a root-owned parent the agent couldn't write into. ADR 0010 closes that gap — eden now `mkdir -p` + `chown` the parent at container start.

## See also

- Upstream ADR-0014 (UID alignment).
- [`docs/sandbox-providers.md` — docker provider parameters](../sandbox-providers.md#docker).
- `eden/providers/_impl/container.py` — `_check_image_uid`, `_mount_spec`, `_expand_sandbox_tilde`.

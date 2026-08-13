# Sandbox and Worktree Errors

Detailed reference for provider and worktree error families. See [Errors](errors.md) for the top-level `EdenError` hierarchy and public error classes.

---

## Sandbox errors

Live in `eden/sandboxes/errors.py`. All inherit `SandboxError` (which inherits `EdenError`). These are not re-exported from the top-level `eden` package — import from `eden.sandboxes.errors` if you need to catch a specific one. Catching `EdenError` works for all of them.

### `SandboxError`

Base for sandbox-provider errors. Catch when you do not care which provider stage failed.

### `ProviderUnavailable`

The provider needs a binary or credential that is not available. Carries `provider: str` and `binary: str`. Raised at `create()` time, not at factory time, so users can import providers without credentials in scope.

Examples: `docker`/`podman` binary not on `PATH`; `DAYTONA_API_KEY` unset; `VERCEL_TOKEN` unset.

**Recovery:** install the missing binary, set the missing env var, or pass the credential to the provider factory directly.

### `ImageNotFound`

`docker run` reported the image is not present locally. Carries `image: str` and `stderr: str`.

**Recovery:** build or pull the image (`docker build -t <name> .` / `docker pull <name>`) before running.

### `ContainerStartFailed`

`docker run` started the container but the container exited non-zero before becoming usable. Carries `image`, `exit_code`, `stderr`.

**Recovery:** check the `stderr` for the failure cause; usually a missing entrypoint, broken image, or insufficient mount permissions.

### `ContainerStartTimeout`

The docker/podman `create()` sequence (image inspect, UID check, `<binary> run`, mount-parent prep) exceeded its shared deadline — either a step's own `subprocess.run(timeout=...)` expired, or the remaining budget ran out between steps. Carries `binary` and `timeout`.

**Recovery:** check for a stuck daemon or slow image pull (`docker ps`/`docker info`), then pass a larger `create_timeout=` to `docker()`/`podman()` if the host is just slow.

### `ExecFailed`

`handle.exec(cmd)` returned a non-zero exit code (raised when the caller invokes `ExecResult.check()`, or from internal cloud-provider operations). Carries `result: ExecResult` and `argv_or_cmd: str`.

**Recovery:** inspect `e.result.stderr` and `e.result.exit_code`; fix the command or the sandbox state.

### `ExecTimeout`

`handle.exec(cmd, timeout=...)` exceeded its timeout. Carries `cmd`, `timeout`, `partial_stdout`, `partial_stderr`.

**Recovery:** raise the per-call timeout, or shorten the command.

### `MountConfigError`

Docker / Podman rejected a bind-mount configuration before container startup. The current typed case is a single-file mount whose sandbox-side parent is outside `/home/agent`; Eden only auto-creates missing file-mount parents under the agent home.

**Recovery:** mount the parent directory instead, or rebuild the image with that parent directory pre-created.

### `MountHostMissing`

Docker / Podman rejected a bind mount because the host-side path did not exist after `~` expansion.

**Recovery:** create the host path before running Eden, or remove the mount.

### `UnsupportedStrategy`

The chosen `BranchStrategy` is not supported by this provider. Carries `provider: str` and `strategy: StrategyTag`.

**Recovery:** pick a different `branch_strategy` (e.g. `BranchStrategy.merge_to_head()`) or switch providers.

## Worktree errors

Live in `eden/worktree/errors.py`. All inherit `WorktreeError` (which inherits `EdenError`). Not re-exported from the top-level package — import from `eden.worktree.errors` if you need to catch a specific one.

### `WorktreeError`

Base for worktree-creation failures.

### `WorktreeLocked`

Another `eden` process holds the per-branch advisory lock. Carries `lock_path: Path` and `holder_pid: int`. Stale locks (PID dead) are wiped automatically on the next acquisition; this exception only fires when the holder is alive.

**Recovery:** wait for the other run to finish, kill it, or use a different branch.

### `DirtyHostBlocked`

`BranchStrategy.head()` requires a clean host repo, but yours has uncommitted changes. Carries `host_repo_path: Path` and `dirty_files: tuple[str, ...]` (first 10).

**Recovery:** commit, stash, or discard the dirty files; or switch to `BranchStrategy.merge_to_head()` / `BranchStrategy.named()`, both of which work with a dirty host.

### `BranchExists`

`BranchStrategy.named(branch=...)` was called with a branch that already exists in the host repo. Carries `branch: str`, plus `conflict_path: Path | None` and `hint: str | None` when the branch is already checked out in another worktree.

**Recovery:** delete the existing branch, pick a different name, or switch to `merge_to_head()` (which generates a fresh `eden/<slug>` name). If `conflict_path` is set, switch that worktree to a different branch before rerunning.

### `GitCommandFailed`

A `git` subprocess invoked by `eden.worktree` exited non-zero. Carries `argv: tuple[str, ...]`, `exit_code: int`, `stderr: str`. Usually wraps a deeper repository issue (corrupted index, missing remote, permission problem).

**Recovery:** read `e.stderr`; fix the underlying repo issue and rerun.

## See also

- [Errors](errors.md) — top-level public error classes and recovery matrix.
- [Sandbox providers](sandbox-providers.md) — which provider raises which `SandboxError` subclass.
- [How it works](how-it-works.md) — where each error fires in the iteration loop.

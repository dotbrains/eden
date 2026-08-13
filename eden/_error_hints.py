"""Recovery-hint synthesis for errors that do not carry hints."""

from __future__ import annotations

from eden.errors import EdenError


def provider_hint(error: EdenError) -> str | None:
    try:
        from eden.sandboxes.errors import (
            ContainerStartFailed,
            ContainerStartTimeout,
            ExecFailed,
            ExecTimeout,
            ImageNotFound,
            ImageUidMismatch,
            MountConfigError,
            MountHostMissing,
            ProviderUnavailable,
            UnsupportedStrategy,
        )
    except ImportError:  # pragma: no cover - sandboxes is in-tree
        return None

    if isinstance(error, ProviderUnavailable):
        binary = getattr(error, "binary", "the runtime")
        provider = getattr(error, "provider", "")
        if provider == "docker":
            return "Is Docker running? Install Docker Desktop or `brew install --cask docker`."
        if provider == "podman":
            return (
                "Is Podman installed and running? `brew install podman` "
                "then `podman machine start`."
            )
        return f"Install {binary!r} and ensure it is on PATH, then re-run."
    if isinstance(error, ImageNotFound):
        image = getattr(error, "image", "<image>")
        return (
            f"Build the image first: `docker build -t {image} -f .eden/Dockerfile .`. "
            f"Or pull it: `docker pull {image}`."
        )
    if isinstance(error, ContainerStartFailed):
        return (
            "The container exited immediately. Check the image's ENTRYPOINT / "
            "CMD and confirm Docker daemon is healthy (`docker ps`)."
        )
    if isinstance(error, ContainerStartTimeout):
        binary = getattr(error, "binary", "the runtime")
        return (
            f"Check `{binary} ps`/`{binary} info` for a stuck daemon or a slow "
            "image pull, then pass a larger `create_timeout=` if the host is just slow."
        )
    if isinstance(error, ImageUidMismatch):
        return (
            "Rebuild the image with `--build-arg AGENT_UID=<host-uid> "
            "AGENT_GID=<host-gid>` or pass matching `container_uid=`/`container_gid=`."
        )
    if isinstance(error, MountConfigError):
        return (
            "Move the mount target inside the sandbox HOME, or pre-create the "
            "parent directory in your image."
        )
    if isinstance(error, MountHostMissing):
        return "Create the host path before running Eden, or remove the mount."
    if isinstance(error, ExecTimeout):
        timeout = getattr(error, "timeout", None)
        if timeout:
            return (
                f"Increase `Timeouts.iteration_step` or the per-call "
                f"timeout (currently {timeout}s)."
            )
        return "Increase the per-call timeout or `Timeouts.iteration_step`."
    if isinstance(error, ExecFailed):
        return "Inspect the captured stderr; rerun with `Logging.file(...)` to persist it."
    if isinstance(error, UnsupportedStrategy):
        return "Pick a strategy this provider supports, or switch to docker/no_sandbox."
    return None


def worktree_hint(error: EdenError) -> str | None:
    try:
        from eden.worktree.errors import (
            BranchExists,
            DirtyHostBlocked,
            GitCommandFailed,
            WorktreeLocked,
        )
    except ImportError:  # pragma: no cover - worktree is in-tree
        return None

    if isinstance(error, WorktreeLocked):
        pid = getattr(error, "holder_pid", None)
        return (
            f"Another eden process (pid {pid}) is using this worktree. "
            "Wait for it, or delete the stale lockfile."
        )
    if isinstance(error, DirtyHostBlocked):
        return "Commit or stash the listed files, or pass `allow_dirty=True`."
    if isinstance(error, BranchExists):
        return (
            "Pass `branch_strategy=BranchStrategy.named(<unique-name>)` "
            "or delete the existing branch."
        )
    if isinstance(error, GitCommandFailed):
        return "Inspect the failing git command; ensure the repo is healthy (`git fsck`)."
    return None


__all__ = ["provider_hint", "worktree_hint"]

# Podman sandbox provider

Detailed reference for Eden's rootless Podman bind-mount provider. See [Container sandbox providers](container-sandbox-providers.md) for shared Docker/Podman behavior and [Sandbox providers](sandbox-providers.md) for the provider matrix.

---

## `podman`

```python
from eden.sandboxes.podman import provider as podman_provider

run(..., sandbox=podman_provider(image="my-image:latest"))
```

### Signature

Identical to `docker` plus `userns`:

```python
def provider(
    *,
    image: str | None = None,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | tuple[str, ...] | None = None,
    container_uid: int | None = None,
    container_gid: int | None = None,
    selinux_label: Literal["z", "Z"] | None = "z",
    devices: tuple[str, ...] | None = None,
    cpus: float | None = None,
    groups: tuple[str | int, ...] | None = None,
    userns: Literal["keep-id"] | None = "keep-id",
    max_output_tail_chars: int = 64 * 1024,
    create_timeout: float = 120.0,
) -> SandboxProvider: ...
```

### What it does

Same lifecycle as `docker`, but invokes `podman` instead. It is rootless by
default and suitable for environments without a privileged daemon.

Mount formatting, Windows-path handling, SELinux relabeling, and single-file
mount parent validation match Docker. By default Eden also passes
`--userns=keep-id:uid=<uid>,gid=<gid>` so rootless Podman maps the host user to
the configured in-container user without runtime `chown`. Pass `userns=None`
for rootful Podman or a custom namespace setup.

### When to use

- Same use cases as `docker`, but on hosts where Docker is unavailable or
  rootless isolation is preferred.
- CI environments that ship `podman`, such as RHEL-family runners.

### When not to use

- macOS hosts without a Podman machine. Eden does not auto-provision the VM;
  configure it yourself first.

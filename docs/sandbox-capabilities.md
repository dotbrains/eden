# Sandbox capabilities, ports, and background exec

Eden declares what each built-in sandbox provider supports via
`capabilities_for(provider)`. Optional handle methods are detected with
`hasattr` — see [ADR 0019](../adr/0019-sandbox-capabilities.md).

## Capability matrix

| Provider | `ports` | `background_exec` |
|----------|---------|-------------------|
| `no_sandbox` | dynamic | yes |
| `isolated` | dynamic | yes |
| `docker` / `podman` | static (pre-declare) | yes |
| `daytona` | dynamic | yes |
| `vercel` | static (pre-declare) | yes |
| `forkd` | unsupported | no |

`forkd` deliberately omits both: the public forkd SDK has no port-forward or
background-exec surface (only an internal guest-agent wire protocol).

## Port exposure

Handles that support ports implement `expose_port(port, public=False)` and
return `ExposedPort(port, url, public)`.

**Dynamic** providers (`no_sandbox`, `isolated`, `daytona`) accept runtime
calls without pre-declaration. **Static** providers (`docker`, `podman`,
`vercel`) require declaring ports at factory time:

```python
from eden.sandboxes import docker

sandbox = docker.provider(ports=(3000, 8080)).create(...)
handle = sandbox  # after create_sandbox / orchestrator wiring
exposed = handle.expose_port(3000)
print(exposed.url)  # http://127.0.0.1:<mapped>
```

Calling `expose_port` for an undeclared port on docker/podman raises
`PortNotDeclared`.

Daytona `public=True` preview URLs require `daytona.provider(public=True)` at
create time; otherwise callers must attach the `x-daytona-preview-token` header
when fetching the returned URL.

## Background processes

Handles that support background exec implement `start(cmd, cwd=None, env=None)`
and return a `SandboxProcess`:

```python
proc = handle.start("python -m http.server 8000")
for line in proc.output():
    print(line)
result = proc.wait(timeout=30.0)
proc.kill()  # when needed
```

`ProcessStatus` reports `state` (`running`, `exited`, `failed`, `killed`) and
`exit_code`. Daytona `kill()` deletes the whole process **session** (not just
one command); Vercel kills a single detached command.

## See also

- [sandbox-providers.md](sandbox-providers.md) — provider overview.
- [python-api-capabilities.md](python-api-capabilities.md) — public types.

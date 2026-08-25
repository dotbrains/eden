# Python API: capabilities

Public exports for optional sandbox capabilities. Usage examples live in
[sandbox-capabilities.md](sandbox-capabilities.md).

## `ProviderCapabilities`

Frozen dataclass with `ports: PortSupport` and `background_exec: bool`.

## `PortSupport`

`Literal["dynamic", "static", "unsupported"]` — how port exposure works for a
provider.

## `capabilities_for(provider)`

Return `ProviderCapabilities` for a `SandboxProvider`. Unknown/custom
providers receive `ports="unsupported"` and `background_exec=False`.

## `ExposedPort`

Frozen dataclass: `port`, `url`, `public`.

## `ProcessStatus`

Frozen dataclass: `state` (`ProcessState`), `exit_code`.

## `SandboxProcess`

Protocol for background processes: `status()`, `output()`, `write()`, `wait()`,
`kill()`.

## `SupportsPorts`

Optional handle Protocol — detected via `hasattr(handle, "expose_port")`.
Method: `expose_port(port, public=False) -> ExposedPort`.

## `SupportsBackgroundExec`

Optional handle Protocol — detected via `hasattr(handle, "start")`.
Method: `start(cmd, cwd=None, env=None) -> SandboxProcess`.

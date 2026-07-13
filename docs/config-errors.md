# Configuration errors

Detailed reference for `ConfigError` and its subclasses. See
[Top-level errors](top-level-errors.md) for the other public `EdenError`
subclasses.

## `ConfigError`

Base for problems detected before any side effect: bad arguments, environment,
or `cwd`. If you see one of these, nothing was created and nothing was started.

## `InvalidOptions`

Generic kwarg-validation failure. Carries `code`, `message`, `hint`, `cause`.
Raised when the orchestrator detects mutually-exclusive or missing-required
arguments to `run(...)` (for example, supplying both `prompt` and `prompt_file`).

**Recovery:** fix the call site.

## `PromptError`

Raised when prompt rendering fails: missing `{name}` arg substitution, malformed
`!\`shell\`` block, unreadable `prompt_file`, etc. Carries `code`, `message`,
`hint`, `cause`.

**Recovery:** inspect `e.code` (for example, `prompt.missing_arg`,
`prompt.shell_failed`) and fix the prompt source.

## `EnvMergeError`

Conflicting `env` overrides between caller, agent, and provider. Default
`code="config.env_merge"`.

**Recovery:** drop the conflicting key from one layer or rename it.

## `CwdError`

The `cwd=` argument is missing, not a directory, or not inside a git repo.
Default `code="config.cwd"`.

**Recovery:** pass a valid path inside a git repo. `cd` into the repo before
running, or pass `cwd=Path("/abs/path/to/repo")`.

## `FloxEnvError`

An agent declared a `flox_env` that cannot be activated: the directory has no
`.flox/env/manifest.toml`, or the `flox` binary is not on `PATH`. Raised before
the first iteration so a dangling reference surfaces immediately rather than
mid-run. Default `code="config.flox_env"`. See
[Agent Flox runtime](agent-flox-runtime.md).

**Recovery:** point `flox_env` at a directory containing
`.flox/env/manifest.toml`, install Flox so the env can be activated, or set
`EDEN_ALLOW_NO_FLOX=1` to run without it (Windows / CI smoke tests). Drop the
`flox_env` declaration to restore the prior host-toolchain behavior.

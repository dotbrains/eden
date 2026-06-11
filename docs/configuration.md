# Configuration

Eden reads configuration from three places: function arguments to `run()`, environment variables (only for cloud sandbox providers), and the optional [`Logging`](python-api.md#configuration-types) / [`Timeouts`](python-api.md#configuration-types) dataclasses.

---

## Environment variables

Eden itself reads environment variables only inside the **cloud sandbox providers**. Every variable is also a keyword argument on the provider factory — the env var is just a fallback. If both are unset and the provider needs the value, the provider raises `ProviderUnavailable` at sandbox-create time (not at factory time).

| Variable | Read by | Required? | Effect |
|---|---|---|---|
| `DAYTONA_API_KEY` | `eden.sandboxes.daytona.provider` | yes (or pass `api_key=`) | API key for the Daytona cloud sandbox. |
| `DAYTONA_ORGANIZATION_ID` | `eden.sandboxes.daytona.provider` | no | Sets the `X-Daytona-Organization-ID` header on Daytona REST calls. |
| `DAYTONA_API_URL` | `eden.sandboxes.daytona.provider` | no | Override the Daytona API endpoint. Defaults to `https://api.daytona.io`. |
| `VERCEL_TOKEN` | `eden.sandboxes.vercel.provider` | yes (or pass `access_token=`) | API token for the Vercel sandbox provider. |
| `VERCEL_TEAM_ID` | `eden.sandboxes.vercel.provider` | no | Sent as `?teamId=…` on every Vercel REST call. |
| `VERCEL_API_URL` | `eden.sandboxes.vercel.provider` | no | Override the Vercel API endpoint. Defaults to `https://api.vercel.com`. |

Read source: `eden/sandboxes/daytona/__init__.py`, `eden/sandboxes/vercel/__init__.py`.

### `.eden/.env` auto-loading

If `<cwd>/.eden/.env` exists, `run()`, `create_sandbox()`, and `interactive()` parse it and merge its values into the env passed to the sandbox. The file is optional — projects opt in by creating it. Precedence is:

1. `.eden/.env` (lowest) — declared values flow in.
2. `env={...}` keyword argument on the call (highest) — silently overrides keys also set in the file.

A collision between `.eden/.env` and a provider's fixed env still raises `EnvMergeError`, so a mis-wired provider is loud, not silent.

Escape sequences in double-quoted values (`\n`, `\r`, `\t`, `\\`) are unescaped via [`python-dotenv`](https://pypi.org/project/python-dotenv/), so gateway tokens with embedded newlines forward into the container correctly. Single-quoted values are literal.

The `eden init` blank template seeds `.eden/.env.example` listing the variables the chosen agent expects (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, …). Copy it to `.eden/.env` and fill in your keys.

Read source: `eden/env/_dotenv.py`, `eden/orchestrator/_setup.py`.

### Variables Eden does not read

The agent CLIs that Eden orchestrates (e.g. `claude-code`, `codex`) read their own env vars — `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. Those are the agent's contract, not Eden's.

When `run()` invokes a hook or an agent process, it merges the host process environment with any per-run / per-hook `env=` mapping (which already includes the `.eden/.env` values described above). Eden does not interpret the merged environment beyond passing it through.

## `Timeouts`

Frozen dataclass passed as `run(timeouts=...)`. See [python-api.md#configuration-types](python-api.md#configuration-types) for fields. Defaults (`hook_step=60.0`, `iteration_step=None`, `copy_to_worktree=60.0`, `git_setup=60.0`) suit most workloads — override only when you have a specific reason. `iteration_step=None` defers to the agent's `idle_timeout`; raise `git_setup` when worktree creation runs against slow filesystems (NFS, networked volumes) or very large repos.

## `Logging`

Frozen dataclass passed as `run(logging=...)` controlling JSONL stream-event logging. The simplest forms are the `Logging.file(...)` and `Logging.stdout(...)` factories:

```python
from eden import Logging, run

run(..., logging=Logging.file("run.jsonl", level="info"))
run(..., logging=Logging.stdout())  # CI-friendly: log lines go to the job log
```

Fields:

- `type` — `"file"` (default sink) or `"stdout"`.
- `path` — `Path` to write logs to. Required for `"file"`, must be omitted for `"stdout"`.
- `level` — one of `"debug"`, `"info"` (default), `"warn"`, `"error"`.

When set, every [`StreamEvent`](python-api.md#streamevent) the orchestrator emits is written to the sink as a JSON line. For the file sink, `run()` returns the resolved path back as `RunResult.log_file_path`; for the stdout sink, `RunResult.log_file_path` is `None`.

Read source: `eden/logging/_config.py`.

## Sandbox-specific configuration

Each sandbox provider takes its own keyword arguments — `image=` for `docker`/`podman`, `api_key=`/`organization_id=`/`base_url=` for `daytona`, `access_token=`/`team_id=`/`base_url=`/`runtime=` for `vercel`, etc. See [sandbox-providers.md](sandbox-providers.md) for the full provider matrix.

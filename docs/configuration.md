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

### Variables Eden does not read

The agent CLIs that Eden orchestrates (e.g. `claude-code`, `codex`) read their own env vars — `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. Those are the agent's contract, not Eden's. The `eden init` blank template includes a `.env.example` listing them as a convenience; see [templates.md](templates.md).

When `run()` invokes a hook or an agent process, it merges the host process environment with any per-run / per-hook `env=` mapping. Eden does not interpret the merged environment beyond passing it through.

## `Timeouts`

Frozen dataclass passed as `run(timeouts=...)`. See [python-api.md#configuration-types](python-api.md#configuration-types) for fields. Defaults (`hook_step=60.0`, `iteration_step=None`) suit most workloads — override only when you have a specific reason. `iteration_step=None` defers to the agent's `idle_timeout`.

## `Logging`

Frozen dataclass passed as `run(logging=...)` controlling JSONL stream-event logging. The simplest form is the `Logging.file(...)` factory:

```python
from eden import Logging, run

run(..., logging=Logging.file("run.jsonl", level="info"))
```

Fields:

- `type` — currently always `"file"` (one sink shipped in v0.1).
- `path` — `Path` to write logs to. Required.
- `level` — one of `"debug"`, `"info"` (default), `"warn"`, `"error"`.

When set, every [`StreamEvent`](python-api.md#streamevent) the orchestrator emits is written to the file as a JSON line. `run()` returns the resolved path back as `RunResult.log_file_path`.

Read source: `eden/logging/_config.py`.

## Sandbox-specific configuration

Each sandbox provider takes its own keyword arguments — `image=` for `docker`/`podman`, `api_key=`/`organization_id=`/`base_url=` for `daytona`, `access_token=`/`team_id=`/`base_url=`/`runtime=` for `vercel`, etc. See [sandbox-providers.md](sandbox-providers.md) for the full provider matrix.

# REST errors

Cloud-provider REST failures from `daytona`, `vercel`, and future REST-backed
providers. See [Top-level errors](top-level-errors.md) for the other public
error classes.

## `RestError`

Base for non-2xx responses from cloud-provider REST APIs. Carries the standard
fields plus:

- `status: int` - HTTP status (`0` for connection-level failures with no HTTP
  response).
- `body: str` - response body if available.
- `url: str` - request URL.

Default `code="rest.error"`. Catch this at the orchestrator boundary; never let
the provider's `requests.RequestException` leak through.

## `RestAuthError`

401 / 403: Bearer token rejected or insufficient permissions. Default
`code="rest.auth"`.

**Recovery:** rotate or refresh the API token (`DAYTONA_API_KEY`,
`VERCEL_TOKEN`, etc.); verify the org/team scope.

## `RestNotFoundError`

404: sandbox, project, or file does not exist on the cloud side. Default
`code="rest.not_found"`. Notably, `daytona`/`vercel` `close()` swallows this for
the sandbox-delete call (idempotent teardown).

**Recovery:** the resource is gone; treat as terminal unless the resource ID is
known-stale, in which case stop using it.

## `RestRateLimited`

429: server-side rate-limit; eden's automatic retries were exhausted. Default
`code="rest.rate_limited"`.

**Recovery:** retry with backoff, parallelize fewer runs, or upgrade the
provider plan.

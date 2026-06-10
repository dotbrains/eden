Use `.venv/bin/python -m mypy eden tests` for type checking (mypy is pinned in `pyproject.toml`'s `[dev]` extras; `pre-commit install` wires the same version into the git hook).

Use `.venv/bin/python -m pytest tests/ -q` to run unit + e2e tests. Linux-only integration tests live behind `-m integration`.

On Linux/macOS, `flox activate` (env under `.flox/`) provisions the toolchain and builds `.venv`; the `.venv/bin/...` commands above run unchanged inside it. Windows has no Flox — use the manual `pip install -e ".[dev]"` path.

Check [`AGENTS.md`](./AGENTS.md) first for the full project overview, architecture map, sandbox/agent conventions, and contribution constraints. Skim [`docs/python-api.md`](./docs/python-api.md) for the public API contract before changing anything in `eden/__init__.py` — `tests/unit/test_docs_consistency.py` enforces coverage of public exports.

For user-facing changes, append an entry to [`CHANGELOG.md`](./CHANGELOG.md). Follow conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`) on the commit subject; this drives the changelog format.

When changing public-facing behavior, check [`README.md`](./README.md) and the relevant `docs/*.md` to see if documentation needs updating.

## Agent skills

### Architecture decisions

Architectural choices live as numbered files under [`docs/adr/`](./docs/adr/). Read the relevant ADR before changing core orchestration, providers, agent layout, output parsing, interactive sessions, tracing, or session storage.

### Sandbox providers

Seven in-tree providers live under [`eden/sandboxes/`](./eden/sandboxes/) and follow the Protocols in [`eden/providers/_protocols.py`](./eden/providers/_protocols.py). [`docs/custom-providers.md`](./docs/custom-providers.md) documents the extension seam; [`docs/sandbox-providers.md`](./docs/sandbox-providers.md) is the user-facing matrix.

### Agents

Each agent factory lives in its own subpackage under [`eden/agents/`](./eden/agents/) and implements the `Agent` Protocol (`build_command(ctx)` plus optional `parse_stream(line)`). [`docs/agents.md`](./docs/agents.md) is the user-facing reference; `cli_agent` is the generic line-streaming adapter for new wrappers.

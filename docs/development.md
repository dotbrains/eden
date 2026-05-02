# Development

Local setup, repo layout, test markers, lint and type gates, and how to publish a release.

---

## Local setup

```bash
git clone https://github.com/dotbrains/eden.git
cd eden
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

The `[dev]` extra pulls in `pytest`, `pytest-cov`, `mypy`, `ruff`, `build`, and `types-requests`. Eden requires Python 3.11+; CI tests against 3.11, 3.12, and 3.13.

## Repo layout

```
eden/
├── _types.py              # public dataclasses (RunResult, Iteration, Commit, Usage, Timeouts)
├── _version.py            # version string from importlib.metadata
├── abort/                 # AbortController, AbortSignal, Aborted
├── agents/                # one subpackage per agent factory + the cli_agent generic
├── cli/                   # `eden init` + `eden version`
├── env/                   # environment-variable merging
├── errors.py              # top-level error hierarchy (EdenError and friends)
├── lifecycle/             # hook types + hook runner
├── logging/               # log routing
├── orchestrator/          # `run()` + `create_worktree()` + iteration loop
├── prompt/                # PromptSource, args, shell blocks, built-ins
├── providers/             # SandboxProvider Protocol + factory helpers
├── sandboxes/             # one subpackage per sandbox provider
├── session/               # session JSONL capture
├── streaming/             # StreamEvent + line buffer
└── worktree/              # git worktree create + lock
```

See [Python API](python-api.md) for the full public surface, [Sandbox providers](sandbox-providers.md) for what lives in `sandboxes/`, and [Agents](agents.md) for what lives in `agents/`.

## Test markers

`pyproject.toml` declares four markers; tests opt in via `pytestmark = pytest.mark.<marker>`.

```bash
.venv/bin/pytest -m unit           # fast, no external services
.venv/bin/pytest -m e2e            # in-process orchestrator runs with simulated_agent
.venv/bin/pytest -m integration    # real Docker/Podman/cloud; Linux only in CI
.venv/bin/pytest -m smoke          # end-to-end smoke tests
.venv/bin/pytest -m "unit or e2e"  # what CI runs by default on every OS/Python
```

## Quality gates

The CI workflow (`.github/workflows/ci.yml`) installs the package with the `[dev]` extra and runs all of these on each push and pull request, across the matrix `{ubuntu-latest, macos-latest, windows-latest}` x `{3.11, 3.12, 3.13}`:

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
pytest -v -m "unit or e2e" --cov=eden --cov-fail-under=70
```

The `integration` marker runs as a separate step on Linux only.

The coverage gate is **70%**. Current actual coverage is **93%**. The full suite is **451 tests** passing.

## Releasing a new version

1. Bump `pyproject.toml` `version` (semver).
2. Commit: `chore: bump version to vX.Y.Z`.
3. Push to `main`. CI must be green.
4. Tag from `main`:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. The `.github/workflows/release.yml` workflow runs automatically and publishes to PyPI via Trusted Publishing. No long-lived tokens are required.

### First-time setup of PyPI Trusted Publishing

Required once, before the first publish:

1. Visit https://pypi.org/manage/project/eden-agent/settings/publishing/ (project owner only).
2. Add a new pending publisher:
   - Owner: `dotbrains`
   - Repository: `eden`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. Save. The first tag push will succeed.

Repeat the steps on https://test.pypi.org for the `testpypi` environment if you want to dry-run release candidates.

### Test releases

Tag with a `-rc` suffix (e.g., `v0.1.0-rc1`) to publish to TestPyPI instead of production PyPI. The release workflow's tag-pattern logic routes `-rc` tags to the test repository.

## Contributing

- Open an issue first for non-trivial changes.
- Follow conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`.
- All checks (ruff format, ruff check, mypy --strict, pytest) must pass before merge.
- New public exports must be documented in [docs/python-api.md](python-api.md) — enforced by `tests/unit/test_docs_consistency.py`.
- New error classes belong in the hierarchy described in [errors.md](errors.md).
- New sandbox providers should follow the Protocol described in [custom-providers.md](custom-providers.md).
- New agents follow the one-agent-per-subpackage convention in `eden/agents/` (see [agents.md](agents.md)).

# Eden Phase 7 — Docs & Release Design

**Status:** Approved design.

**Predecessors:** Phases 1–6 (skeleton, sandbox foundations, orchestration, claude_code, provider parity local + daytona + vercel, additional agents, CLI scaffolder). Latest commit on main: `face7a3`.

**Goal:** Rebuild `docs/` from scratch, rewrite `README.md` for the v0.1.0 release, add a PyPI publish workflow, and tag `v0.1.0`. Final phase of the Eden Python rewrite roadmap.

**Out of scope (deferred to v0.2+):**
- Sphinx / mkdocs site or other static-site tooling.
- Auto-generated API reference (`pdoc`/`mkdocstrings`).
- Real-binary integration tests for `codex`/`opencode`/`pi` (gated by `shutil.which`).
- Templates beyond `blank` for `eden init` (the scaffolder shipped with one in Phase 6).
- Performance benchmark vs the Rust prototype (master-spec risk-mitigation note; YAGNI for v0).

---

## 1. Public surface added

No new Python API. Phase 7 freezes the surface that landed in Phases 1–6:

```python
from eden import (
    # orchestrator
    run, create_worktree,
    # types
    RunResult, Iteration, Commit, Usage, Timeouts, Mount, FinalizeResult,
    BranchStrategy, StreamEvent, Logging,
    # cancellation
    AbortController, AbortSignal, Aborted,
    # agents
    Agent, IterationContext,
    simulated_agent, claude_code, codex, opencode, pi, cli_agent,
    # lifecycle
    Hook, HookPhase, Hooks, HostHooks, SandboxHooks,
    # providers (Protocol re-export)
    IsolatedSandboxHandle,
    # errors
    EdenError, ConfigError, CwdError, EdenTimeoutError, EnvMergeError,
    HookError, HookFailed, HookTimeout, IdleTimeout, InvalidOptions,
    PromptError, RestAuthError, RestError, RestNotFoundError,
    RestRateLimited, SessionCaptureFailed, StepTimeout,
    # version
    __version__,
)
```

The CLI surface (`eden init`, `eden version`) is unchanged from Phase 6.

---

## 2. Architecture

### 2.1 Two artifact streams

1. **`docs/` content** — 14 hand-written markdown files + 3 ADRs in the structure specified by the master design. No build tooling; markdown renders natively on GitHub.
2. **Release machinery** — a new `.github/workflows/release.yml` triggered by tag push `v*`, plus a version bump in `pyproject.toml`, plus a README rewrite that points to the new docs.

The two streams are decoupled. Docs land first (verifiable on GitHub render). Release workflow + tag follows. README rewrite bridges them.

### 2.2 New + modified files

```
docs/
├── README.md                          # NEW — table of contents
├── what-is-eden.md                    # NEW
├── quick-start.md                     # NEW
├── python-api.md                      # NEW — canonical public-API reference
├── how-it-works.md                    # NEW
├── prompts.md                         # NEW
├── templates.md                       # NEW (blank only)
├── cli.md                             # NEW
├── configuration.md                   # NEW
├── sandbox-providers.md               # NEW
├── agents.md                          # NEW
├── custom-providers.md                # NEW
├── errors.md                          # NEW
├── development.md                     # NEW
├── superpowers/                       # UNCHANGED — internal phase specs/plans
└── adr/
    ├── 0001-finalizing-vs-direct-handles.md   # NEW
    ├── 0002-sync-first-public-api.md          # NEW
    └── 0003-one-agent-per-file.md             # NEW

.github/workflows/
└── release.yml                        # NEW — tag-triggered PyPI publish

tests/unit/
└── test_docs_consistency.py           # NEW — asserts eden.__all__ ⊆ docs/python-api.md

README.md                              # REWRITE
pyproject.toml                         # MODIFY — version 0.0.1 → 0.1.0; classifier Alpha → Beta
```

Every new docs file targets ≤300 lines of prose. `python-api.md` is the only one that may approach that bound.

### 2.3 Boundaries

- Each docs file has one clear responsibility (one user question answered well).
- Cross-links between docs use relative paths; never absolute GitHub URLs.
- The release workflow is single-job, single-purpose: build sdist+wheel, upload to PyPI on tag push.
- The consistency test is one assertion: every name in `eden.__all__` appears in `docs/python-api.md`. Drift catcher only — not a full doc-quality check.

---

## 3. Component contracts

### 3.1 Docs file shape (universal)

Every `docs/*.md` file (except `docs/README.md` which is itself a TOC) starts with:

```markdown
# <Title>

<one-sentence TL;DR>

---

<body>
```

This makes the docs composable for agents reading out of order: title and TL;DR are always at fixed positions.

### 3.2 `docs/README.md` — table of contents

A flat list of all docs files with a one-line description for each. Grouped under three headings: **Getting started** (what-is-eden, quick-start), **Reference** (python-api, cli, configuration, sandbox-providers, agents, prompts, templates, errors), **Concepts** (how-it-works, custom-providers, development, ADRs).

### 3.3 `docs/python-api.md` — canonical reference

The most load-bearing doc. Structure:

1. Top-level entry points: `run(...)`, `create_worktree(...)`. Full signature, parameter table, return type, minimal example.
2. Configuration types: `Timeouts`, `Logging`, `Mount`, `BranchStrategy`. Fields + defaults.
3. Result types: `RunResult`, `Iteration`, `Commit`, `Usage`, `FinalizeResult`. Frozen dataclass field reference.
4. Streaming: `StreamEvent` kinds (`text`, `idle_warning`, `tool_call`, `usage`).
5. Agents: each factory's signature (`simulated_agent`, `claude_code`, `codex`, `opencode`, `pi`, `cli_agent`) + the `Agent` Protocol + `IterationContext` fields.
6. Lifecycle: `Hook`, `HookPhase`, `Hooks`, `HostHooks`, `SandboxHooks` shapes + ordering rules.
7. Cancellation: `AbortController`, `AbortSignal`, `Aborted`.
8. Provider Protocol re-export: `IsolatedSandboxHandle` (just enough for users who want to write custom providers — depth lives in `custom-providers.md`).
9. Errors: short link to `errors.md` plus the import line.

Every name in `eden.__all__` appears in this document.

### 3.4 ADRs

Each ADR follows the lightweight template: **Status / Context / Decision / Consequences**.

- **0001 — Finalizing vs. direct handles.** Why isolated/cloud providers expose `IsolatedSandboxHandle.finalize() -> FinalizeResult` rather than streaming work back through the sandbox handle directly. Trade-off: simpler sandbox-side code, post-iteration commit semantics match local providers.
- **0002 — Sync-first public API.** Why `eden.run(...)` is synchronous (subprocess + threading internally) rather than `asyncio`. Trade-off: simpler API surface for the dominant use case (single agent, one host process); async wrapper can land later if demand justifies it.
- **0003 — One agent per file.** Why `eden/agents/<name>/__init__.py` rather than a single `agents.py` registry. Trade-off: smaller files, easier to add agents without merge conflicts, lets each agent own its parse logic.

### 3.5 `.github/workflows/release.yml`

```yaml
name: release
on:
  push:
    tags: ['v*']
permissions:
  contents: read
  id-token: write   # Trusted Publishing
jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi   # required for Trusted Publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install --upgrade pip build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

No secrets. PyPI Trusted Publishing pairs the GitHub repo + workflow + environment to the PyPI project, so the OIDC token from `id-token: write` authenticates the upload. The PyPI side is configured manually (one-time) at https://pypi.org/manage/project/eden-agent/settings/publishing/ — documented in `docs/development.md`.

### 3.6 `tests/unit/test_docs_consistency.py`

```python
import re
from pathlib import Path

import eden


def test_docs_python_api_covers_all_public_exports() -> None:
    api_doc = Path("docs/python-api.md").read_text()
    missing = [name for name in eden.__all__ if not re.search(rf"\b{re.escape(name)}\b", api_doc)]
    assert missing == [], f"docs/python-api.md missing: {missing}"
```

One test. Fires whenever someone adds a public export without documenting it.

### 3.7 README rewrite

Sections:

1. Title + one-line tagline.
2. Badge row: CI status, PyPI version, Python versions, license.
3. **What is Eden?** — 2 sentences.
4. **Install:** `pip install eden-agent`.
5. **Quick example:** ~15-line `eden.run(...)` snippet using the simulated agent (no external dependencies needed to run it).
6. **Documentation:** link to `docs/README.md`.
7. **License:** PolyForm Shield 1.0.0 link.

Drops the "Pre-alpha" status block — that information moves to `docs/what-is-eden.md` (current state + roadmap).

### 3.8 `pyproject.toml` changes

```diff
- version = "0.0.1"
+ version = "0.1.0"

- "Development Status :: 3 - Alpha",
+ "Development Status :: 4 - Beta",
```

Nothing else. `eden/_version.py` reads from `importlib.metadata` and stays in sync.

---

## 4. Error handling

| Failure | Behavior |
|---|---|
| `python -m build` fails on tag push | Release workflow fails; tag stays in git but no PyPI publish. Fix and re-tag `v0.1.1`. |
| PyPI Trusted Publishing not yet configured | Workflow's publish step fails with `403 Forbidden`. User configures the trusted publisher on PyPI, re-runs the workflow via the "Re-run jobs" button. |
| Tag pushed twice (e.g., force-deleted and re-pushed) | Workflow runs twice. PyPI rejects the second upload (file already exists). First publish succeeds. |
| Docs link rot during development | Caught by manual review checklist in the plan. No automated link checker in v0.1 (deferred). |
| `eden.__all__` adds a name without a corresponding doc entry | `test_docs_python_api_covers_all_public_exports` fails in CI. |

The release workflow's `id-token: write` permission is scoped to one job — no token leak surface beyond standard GHA.

---

## 5. Concurrency

No new threads or processes. Release workflow runs as a normal GHA job. Workflow-level concurrency group (`group: release-${{ github.ref }}`) prevents duplicate runs if a tag is force-pushed.

---

## 6. Testing strategy

### 6.1 Unit tests

**`tests/unit/test_docs_consistency.py` (1 test):**
- Every name in `eden.__all__` appears at least once in `docs/python-api.md`.

That's the only automated docs check. Prose quality, link correctness, and code-snippet runnability are covered by the manual review checklist.

### 6.2 Manual review checklist (in the plan, not enforced by CI)

- [ ] Every relative cross-link in `docs/` resolves to an existing file.
- [ ] Every code snippet in `quick-start.md`, `python-api.md`, `prompts.md`, `templates.md` runs as written (`python -c "..."` or in a fresh venv).
- [ ] Every public symbol in `eden.__all__` documented in `docs/python-api.md` (also covered by the consistency test).
- [ ] Every error class in `eden.errors` documented in `docs/errors.md`.
- [ ] Every sandbox provider documented in `docs/sandbox-providers.md`.
- [ ] Every agent factory documented in `docs/agents.md`.
- [ ] README's Quick Example snippet runs end-to-end with the simulated agent.

### 6.3 Release workflow validation

Tag `v0.1.0-rc1` first as a dry run. The workflow has a conditional step: rc tags upload to TestPyPI, non-rc tags upload to production PyPI. Once the rc upload is verified, tag `v0.1.0` for production.

```yaml
- uses: pypa/gh-action-pypi-publish@release/v1
  if: ${{ !contains(github.ref, '-rc') }}
- uses: pypa/gh-action-pypi-publish@release/v1
  if: ${{ contains(github.ref, '-rc') }}
  with:
    repository-url: https://test.pypi.org/legacy/
```

### 6.4 Coverage

70% gate retained. The new test adds one assertion covering one path; total coverage stays in the 90%+ range established in earlier phases.

---

## 7. Backwards compatibility

- `0.0.1 → 0.1.0` is the first public release; no migration concerns.
- The public surface frozen here becomes a semver stability commitment. Future breaking changes require a major bump or a deprecation cycle.
- Pre-existing internal phase specs/plans under `docs/superpowers/` remain untouched.

---

## 8. Phase boundary

**Lands in 7:** all 14 user-facing docs files + 3 ADRs + `docs/README.md` TOC + README rewrite + release workflow + version bump + docs consistency test + git tag `v0.1.0`.

**Deferred to v0.2+:** Sphinx/mkdocs site, auto-generated API reference, real-binary agent integration tests, additional `eden init` templates, Rust-vs-Python benchmark, automated link checking.

---

**Estimated effort:** ~3-4 days. Bulk is prose writing across 14 docs + 3 ADRs (~2 days). Release machinery ~half a day. README rewrite ~half a day. Verification + tag dry-run ~half a day.

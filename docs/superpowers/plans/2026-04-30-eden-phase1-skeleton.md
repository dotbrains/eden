# Eden Phase 1 — Skeleton & Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wipe the existing Rust workspace, initialize a fresh git repo, and build the minimal Python package skeleton — installable via `pip install -e .`, with `eden --help` and a stub `eden init` working, plus CI green on Linux/macOS/Windows × Python 3.11/3.12/3.13.

**Architecture:** Greenfield Python 3 package replacing a Rust workspace. The skeleton ships with no functional features (no run, no sandboxes, no agents) — it establishes the package layout, build/install plumbing, CLI entry point, and CI gates. Subsequent phases (sandbox foundations, orchestration, etc.) build on this base.

**Tech Stack:** Python 3.11+, `typer` (CLI), `rich` (terminal output), `questionary` (interactive prompts), `pytest` (tests), `mypy --strict` (types), GitHub Actions (CI), `pyproject.toml` (build config, no `setup.py`).

**Reference spec:** `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md`

---

## File structure produced by this plan

```
eden/                                       # repo root (already exists at filesystem)
├── .github/
│   ├── workflows/
│   │   └── ci.yml                          # 3.11/3.12/3.13 × macOS/Linux/Windows matrix
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug.md
│   │   └── feature.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── eden/                                   # the Python package
│   ├── __init__.py                         # exports: __version__
│   ├── _version.py                         # __version__ = "0.0.1"
│   ├── py.typed                            # PEP 561 marker (empty file)
│   └── cli/
│       ├── __init__.py
│       ├── main.py                         # typer app entry point
│       └── init.py                         # `eden init` stub command
├── tests/
│   ├── __init__.py
│   ├── test_version.py                     # asserts __version__ matches pyproject
│   └── test_cli.py                         # asserts `eden --help` and `eden init` work
├── docs/
│   ├── superpowers/                        # PRESERVED from before phase 1
│   │   ├── specs/
│   │   │   └── 2026-04-30-eden-python-rewrite-design.md
│   │   └── plans/
│   │       └── 2026-04-30-eden-phase1-skeleton.md  # this file
│   └── (nothing else; user-facing docs land in phase 7)
├── .gitignore                              # Python-flavored
├── LICENSE                                 # PolyForm Shield 1.0.0 (preserved from before)
├── README.md                               # placeholder
└── pyproject.toml                          # all build/test/lint config in one file
```

**File responsibilities:**

- `pyproject.toml` — single source of truth: package metadata, deps, build backend (`hatchling`), pytest config, mypy config, ruff config, project scripts.
- `eden/__init__.py` — only exports `__version__` in this phase. Public API exports come in later phases.
- `eden/_version.py` — single string variable. Source of truth for the version; `pyproject.toml` reads it dynamically.
- `eden/cli/main.py` — `typer.Typer` app instance + the `eden` console-script entry point. Wires subcommands (currently just `init`).
- `eden/cli/init.py` — `eden init` command stub. Prints a "not implemented" message in this phase; full scaffolder lands in phase 6.
- `tests/test_version.py` — guards against pyproject/`_version.py` drift.
- `tests/test_cli.py` — uses `typer.testing.CliRunner` to assert `eden --help` exits 0 and `eden init` exits 1 with a clear "not implemented" stderr message.
- `.github/workflows/ci.yml` — matrix job that installs the package, runs pytest, runs mypy `--strict`, runs ruff. Three Python × three OS = 9 jobs.

---

## Task 1: Day 0 — Wipe Rust, initialize git repo

**Files:**
- Delete: `crates/`, `scripts/`, `Cargo.toml`, `Cargo.lock`, `CONTEXT.md`, `README.md`
- Wipe (preserving `docs/superpowers/`): everything else under `docs/`
- Keep: `LICENSE`, `docs/superpowers/`

- [ ] **Step 1: Verify current directory and confirm what gets preserved**

Run from the repo root:

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden
ls -la
ls docs/superpowers/specs/
ls docs/superpowers/plans/
```

Expected: `LICENSE` is present in the root listing; the spec file `2026-04-30-eden-python-rewrite-design.md` is present under `docs/superpowers/specs/`; this plan file is present under `docs/superpowers/plans/`.

If any of those are missing, **stop** and surface the issue — do not proceed with the wipe.

- [ ] **Step 2: Wipe Rust artifacts and Rust-flavored docs**

Run:

```bash
rm -rf crates/ scripts/
rm -f Cargo.toml Cargo.lock CONTEXT.md README.md
find docs -mindepth 1 -maxdepth 1 ! -name superpowers -exec rm -rf {} +
```

Expected: no errors. Verify with:

```bash
ls
ls docs/
```

`ls` should show: `LICENSE  docs`. `ls docs/` should show only: `superpowers`.

- [ ] **Step 3: Initialize git repo**

Run:

```bash
git init -b main
```

Expected output ends with: `Initialized empty Git repository in .../eden/.git/`.

Verify:

```bash
git status
```

Expected: shows `LICENSE` and `docs/` as untracked.

- [ ] **Step 4: Create the initial commit**

Run:

```bash
git add LICENSE docs/superpowers
git commit -m "chore: initial commit (PolyForm Shield 1.0.0)"
```

Expected: commit succeeds with two files (`LICENSE`) plus the spec/plan markdown files. Verify:

```bash
git log --stat
```

Expected: one commit, message `chore: initial commit (PolyForm Shield 1.0.0)`, `LICENSE` and the markdown files listed in the changes.

- [ ] **Step 5: Create the GitHub remote**

Run:

```bash
gh repo create smeltery/eden --public --source=. --remote=origin --push --description "Python orchestrator for AI coding agents in sandboxed worktrees."
```

Expected: command outputs the GitHub URL and pushes. If the repo `smeltery/eden` already exists empty on GitHub, run instead:

```bash
git remote add origin git@github.com:smeltery/eden.git
git push -u origin main
```

Verify:

```bash
git remote -v
git branch -vv
```

Expected: `origin` points to `git@github.com:smeltery/eden.git`; the `main` branch tracks `origin/main`.

---

## Task 2: Add `.gitignore` for Python

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Write `.gitignore`**

Create `.gitignore` with this exact content:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Testing / coverage
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
htmlcov/

# Type checkers
.mypy_cache/
.dmypy.json
dmypy.json
.pyre/
.pytype/
.ruff_cache/

# Editors / OS
.idea/
.vscode/
*.swp
*~
.DS_Store
Thumbs.db

# Eden runtime artifacts
.eden/logs/
.eden/worktrees/
.eden/.env
```

- [ ] **Step 2: Stage and commit**

```bash
git add .gitignore
git commit -m "chore: add Python .gitignore"
```

Expected: commit succeeds. Verify with `git status` — should show "nothing to commit, working tree clean."

---

## Task 3: Write the failing version test

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_version.py`

- [ ] **Step 1: Create empty test package marker**

```bash
mkdir -p tests
```

Create `tests/__init__.py` with a single line:

```python
# Eden test suite.
```

- [ ] **Step 2: Write the failing version test**

Create `tests/test_version.py`:

```python
"""Verify the package exposes a version string and it matches pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

import eden


def test_version_string_exists() -> None:
    assert isinstance(eden.__version__, str)
    assert eden.__version__  # non-empty


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    declared = data["project"]["version"]
    assert eden.__version__ == declared, (
        f"eden.__version__ ({eden.__version__!r}) does not match "
        f"pyproject.toml project.version ({declared!r})"
    )
```

- [ ] **Step 3: Confirm the test cannot run yet**

Run:

```bash
python -m pytest tests/test_version.py -v
```

Expected: error — `ModuleNotFoundError: No module named 'eden'` (because no package or `pyproject.toml` exists yet).

This confirms the test correctly identifies the missing implementation.

---

## Task 4: Create the minimum `eden` package and `pyproject.toml` to pass version tests

**Files:**
- Create: `eden/__init__.py`
- Create: `eden/_version.py`
- Create: `eden/py.typed` (empty)
- Create: `pyproject.toml`

- [ ] **Step 1: Create the package marker and version module**

```bash
mkdir -p eden
```

Create `eden/_version.py`:

```python
"""Single source of truth for the Eden version string."""

__version__ = "0.0.1"
```

Create `eden/__init__.py`:

```python
"""Eden — Python orchestrator for AI coding agents in sandboxed worktrees."""

from __future__ import annotations

from eden._version import __version__

__all__ = ["__version__"]
```

Create `eden/py.typed` as an **empty file** (PEP 561 marker — no content).

```bash
: > eden/py.typed
```

- [ ] **Step 2: Create `pyproject.toml`**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "eden-agent"
version = "0.0.1"
description = "Python orchestrator for AI coding agents in sandboxed worktrees."
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.11"
authors = [
    { name = "smeltery" },
]
keywords = [
    "agents",
    "claude-code",
    "codex",
    "docker",
    "podman",
    "sandbox",
    "worktree",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development",
]
dependencies = [
    "typer>=0.12",
    "rich>=13.7",
    "questionary>=2.0",
    "python-dotenv>=1.0",
    "anyio>=4.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "mypy>=1.10",
    "ruff>=0.5",
    "build>=1.2",
]

[project.scripts]
eden = "eden.cli.main:app"

[project.urls]
Homepage = "https://github.com/smeltery/eden"
Issues = "https://github.com/smeltery/eden/issues"

[tool.hatch.build.targets.wheel]
packages = ["eden"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
]
markers = [
    "unit: fast unit tests with no external services",
    "integration: tests that touch real Docker/Podman/cloud services",
    "smoke: end-to-end smoke tests",
]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
files = ["eden", "tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "RUF", # ruff-specific
]
```

- [ ] **Step 3: Install in editable mode with dev extras**

Create a virtual environment and install:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: install succeeds. Verify:

```bash
python -c "import eden; print(eden.__version__)"
```

Expected output: `0.0.1`.

- [ ] **Step 4: Run the version test — verify it passes**

Run:

```bash
python -m pytest tests/test_version.py -v
```

Expected: 2 passed in <1s.

- [ ] **Step 5: Commit**

```bash
git add eden/ pyproject.toml tests/
git commit -m "feat: add eden package skeleton with version test"
```

---

## Task 5: Write the failing CLI test

**Files:**
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI test**

Create `tests/test_cli.py`:

```python
"""Verify the eden CLI entry point works and exposes the init subcommand."""

from __future__ import annotations

from typer.testing import CliRunner

from eden.cli.main import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "eden" in result.output.lower()


def test_init_subcommand_exists() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0, result.output


def test_init_stub_reports_not_implemented() -> None:
    result = runner.invoke(app, ["init"])
    # Stub exits non-zero with a clear message; full scaffolder lands in phase 6.
    assert result.exit_code == 1, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "not implemented" in combined.lower()
    assert "phase 6" in combined.lower()
```

- [ ] **Step 2: Confirm the test fails**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: errors with `ModuleNotFoundError: No module named 'eden.cli'` (because `eden/cli/` doesn't exist yet).

---

## Task 6: Create the CLI app and `init` stub to pass the CLI test

**Files:**
- Create: `eden/cli/__init__.py`
- Create: `eden/cli/main.py`
- Create: `eden/cli/init.py`

- [ ] **Step 1: Create the CLI subpackage**

```bash
mkdir -p eden/cli
```

Create `eden/cli/__init__.py`:

```python
"""Eden command-line interface."""
```

- [ ] **Step 2: Create the `init` stub**

Create `eden/cli/init.py`:

```python
"""`eden init` — scaffold a `.eden/` directory in the current repo.

Phase 1 ships a stub that reports "not implemented." The full interactive
scaffolder lands in phase 6 (CLI & templates).
"""

from __future__ import annotations

import typer
from rich.console import Console

console = Console(stderr=True)


def init_command() -> None:
    console.print(
        "[red]eden init is not implemented yet.[/red] "
        "Full scaffolder lands in phase 6 of the rewrite.",
    )
    raise typer.Exit(code=1)
```

- [ ] **Step 3: Create the typer app and wire the `init` subcommand**

Create `eden/cli/main.py`:

```python
"""Top-level Typer application for the `eden` console script."""

from __future__ import annotations

import typer

from eden import __version__
from eden.cli.init import init_command

app = typer.Typer(
    name="eden",
    help="Python orchestrator for AI coding agents in sandboxed worktrees.",
    no_args_is_help=True,
    add_completion=False,
)

app.command(name="init", help="Scaffold .eden/ in the current repo.")(init_command)


@app.command(name="version", help="Print the eden version and exit.")
def version_command() -> None:
    typer.echo(__version__)
```

- [ ] **Step 4: Run the CLI test — verify it passes**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Manually exercise the CLI**

Run each:

```bash
eden --help
eden version
eden init
```

Expected:
- `eden --help` exits 0; output mentions "Python orchestrator for AI coding agents".
- `eden version` exits 0; prints `0.0.1`.
- `eden init` exits 1; prints `eden init is not implemented yet. Full scaffolder lands in phase 6 of the rewrite.` to stderr.

- [ ] **Step 6: Run the full test suite**

```bash
python -m pytest -v
```

Expected: 5 passed total (2 version + 3 CLI).

- [ ] **Step 7: Commit**

```bash
git add eden/cli/ tests/test_cli.py
git commit -m "feat: add eden CLI with init stub and version subcommand"
```

---

## Task 7: Wire mypy `--strict` and ruff, fix any failures

**Files:**
- No new files; this validates existing code passes the type/lint gates.

- [ ] **Step 1: Run mypy on the package**

```bash
mypy --strict eden tests
```

Expected: `Success: no issues found`. If any errors appear, fix them (most likely candidates: missing return-type annotations or `Any` leakage from `typer.testing.CliRunner.invoke`). Common fixes:

- Add `-> None` to test functions and Typer commands.
- Add `from __future__ import annotations` if not already present (it is, in every file).

- [ ] **Step 2: Run ruff format check**

```bash
ruff format --check eden tests
```

Expected: `X files already formatted`. If it reports diffs, run `ruff format eden tests` and re-run the check.

- [ ] **Step 3: Run ruff lint**

```bash
ruff check eden tests
```

Expected: `All checks passed!`. Fix any reported issues directly.

- [ ] **Step 4: Commit any fixes**

```bash
git status
```

If `git status` shows changes, commit them:

```bash
git add -A
git commit -m "chore: satisfy mypy --strict and ruff lint"
```

If clean, skip the commit.

---

## Task 8: Write the placeholder `README.md`

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

Create `README.md`:

````markdown
# Eden

Python orchestrator for AI coding agents in sandboxed worktrees.

> **Status:** Pre-alpha. Phase 1 (skeleton) only — `eden run`, sandbox providers, agents, and templates are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.

## Install (development)

```bash
git clone https://github.com/smeltery/eden.git
cd eden
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

The full surface is documented under `docs/` once phase 7 lands. Until then:

```bash
eden --help
eden version
```

## License

[PolyForm Shield 1.0.0](LICENSE).
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add placeholder README pointing at design + plans"
```

---

## Task 9: Add GitHub Actions CI matrix

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the CI workflow**

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: test (${{ matrix.os }} / py${{ matrix.python-version }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml

      - name: Install package with dev extras
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Ruff format check
        run: ruff format --check eden tests

      - name: Ruff lint
        run: ruff check eden tests

      - name: mypy --strict
        run: mypy --strict eden tests

      - name: pytest
        run: pytest -v
```

- [ ] **Step 2: Commit and push**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add 3.11/3.12/3.13 × macOS/Linux/Windows matrix"
git push
```

- [ ] **Step 3: Watch the first CI run**

Run:

```bash
gh run watch
```

Expected: all 9 matrix jobs pass green. If any fail, drill into the logs:

```bash
gh run view --log-failed
```

Common Windows-specific issues at this stage:
- Path separator differences in tests — there shouldn't be any in phase 1; if there are, use `pathlib.Path` and avoid string concatenation.
- Line-ending diffs in ruff format — ensure `.gitattributes` or git config doesn't auto-convert. Add a `.gitattributes` if needed:

  ```gitattributes
  * text=auto eol=lf
  ```

  Then `git add .gitattributes && git commit -m "chore: enforce LF line endings" && git push`.

---

## Task 10: Add issue templates, PR template, CODEOWNERS

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug.md`
- Create: `.github/ISSUE_TEMPLATE/feature.md`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/CODEOWNERS`

- [ ] **Step 1: Create issue templates**

```bash
mkdir -p .github/ISSUE_TEMPLATE
```

Create `.github/ISSUE_TEMPLATE/bug.md`:

```markdown
---
name: Bug report
about: Report a defect in eden
title: "bug: "
labels: bug
---

## What happened

<!-- A clear description of the bug. -->

## Steps to reproduce

1.
2.
3.

## Expected behavior

## Actual behavior

## Environment

- eden version: `eden version`
- Python version:
- OS:
- Sandbox provider (if applicable):

## Logs / traceback

```
<!-- paste relevant output here -->
```
```

Create `.github/ISSUE_TEMPLATE/feature.md`:

```markdown
---
name: Feature request
about: Propose a new feature or behavior change
title: "feat: "
labels: enhancement
---

## Problem

<!-- What user-facing problem does this solve? -->

## Proposed solution

## Alternatives considered

## Additional context
```

- [ ] **Step 2: Create PR template**

Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Summary

<!-- What does this change and why? -->

## Test plan

- [ ]
- [ ]

## Checklist

- [ ] Tests added or updated
- [ ] `mypy --strict eden tests` passes
- [ ] `ruff format --check eden tests` passes
- [ ] `ruff check eden tests` passes
- [ ] `pytest` passes locally
```

- [ ] **Step 3: Create CODEOWNERS**

Create `.github/CODEOWNERS`:

```
# Default owners for everything in the repo.
# Replace @smeltery/maintainers with the actual GitHub team or user handle.
* @smeltery/maintainers
```

If the team `@smeltery/maintainers` does not exist, swap in a personal handle (e.g. `@nicholasadamou`) so PR review assignment works. Verify by running:

```bash
gh api orgs/smeltery/teams/maintainers --silent && echo "team exists" || echo "team missing — use a personal handle"
```

- [ ] **Step 4: Commit and push**

```bash
git add .github/ISSUE_TEMPLATE .github/PULL_REQUEST_TEMPLATE.md .github/CODEOWNERS
git commit -m "chore: add issue, PR, and CODEOWNERS templates"
git push
```

Expected: CI passes again (these files don't affect tests, mypy, or ruff).

---

## Task 11: Configure repo settings on GitHub

**Files:**
- No files; this configures GitHub itself via `gh`.

- [ ] **Step 1: Set repo description and topics**

Run:

```bash
gh repo edit smeltery/eden \
  --description "Python orchestrator for AI coding agents in sandboxed worktrees." \
  --add-topic agents \
  --add-topic claude-code \
  --add-topic codex \
  --add-topic docker \
  --add-topic podman \
  --add-topic sandbox \
  --add-topic worktree \
  --add-topic python
```

Expected: command exits 0. Verify on github.com that topics appear.

- [ ] **Step 2: Enable branch protection on `main`**

Run:

```bash
gh api -X PUT repos/smeltery/eden/branches/main/protection \
  -F required_status_checks.strict=true \
  -F 'required_status_checks.contexts[]=test (ubuntu-latest / py3.11)' \
  -F 'required_status_checks.contexts[]=test (ubuntu-latest / py3.12)' \
  -F 'required_status_checks.contexts[]=test (ubuntu-latest / py3.13)' \
  -F 'required_status_checks.contexts[]=test (macos-latest / py3.11)' \
  -F 'required_status_checks.contexts[]=test (macos-latest / py3.12)' \
  -F 'required_status_checks.contexts[]=test (macos-latest / py3.13)' \
  -F 'required_status_checks.contexts[]=test (windows-latest / py3.11)' \
  -F 'required_status_checks.contexts[]=test (windows-latest / py3.12)' \
  -F 'required_status_checks.contexts[]=test (windows-latest / py3.13)' \
  -F enforce_admins=false \
  -F required_pull_request_reviews.required_approving_review_count=1 \
  -F required_pull_request_reviews.dismiss_stale_reviews=true \
  -F restrictions= \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

Expected: returns the protection rule JSON.

If the command errors with "Required status check ... is not yet reporting," that means the matrix job names haven't appeared in any completed workflow run yet. Re-run after Task 9's CI run completes successfully — branch protection requires the check names to be known to GitHub before they can be required.

Verify:

```bash
gh api repos/smeltery/eden/branches/main/protection | jq '.required_status_checks.contexts'
```

Expected: lists all 9 matrix job names.

- [ ] **Step 3: Disable wikis and projects (not used)**

```bash
gh repo edit smeltery/eden --enable-wiki=false --enable-projects=false
```

Expected: command exits 0.

---

## Task 12: Verify the skeleton end-to-end on a fresh checkout

**Files:**
- No files; this is a smoke check that the published repo works for a new contributor.

- [ ] **Step 1: Clone into a temp directory and install**

Run:

```bash
TMP=$(mktemp -d)
cd "$TMP"
git clone git@github.com:smeltery/eden.git
cd eden
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Expected: clone, venv, install all succeed.

- [ ] **Step 2: Run the test suite**

```bash
pytest -v
```

Expected: 5 passed.

- [ ] **Step 3: Run all gates**

```bash
ruff format --check eden tests
ruff check eden tests
mypy --strict eden tests
```

Expected: all three exit 0.

- [ ] **Step 4: Exercise the CLI**

```bash
eden --help
eden version
eden init || echo "exit code: $?"
```

Expected:
- `eden --help` shows command list including `init` and `version`.
- `eden version` prints `0.0.1`.
- `eden init` exits 1 and prints the "not implemented" message.

- [ ] **Step 5: Clean up**

```bash
deactivate
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden
rm -rf "$TMP"
```

If everything passed, **Phase 1 is complete.** The skeleton is in place. Phase 2 (sandbox foundations) starts from this base.

---

## Self-review

Run through this checklist before declaring the plan done:

**1. Spec coverage:** Phase 1 in the spec calls for: `git init`, `pyproject.toml`, package skeleton, `py.typed`, CI matrix (3.11/3.12/3.13 × macOS/Linux/Windows), README placeholder, `.gitignore`, `eden init` stub, `pip install -e .` working locally, branch protection on `main` enabled before phase 2 begins, repo description, topics, issue/PR templates, CODEOWNERS. All covered: Tasks 1, 4, 4, 4, 9, 8, 2, 6, 4, 11, 11, 11, 10, 10. The `PYPI_API_TOKEN` secret is explicitly deferred to phase 7, matching the spec.

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later" / "add appropriate error handling" / "similar to Task N" anywhere. Each task has exact code or exact commands. No undefined symbols referenced.

**3. Type consistency:** Function names used across tasks: `init_command` (defined Task 6, referenced in main.py same task — consistent), `app` (defined Task 6, referenced in tests Task 5 — consistent), `__version__` (defined Task 4, referenced in tests Task 3 — consistent). No drift.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-04-30-eden-phase1-skeleton.md`.

This is **Phase 1 only** (skeleton). Phases 2 through 7 each get their own plan, written when we're about to start them — by then we'll have learned things from earlier phases that should inform the later plans.

# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project overview

Eden is a Python 3.11+ orchestrator for AI coding agents in sandboxed git worktrees. It creates a fresh worktree/branch, runs an agent CLI inside a sandbox provider, streams output through the iteration loop, and commits resulting changes for review.

The package is published as `eden-agent`; the installed CLI entry point is `eden`.

## Setup and development commands

**Recommended (Linux/macOS): Flox.** The repo ships a declarative,
lockfile-pinned dev environment under [`.flox/`](./.flox/). With
[Flox](https://flox.dev) installed, run `flox activate` from the repo root: it
provisions the toolchain (Python 3.11/3.12/3.13, git, gh, docker/podman clients,
pre-commit, make) and auto-builds `.venv` via `pip install -e ".[dev]"` on first
activation. All the `pytest` / `pre-commit` / `eden` commands below then work
unchanged inside the activated shell. Select the interpreter the venv is built
from with `EDEN_PYTHON` (e.g. `EDEN_PYTHON=python3.12 flox activate`); it
defaults to `python3.11`. ruff and mypy stay pip-pinned in `.venv` (exact
versions from `pyproject.toml [dev]`), not in the Flox manifest, so local and CI
can't drift. docker/podman are clients only — the daemon/VM is host-provided.
Windows is unsupported by Flox; use the manual path below.

Manual path (no Flox, and required on Windows):

- Install the package with development dependencies: `python -m pip install -e ".[dev]"`
- Upgrade pip before install in fresh environments: `python -m pip install --upgrade pip`
- Install local commit hooks after installing dev dependencies: `pre-commit install`
- Run all format/lint/type hooks: `pre-commit run --all-files --show-diff-on-failure`
- Run CI's default test set with coverage: `pytest -v -m "unit or e2e" --cov=eden --cov-fail-under=70`
- Run Linux-only integration tests: `pytest -v -m integration`
- Run fast unit tests only: `pytest -m unit`
- Run e2e tests only: `pytest -m e2e`
- Run a single test file: `pytest tests/unit/test_run_loop.py`
- Run a single test: `pytest tests/unit/test_run_loop.py::test_name`
- Build the package: `python -m build`
- Check the installed CLI version: `eden version`

CI minimizes overlap while preserving coverage: `check` runs `pre-commit run --all-files --show-diff-on-failure` and `pytest -v -m "unit or e2e" --cov=eden --cov-fail-under=70` once on Ubuntu with Python 3.11 in Flox; `build` runs `python -m build` once on Ubuntu in Flox; `test-compat` runs unit-only compatibility legs for Linux/Python 3.12 in Flox, macOS/Python 3.13 in Flox, and Windows/Python 3.13 via `actions/setup-python` + pip. Integration tests run once on Linux inside Flox.

For Warp environment setup, use: `cd eden && python -m pip install --upgrade pip && python -m pip install -e ".[dev]"`.

## Architecture map

The top-level `eden/__init__.py` is the public API surface. If you add a public export, also update the API documentation; `tests/unit/test_docs_consistency.py` enforces documentation coverage for public exports.

The main execution path is:

1. `eden.run(...)` resolves configuration and branch strategy.
2. `eden.worktree.create_worktree()` creates or selects a worktree under `.eden/worktrees/`.
3. A `SandboxProvider` creates a `SandboxHandle`.
4. The orchestrator renders prompts, calls `agent.build_command(ctx)`, executes inside the sandbox, parses streamed stdout into `StreamEvent`s, watches completion/idle/timeout/abort conditions, and commits changes per iteration.
5. Non-bind-mount providers finalize by applying a patch/diff back to the host worktree.

Important modules:

- `eden/orchestrator/` contains `run()`, `interactive()`, setup resolution, the iteration loop, completion matching, idle watchdogs, result assembly, and recovery formatting.
- `eden/worktree/` owns git worktree creation, branch strategies, and advisory locks.
- `eden/providers/` defines sandbox Protocols and shared implementations for containers, REST-backed providers, directory upload, and patch sync.
- `eden/sandboxes/` exposes concrete providers: `no_sandbox`, `docker`, `podman`, `isolated`, `daytona`, `vercel`, and `forkd`, plus `create_sandbox()` for caller-managed multi-agent runs.
- `eden/agents/` contains agent factories. Dedicated agents live in one subpackage per agent; `cli_agent` is the generic line-streaming adapter.
- `eden/prompt/` renders prompt sources, arguments, and shell blocks.
- `eden/lifecycle/` defines host/sandbox hooks and hook execution phases.
- `eden/session/` captures Claude Code session JSONL files into `.eden/sessions/`.
- `eden/output/` extracts structured XML-tagged output from agent streams.
- `eden/cli/` implements `eden init`, `eden run`, `eden cost`, `eden clean`, `eden replay`, and `eden version`.

## Sandbox model

Sandbox providers are grouped by how changes return to the host:

- Bind-mount providers: `no_sandbox`, `docker`, and `podman`. The worktree is mounted directly, so edits happen in place and no finalize step is needed.
- Patch-sync provider: `isolated`. Files are copied to an isolated directory and finalized back to the worktree as a patch.
- Cloud/REST providers: `daytona` and `vercel`. Files are uploaded/downloaded over REST and finalized back as diffs.

Provider `kind` (`"none"`, `"bind_mount"`, or `"isolated"`) affects default branch strategy and whether the orchestrator calls `finalize()`.

## Agent conventions

Each agent factory implements the `Agent` Protocol through `build_command(ctx)` and optional `parse_stream(line)`.

Built-in factories:

- `simulated_agent`: in-process deterministic test agent; does not require an external CLI.
- `claude_code`: wraps the `claude` CLI, requires an explicit model, and captures Claude session JSONL by default.
- `codex`, `opencode`, and `pi`: thin wrappers over `cli_agent`.
- `cli_agent`: generic adapter for line-streaming CLI tools.

New dedicated agents should follow the one-agent-per-subpackage convention under `eden/agents/`, and public factories should be re-exported through the top-level package when they are part of the supported API.

## Tests and markers

Pytest markers are declared in `pyproject.toml`:

- `unit`: fast tests without external services.
- `e2e`: in-process orchestrator runs with `simulated_agent`.
- `integration`: tests that touch Docker, Podman, cloud, or forkd microVM services.
- `smoke`: end-to-end smoke tests.

Prefer `unit` or focused e2e tests while iterating. Run the CI command before considering a change complete.

## Formatting, linting, and typing

Ruff and mypy versions are intentionally pinned in `pyproject.toml` so local checks match CI. Ruff hooks run in pre-commit-managed environments. The mypy hook uses `language: system` and shells through `scripts/precommit_mypy.py`, which locates mypy in `.venv/bin/mypy` (or `.venv\Scripts\mypy.exe` on Windows) and falls back to `mypy` on PATH for CI — `git commit` works without activating the venv first.

Ruff is configured for line length 100 and Python 3.11. Mypy runs in strict mode over `eden` and `tests`.

## Documentation and design references

Use these docs when changing related areas:

- `docs/how-it-works.md` for the run loop, branch strategies, sandbox lifecycle, finalization, and lifecycle hooks.
- `docs/sandbox-providers.md` for provider behavior and provider selection.
- `docs/agents.md` for agent factory APIs and conventions.
- `docs/python-api.md` for the public API contract.
- `docs/cli.md` for CLI behavior and scaffolded files.
- `docs/development.md` for repo layout, local setup, quality gates, release process, and contribution notes.
- `docs/adr/` for architectural decisions; review relevant ADRs before changing core orchestration, providers, agent layout, output parsing, interactive sessions, or tracing.

## Contribution constraints from project docs

- Open an issue first for non-trivial changes.
- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`.
- New public exports must be documented in `docs/python-api.md`.
- New error classes should fit the hierarchy documented in `docs/errors.md`.
- New sandbox providers should follow the Protocol described in `docs/custom-providers.md`.
- New agents should follow the one-agent-per-subpackage convention in `eden/agents/`.

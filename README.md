# Eden

Python orchestrator for AI coding agents in sandboxed worktrees.

> **Status:** Pre-alpha. Phases 1–4a complete: package skeleton, provider Protocols, worktree manager, `no_sandbox`/`docker`/`podman` bind-mount providers, local `isolated` patch-sync provider, `create_sandbox()` factory, top-level `eden.run(...)` orchestrator with `simulated_agent` and `claude_code` agents, prompt rendering pipeline, lifecycle hooks, idle/abort/completion handling, file logging, Claude Code session JSONL capture, and post-iteration `finalize()` for isolated handles. Cloud providers (4b — vercel, daytona), other agents (5), CLI scaffolder (6), and full docs (7) are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.

## Install (development)

```bash
git clone https://github.com/dotbrains/eden.git
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

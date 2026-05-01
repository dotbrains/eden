# Eden

Python orchestrator for AI coding agents in sandboxed worktrees.

> **Status:** Pre-alpha. Phase 1 (skeleton) only — `eden run`, sandbox providers, agents, and templates are not yet implemented. See `docs/superpowers/specs/2026-04-30-eden-python-rewrite-design.md` for the full design and `docs/superpowers/plans/` for phase-by-phase implementation plans.

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

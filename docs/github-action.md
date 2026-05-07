# GitHub Action

Run an eden iteration loop from any GitHub workflow with a composite Action that wraps `eden run`. No Dockerfile or self-hosted runner required.

```yaml
name: Nightly bug-fix loop
on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:

jobs:
  eden:
    runs-on: ubuntu-latest
    permissions:
      contents: write       # for the agent's commits
      issues: write         # for the github backlog manager to close issues
    steps:
      - uses: actions/checkout@v4
      - uses: dotbrains/eden@v0.1.0
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          template: simple-loop
          agent: claude-code
          backlog: github
          max-iterations: "5"
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `template` | `simple-loop` | Template to run in-process. Currently only `simple-loop` is supported by `eden run`. |
| `sandbox` | `no-sandbox` | Sandbox provider — `docker`, `podman`, or `no-sandbox`. CI runners default to `no-sandbox`. |
| `agent` | `claude-code` | Agent factory: `claude-code`, `codex`, `opencode`, or `pi`. |
| `model` | _(per-agent default)_ | Override the model identifier. |
| `backlog` | `github` | Backlog manager: `github`, `beads`, `linear`, or `jira`. |
| `image-name` | _(empty)_ | Container image; required when `sandbox` is `docker`/`podman`. |
| `max-iterations` | `3` | Max iteration loop turns. |
| `idle-timeout` | `600` | Bail when agent stdout is silent this many seconds. |
| `python-version` | `3.12` | Python the action installs before pip-install. |
| `eden-version` | _(empty)_ | Pin to a specific PyPI version. Empty = latest. |

## Authentication

The action forwards three env vars to `eden run` if they're set in the calling workflow's `env:` block: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GH_TOKEN`. Set whichever your agent + backlog combination needs:

| Combination | Required env vars |
|---|---|
| `agent: claude-code` | `ANTHROPIC_API_KEY` |
| `agent: codex` | `OPENAI_API_KEY` |
| `backlog: github` | `GH_TOKEN` (use `secrets.GITHUB_TOKEN` for repo-scoped access) |
| `backlog: linear` | `LINEAR_API_KEY` (set as `env:` on the step; passed through `gh action`) |
| `backlog: jira` | `JIRA_API_TOKEN` and `JIRA_API_HOST` |

For non-default env vars (Linear/Jira), set them in `env:` at the step level — they'll be visible to the `eden run` subprocess the action invokes.

## Permissions

The agent commits to the branch on completion, so the workflow needs:

```yaml
permissions:
  contents: write   # commit + push
  issues: write     # github backlog manager closes issues
  pull-requests: write   # if your workflow opens PRs from the eden branch
```

## Why `no-sandbox` on CI

The standard GitHub-hosted runner is already a fresh ephemeral VM, so wrapping the agent in another Docker container offers no isolation benefit and adds image-pull latency. If you want network-isolated runs (e.g. blocking outbound traffic), set `sandbox: docker` and provide a hardened `image-name`.

Read source: `action.yml`.

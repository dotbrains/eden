# GitHub Agent Workflow Template

Detailed reference for the `github-agent-workflows` template. See [Templates](templates.md) for the local run templates.

---

## `github-agent-workflows`

GitHub Actions scaffold for label-driven agent work:

```bash
eden init --template github-agent-workflows --backlog github --yes
```

### What It Provides

This template wires up operational workflow patterns in Eden:

- `agent:implement` on an issue starts an implementation workflow.
- `agent:review` on a pull request starts an automated reviewer.
- Issue-shape guards refuse PRD/parent issues and sub-issues until they are split into independently implementable work.
- Existing collaborator PRs that already close the issue block duplicate agent work.
- A local factory script can run several issue branches in parallel.
- The reviewer writes a GitHub review payload and optional thread replies.

### Files Produced

| File | Role |
|------|------|
| `.github/workflows/eden-agent-implement.yml` | Label-triggered issue implementer. Checks issue shape, refuses duplicate PRs, runs `.eden/github/implement_issue.py`, pushes `eden/issue-<number>`, opens a draft PR, and labels it `agent:review`. |
| `.github/workflows/eden-agent-review.yml` | Label-triggered PR reviewer. Runs `.eden/github/review_pr.py`, pushes `review:` fixes with `--force-with-lease`, posts a formal PR review, and replies to existing threads. |
| `.eden/github/implement_issue.py` | Eden entry point for one GitHub issue. Creates a named branch sandbox and runs the implementer prompt. |
| `.eden/github/review_pr.py` | Eden entry point for one PR. Runs on the checked-out PR branch and asks the agent to write review JSON files. |
| `.eden/github/factory.py` | Local factory runner. Lists backlog tasks and runs up to `EDEN_FACTORY_MAX_PARALLEL` worktrees concurrently. |
| `.eden/github/implement-issue.md` | Implementation prompt. Reads the GitHub issue and asks for one coherent `eden:` commit. |
| `.eden/github/review-pr.md` | Review prompt. Reads the diff and requires `$REVIEW_OUTPUT` plus `$REVIEW_REPLIES`. |
| `.eden/github/SETUP_TRACKER.md` | Tracker setup contract, especially useful with `--backlog custom`. |
| `.eden/github/REVIEW_OUTPUT.md` | JSON contract for formal GitHub reviews and thread replies. |
| `.eden/Dockerfile`, `.env.example`, `.gitignore`, `CODING_STANDARDS.md` | Same runtime support files as the review templates. |

### GitHub Setup

Create these labels in the repository:

- `agent:implement`
- `agent:review`
- `agent:blocked`
- `agent:in-progress`

Configure the relevant secrets for your selected agent, such as `ANTHROPIC_API_KEY` for Claude Code or `OPENAI_API_KEY` for Codex. If `GITHUB_TOKEN` cannot re-trigger workflows in your repository policy, add `AGENT_PAT` with contents, issues, and pull-request write permissions.

### Review Output

The reviewer prompt writes `$REVIEW_OUTPUT` as the payload for `POST /pulls/{number}/reviews`:

```json
{"event":"COMMENT","body":"Summary.","comments":[]}
```

It writes `$REVIEW_REPLIES` as an array of replies to existing review comments:

```json
[{"commentId":"PRRC_kw...","body":"Fixed in review commit abc123."}]
```

### Custom Trackers

With `--backlog custom`, the Dockerfile, `.env.example`, and factory script intentionally contain `<TODO: ...>` markers. Replace them with commands that list tasks as JSON, view one task, and close a task after commits land.

Read source: `eden/cli/_templates/github_agent_workflows.py`.

## See also

- [Templates](templates.md) — local run templates.
- [GitHub Action](github-action.md) — run an Eden iteration loop in any GitHub workflow.

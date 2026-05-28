"""GitHub label-driven agent workflow template for ``eden init``."""

# ruff: noqa: E501

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._env import render_env_example
from eden.cli._templates.plan_implement_review import (
    _CODING_STANDARDS,
    _DOCKERFILE,
    _GITIGNORE,
)

_AGENT_IMPORT: dict[str, str] = {
    "claude-code": "claude_code",
    "codex": "codex",
    "opencode": "opencode",
    "pi": "pi",
}

_AGENT_CALL: dict[str, str] = {
    "claude-code": 'claude_code("{model}")',
    "codex": 'codex("{model}")',
    "opencode": 'opencode("{model}")',
    "pi": 'pi("{model}")',
}

_IMPLEMENT_WORKFLOW = r"""\
name: Eden Agent Implement

on:
  issues:
    types: [labeled]

jobs:
  implement:
    if: github.event.label.name == 'agent:implement'
    runs-on: ubuntu-latest
    timeout-minutes: 60
    concurrency:
      group: eden-agent-implement-issue-${{{{ github.event.issue.number }}}}
      cancel-in-progress: false
    permissions:
      contents: write
      issues: write
      pull-requests: write

    env:
      ISSUE_NUMBER: ${{{{ github.event.issue.number }}}}
      ISSUE_TITLE: ${{{{ github.event.issue.title }}}}
      GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
      GH_REPO: ${{{{ github.repository }}}}

    steps:
      - name: Detect issue shape
        id: shape
        run: |
          set -euo pipefail
          sub_count=$(gh api "repos/${{GH_REPO}}/issues/${{ISSUE_NUMBER}}/sub_issues" --jq 'length' 2>/dev/null || echo "0")
          owner="${{GH_REPO%/*}}"
          repo="${{GH_REPO#*/}}"
          parent_number=$(gh api graphql \
            -f query='query($owner: String!, $repo: String!, $num: Int!) { repository(owner: $owner, name: $repo) { issue(number: $num) { parent { number } } } }' \
            -f owner="$owner" -f repo="$repo" -F num="$ISSUE_NUMBER" \
            --jq '.data.repository.issue.parent.number // empty' 2>/dev/null || echo "")
          if [ "$sub_count" != "0" ] || [ -n "$parent_number" ]; then
            echo "proceed=false" >> "$GITHUB_OUTPUT"
          else
            echo "proceed=true" >> "$GITHUB_OUTPUT"
          fi
          echo "sub_count=$sub_count" >> "$GITHUB_OUTPUT"
          echo "parent_number=$parent_number" >> "$GITHUB_OUTPUT"

      - name: Refuse unsupported issue shape
        if: steps.shape.outputs.proceed != 'true'
        env:
          SUB_COUNT: ${{{{ steps.shape.outputs.sub_count }}}}
          PARENT_NUMBER: ${{{{ steps.shape.outputs.parent_number }}}}
        run: |
          gh issue edit "$ISSUE_NUMBER" --remove-label "agent:implement" || true
          gh issue edit "$ISSUE_NUMBER" --add-label "agent:blocked" || true
          if [ "$SUB_COUNT" != "0" ]; then
            body="Refused to run: issue #${{ISSUE_NUMBER}} has sub-issues. Label an independently implementable issue instead."
          else
            body="Refused to run: issue #${{ISSUE_NUMBER}} is a sub-issue of #${{PARENT_NUMBER}}. Label the parent workflow or detach this issue first."
          fi
          gh issue comment "$ISSUE_NUMBER" --body "$body"

      - name: Preflight existing PR
        if: steps.shape.outputs.proceed == 'true'
        id: preflight
        run: |
          set -euo pipefail
          existing=$(gh pr list --state open --search "in:body \"#${{ISSUE_NUMBER}}\"" --json number,url,body,author \
            --jq "[.[] | select(.body | test(\"(?i)(closes|fixes|resolves)\\\\s+#${{ISSUE_NUMBER}}\\\\b\"))]")
          refused=false
          existing_pr_url=""
          count=$(echo "$existing" | jq 'length')
          for i in $(seq 0 $((count - 1))); do
            author=$(echo "$existing" | jq -r ".[$i].author.login")
            if gh api "repos/${{GH_REPO}}/collaborators/${{author}}" --silent 2>/dev/null; then
              refused=true
              existing_pr_url=$(echo "$existing" | jq -r ".[$i].url")
              break
            fi
          done
          echo "refused=$refused" >> "$GITHUB_OUTPUT"
          echo "existing_pr_url=$existing_pr_url" >> "$GITHUB_OUTPUT"

      - name: Refuse existing PR
        if: steps.preflight.outputs.refused == 'true'
        env:
          EXISTING_PR_URL: ${{{{ steps.preflight.outputs.existing_pr_url }}}}
        run: |
          gh issue edit "$ISSUE_NUMBER" --remove-label "agent:implement" || true
          gh issue edit "$ISSUE_NUMBER" --add-label "agent:blocked" || true
          gh issue comment "$ISSUE_NUMBER" --body "Refused to run: $EXISTING_PR_URL already targets this issue."

      - name: Checkout
        if: steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{{{ secrets.AGENT_PAT || secrets.GITHUB_TOKEN }}}}

      - name: Set up Python
        if: steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        if: steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        run: |
          python -m pip install --upgrade pip
          python -m pip install eden-agent

      - name: Build sandbox image
        if: steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        run: |
          docker build \
            --build-arg AGENT_UID="$(id -u)" \
            --build-arg AGENT_GID="$(id -g)" \
            -t {image_name} \
            -f .eden/Dockerfile .

      - name: Run implementer
        if: steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        env:
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
        run: python .eden/github/implement_issue.py

      - name: Push branch
        if: success() && steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        env:
          BRANCH: eden/issue-${{{{ env.ISSUE_NUMBER }}}}
        run: git push --force-with-lease origin "$BRANCH"

      - name: Open draft PR
        if: success() && steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        id: open_pr
        env:
          BRANCH: eden/issue-${{{{ env.ISSUE_NUMBER }}}}
        run: |
          title="Fix #${{ISSUE_NUMBER}}: ${{ISSUE_TITLE}}"
          body_file="${{RUNNER_TEMP}}/pr-body.md"
          printf 'Closes #%s\\n\\nImplemented by Eden.\\n' "$ISSUE_NUMBER" > "$body_file"
          pr_url=$(gh pr create --draft --base main --head "$BRANCH" --title "${{title:0:256}}" --body-file "$body_file" | tail -n1)
          echo "pr_number=$(basename "$pr_url")" >> "$GITHUB_OUTPUT"

      - name: Request automated review
        if: success() && steps.open_pr.outputs.pr_number != ''
        env:
          PR_NUMBER: ${{{{ steps.open_pr.outputs.pr_number }}}}
        run: gh pr edit "$PR_NUMBER" --add-label "agent:review"

      - name: Mark blocked on failure
        if: failure() && steps.shape.outputs.proceed == 'true' && steps.preflight.outputs.refused != 'true'
        env:
          RUN_URL: ${{{{ github.server_url }}}}/${{{{ github.repository }}}}/actions/runs/${{{{ github.run_id }}}}
        run: |
          reason="check workflow logs"
          [ -f "${{RUNNER_TEMP}}/failure_reason.txt" ] && reason=$(cat "${{RUNNER_TEMP}}/failure_reason.txt")
          gh issue edit "$ISSUE_NUMBER" --add-label "agent:blocked" || true
          gh issue comment "$ISSUE_NUMBER" --body "`agent:implement` failed: $reason

Workflow run: $RUN_URL"
"""

_REVIEW_WORKFLOW = r"""\
name: Eden Agent Review

on:
  pull_request_target:
    types: [labeled]

jobs:
  review:
    if: github.event.label.name == 'agent:review'
    runs-on: ubuntu-latest
    timeout-minutes: 60
    concurrency:
      group: eden-agent-review-pr-${{{{ github.event.pull_request.number }}}}
      cancel-in-progress: false
    permissions:
      contents: write
      pull-requests: write

    env:
      PR_NUMBER: ${{{{ github.event.pull_request.number }}}}
      BRANCH: ${{{{ github.event.pull_request.head.ref }}}}
      BRANCH_HEAD_SHA: ${{{{ github.event.pull_request.head.sha }}}}
      GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}

    steps:
      - name: Checkout PR branch
        uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
          fetch-depth: 0

      - name: Prepare branch
        run: |
          git fetch origin main:main || git fetch origin main
          git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH"
          git config user.name "eden-agent[bot]"
          git config user.email "eden-agent[bot]@users.noreply.github.com"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install eden-agent

      - name: Build sandbox image
        run: |
          docker build \
            --build-arg AGENT_UID="$(id -u)" \
            --build-arg AGENT_GID="$(id -g)" \
            -t {image_name} \
            -f .eden/Dockerfile .

      - name: Run reviewer
        env:
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
          REVIEW_OUTPUT: ${{{{ runner.temp }}}}/review_payload.json
          REVIEW_REPLIES: ${{{{ runner.temp }}}}/review_replies.json
        run: python .eden/github/review_pr.py

      - name: Push review fixes
        if: success()
        run: |
          set +e
          git push --force-with-lease="refs/heads/$BRANCH:$BRANCH_HEAD_SHA" origin "$BRANCH" 2> push_err.txt
          status=$?
          set -e
          if [ $status -ne 0 ]; then
            cat push_err.txt
            exit $status
          fi

      - name: Post PR review
        if: success()
        env:
          PAYLOAD: ${{{{ runner.temp }}}}/review_payload.json
        run: |
          [ -s "$PAYLOAD" ] || echo '{"event":"COMMENT","body":"Eden review completed.","comments":[]}' > "$PAYLOAD"
          gh api --method POST "repos/{owner}/{repo}/pulls/${{PR_NUMBER}}/reviews" --input "$PAYLOAD"

      - name: Post thread replies
        if: success()
        env:
          REPLIES: ${{{{ runner.temp }}}}/review_replies.json
        run: |
          [ -s "$REPLIES" ] || echo '[]' > "$REPLIES"
          count=$(jq 'length' "$REPLIES")
          for i in $(seq 0 $((count - 1))); do
            commentId=$(jq -r ".[$i].commentId" "$REPLIES")
            body=$(jq -r ".[$i].body" "$REPLIES")
            rest_id=$(gh api graphql -f query="query(\\$id:ID!){ node(id:\\$id){ ... on PullRequestReviewComment { databaseId } } }" -F id="$commentId" --jq '.data.node.databaseId')
            gh api --method POST "repos/{owner}/{repo}/pulls/${{PR_NUMBER}}/comments/${{rest_id}}/replies" -f body="$body"
          done
"""

_IMPLEMENT_PROMPT = """\
# GitHub Issue

Issue #{{{{ISSUE_NUMBER}}}}: {{{{ISSUE_TITLE}}}}

!`gh issue view {{{{ISSUE_NUMBER}}}} --comments`

# Task

Implement the issue on branch `{{{{SOURCE_BRANCH}}}}`.

Workflow:
1. Read the issue and relevant files.
2. Make the smallest coherent code change.
3. Run focused tests and linters.
4. Commit with an `eden:` prefix.

When complete, output:

<promise>COMPLETE</promise>
"""

_REVIEW_PROMPT = """\
# Pull Request Review

Review branch `{{{{SOURCE_BRANCH}}}}` against `{{{{TARGET_BRANCH}}}}`.

## Diff

!`git diff {{{{TARGET_BRANCH}}}}...{{{{SOURCE_BRANCH}}}}`

## Existing review comments

!`gh pr view {{{{PR_NUMBER}}}} --json comments,reviews`

## Standards

Read `.eden/CODING_STANDARDS.md`.

# Required Output

Write a GitHub review payload to `$REVIEW_OUTPUT`:

```json
{{"event":"COMMENT","body":"summary","comments":[]}}
```

Write thread replies to `$REVIEW_REPLIES`:

```json
[{{"commentId":"PRRC_kw...","body":"reply"}}]
```

If changes are needed, commit them with `review:`. Then output:

<promise>COMPLETE</promise>
"""

_IMPLEMENT_SCRIPT = """\
from __future__ import annotations

import os

from eden import BranchStrategy, create_sandbox, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider

issue_number = os.environ["ISSUE_NUMBER"]
issue_title = os.environ["ISSUE_TITLE"]
branch = f"eden/issue-{{issue_number}}"

with create_sandbox(
    sandbox=sandbox_provider.provider({image_arg}),
    branch_strategy=BranchStrategy.named(branch),
    name=f"github-issue-{{issue_number}}",
) as sandbox:
    result = sandbox.run(
        name=f"implement-{{issue_number}}",
        agent={agent_call},
        prompt_file=".eden/github/implement-issue.md",
        prompt_args={{"ISSUE_NUMBER": issue_number, "ISSUE_TITLE": issue_title}},
        max_iterations=10,
    )
    if not result.commits:
        raise SystemExit("implementer produced no commits")
"""

_REVIEW_SCRIPT = """\
from __future__ import annotations

import os
from pathlib import Path

from eden import BranchStrategy, create_sandbox, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider

pr_number = os.environ["PR_NUMBER"]
branch = os.environ["BRANCH"]

Path(os.environ["REVIEW_OUTPUT"]).write_text(
    '{{"event":"COMMENT","body":"Eden review completed.","comments":[]}}',
    encoding="utf-8",
)
Path(os.environ["REVIEW_REPLIES"]).write_text("[]", encoding="utf-8")

with create_sandbox(
    sandbox=sandbox_provider.provider({image_arg}),
    branch_strategy=BranchStrategy.head(),
    name=f"github-review-{{pr_number}}",
) as sandbox:
    sandbox.run(
        name=f"review-{{pr_number}}",
        agent={agent_call},
        prompt_file=".eden/github/review-pr.md",
        prompt_args={{"PR_NUMBER": pr_number}},
        max_iterations=3,
    )
"""

_FACTORY_SCRIPT = """\
from __future__ import annotations

import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from eden import BranchStrategy, create_sandbox, create_worktree, {agent_import}
from eden.sandboxes import {sandbox} as sandbox_provider

MAX_PARALLEL = int(os.environ.get("EDEN_FACTORY_MAX_PARALLEL", "4"))


def _tasks() -> list[dict[str, str]]:
    raw = os.popen({list_tasks_command!r}).read()
    return json.loads(raw or "[]")


def _run_task(task: dict[str, str]) -> str:
    task_id = str(task["id"])
    branch = f"eden/factory/{{task_id}}"
    original_cwd = os.getcwd()
    with create_worktree(
        branch_strategy=BranchStrategy.named(branch),
    ) as worktree:
        try:
            os.chdir(worktree.worktree_path)
            with create_sandbox(
                sandbox=sandbox_provider.provider({image_arg}),
                branch_strategy=BranchStrategy.head(),
            ) as sandbox:
                result = sandbox.run(
                    name=f"factory-{{task_id}}",
                    agent={agent_call},
                    prompt_file=".eden/github/implement-issue.md",
                    prompt_args={{
                        "ISSUE_NUMBER": task_id,
                        "ISSUE_TITLE": str(task.get("title", task_id)),
                    }},
                    max_iterations=10,
                )
                return f"{{task_id}}: {{len(result.commits)}} commits on {{branch}}"
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    tasks = _tasks()[:MAX_PARALLEL]
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futures = [pool.submit(_run_task, task) for task in tasks]
        for future in as_completed(futures):
            print(future.result())
"""

_SETUP_TRACKER = """\
# Custom Tracker Setup

This scaffold is ready for GitHub Actions, but the selected backlog manager is
`{backlog_name}`. If it is `custom`, replace every `<TODO: ...>` command in
`.eden/github/factory.py`, `.eden/Dockerfile`, and `.eden/.env.example` before
running the factory.

Tracker commands should follow this contract:

- list: print JSON array objects with `id`, `title`, and optional `body`.
- view: print one task body for a stable id.
- close: mark a task complete only after tests pass and commits exist.

For GitHub-backed workflows, create these labels:

- `agent:implement`
- `agent:review`
- `agent:blocked`
- `agent:in-progress`
"""

_REVIEW_CONTRACT = """\
# GitHub Review Output Contract

`.eden/github/review-pr.md` asks the reviewer to write two files.

`$REVIEW_OUTPUT` is sent to `POST /pulls/{number}/reviews`:

```json
{{"event":"COMMENT","body":"Summary.","comments":[]}}
```

`$REVIEW_REPLIES` is an array of replies to existing review comments:

```json
[{{"commentId":"PRRC_kw...","body":"Fixed in review commit abc123."}}]
```

Keep payloads small. If the reviewer changes code, it should commit with a
`review:` prefix before writing the payload.
"""


def render_github_agent_workflows(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return files for GitHub label-driven Eden agent workflows."""
    if agent not in _AGENT_IMPORT:
        raise ValueError(f"unsupported agent for github-agent-workflows: {agent!r}")
    agent_import = _AGENT_IMPORT[agent]
    agent_call = _AGENT_CALL[agent].format(model=model)
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)
    script_args = {
        "agent_import": agent_import,
        "agent_call": agent_call,
        "sandbox": sandbox,
        "image_arg": image_arg,
    }
    return {
        "../.github/workflows/eden-agent-implement.yml": _render_workflow(
            _IMPLEMENT_WORKFLOW,
            image_name=image_name,
        ),
        "../.github/workflows/eden-agent-review.yml": _render_workflow(
            _REVIEW_WORKFLOW,
            image_name=image_name,
        ),
        "Dockerfile": _DOCKERFILE.format(backlog_install=backlog.dockerfile_install),
        "github/implement_issue.py": _IMPLEMENT_SCRIPT.format(**script_args),
        "github/review_pr.py": _REVIEW_SCRIPT.format(**script_args),
        "github/factory.py": _FACTORY_SCRIPT.format(
            **script_args,
            list_tasks_command=backlog.list_tasks_command,
        ),
        "github/implement-issue.md": _IMPLEMENT_PROMPT,
        "github/review-pr.md": _REVIEW_PROMPT,
        "github/SETUP_TRACKER.md": _SETUP_TRACKER.format(backlog_name=backlog.name),
        "github/REVIEW_OUTPUT.md": _REVIEW_CONTRACT,
        "CODING_STANDARDS.md": _CODING_STANDARDS,
        ".env.example": env_example,
        ".gitignore": _GITIGNORE,
    }


def _render_workflow(text: str, *, image_name: str) -> str:
    """Undo Python-format escaping used for GitHub Actions expressions."""
    return (
        text.removeprefix("\\\n")
        .replace("{image_name}", image_name)
        .replace("${{{{", "${{")
        .replace("}}}}", "}}")
        .replace("${{GH_REPO%/*}}", "${GH_REPO%/*}")
        .replace("${{GH_REPO#*/}}", "${GH_REPO#*/}")
        .replace("${{author}}", "${author}")
        .replace("${{ISSUE_TITLE}}", "${ISSUE_TITLE}")
        .replace("${{title:0:256}}", "${title:0:256}")
        .replace("${{GH_REPO}}", "${GH_REPO}")
        .replace("${{ISSUE_NUMBER}}", "${ISSUE_NUMBER}")
        .replace("${{PARENT_NUMBER}}", "${PARENT_NUMBER}")
        .replace("${{SUB_COUNT}}", "${SUB_COUNT}")
        .replace("${{EXISTING_PR_URL}}", "${EXISTING_PR_URL}")
        .replace("${{RUNNER_TEMP}}", "${RUNNER_TEMP}")
        .replace("${{BRANCH}}", "${BRANCH}")
        .replace("${{BRANCH_HEAD_SHA}}", "${BRANCH_HEAD_SHA}")
        .replace("${{PR_NUMBER}}", "${PR_NUMBER}")
        .replace("${{rest_id}}", "${rest_id}")
        .replace("\\\\$", "\\$")
    )


__all__ = ["render_github_agent_workflows"]

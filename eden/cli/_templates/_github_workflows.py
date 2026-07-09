"""GitHub Actions workflow text for the GitHub agent template."""

# ruff: noqa: E501

from __future__ import annotations

IMPLEMENT_WORKFLOW = r"""\
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

REVIEW_WORKFLOW = r"""\
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


def render_workflow(text: str, *, image_name: str) -> str:
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


__all__ = ["IMPLEMENT_WORKFLOW", "REVIEW_WORKFLOW", "render_workflow"]

"""Static assets for the sequential-reviewer template."""

from __future__ import annotations

DOCKERFILE = """\
FROM python:3.13-slim

ARG AGENT_UID=1000
ARG AGENT_GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \\
    ca-certificates curl git gnupg nodejs npm \\
    && rm -rf /var/lib/apt/lists/*

{backlog_install}

RUN groupadd --gid ${{AGENT_GID}} --non-unique agent \\
    && useradd --uid ${{AGENT_UID}} --non-unique --gid ${{AGENT_GID}} \\
       --create-home --home-dir /home/agent --shell /bin/sh agent

WORKDIR /workspace
USER ${{AGENT_UID}}:${{AGENT_GID}}
ENV NPM_CONFIG_PREFIX=/home/agent/.npm-global
ENV PATH="/home/agent/.local/bin:/home/agent/.npm-global/bin:${{PATH}}"

{agent_install}

CMD ["sleep", "infinity"]
"""


MAIN_PY = """\
\"\"\"Entry point for this Eden sequential-reviewer project.

Run with: python .eden/main.py
\"\"\"

import time

from eden import {agent_import}, create_sandbox
from eden.providers._types import BranchStrategy
from eden.sandboxes import {sandbox} as sandbox_provider

MAX_ITERATIONS = 10


if __name__ == "__main__":
    for i in range(1, MAX_ITERATIONS + 1):
        print(f"\\n=== Iteration {{i}}/{{MAX_ITERATIONS}} ===\\n")

        branch = f"eden/seq-reviewer/{{int(time.time())}}-{{i}}"

        with create_sandbox(
            sandbox=sandbox_provider.provider({image_arg}),
            branch_strategy=BranchStrategy.named(branch),
            name=f"seq-{{i}}",
        ) as sandbox:
            implement = sandbox.run(
                name="implementer",
                agent={agent_call},
                prompt_file=".eden/implement-prompt.md",
                max_iterations=20,
            )
            if not implement.commits:
                print("Implementer made no commits; skipping review.")
                continue

            print(f"\\nImplementation complete on {{implement.branch}} "
                  f"({{len(implement.commits)}} commits)")

            review = sandbox.run(
                name="reviewer",
                agent={agent_call},
                prompt_file=".eden/review-prompt.md",
                max_iterations=1,
            )
            print(f"Review complete: {{review.completion_signal}}")
"""


GITIGNORE = """\
# Eden runtime artifacts
.eden/logs/
.eden/sessions/
.eden/worktrees/
.eden/isolated/
.env
"""


__all__ = [
    "DOCKERFILE",
    "GITIGNORE",
    "MAIN_PY",
]

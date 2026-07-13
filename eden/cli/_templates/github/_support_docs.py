"""Support document templates for GitHub agent workflows."""

from __future__ import annotations

SETUP_TRACKER = """\
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

REVIEW_CONTRACT = """\
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

__all__ = ["REVIEW_CONTRACT", "SETUP_TRACKER"]

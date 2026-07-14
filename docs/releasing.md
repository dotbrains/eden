# Releasing

Eden publishes tagged versions through PyPI Trusted Publishing.

---

## New version

1. Bump `pyproject.toml` `version` (semver).
2. Commit: `chore: bump version to vX.Y.Z`.
3. Push to `main`. CI must be green.
4. Tag from `main`:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. The `.github/workflows/release.yml` workflow runs automatically and publishes to PyPI. No long-lived tokens are required.

## First-time PyPI Trusted Publishing setup

Required once, before the first publish:

1. Visit https://pypi.org/manage/project/eden-agent/settings/publishing/ (project owner only).
2. Add a new pending publisher:
   - Owner: `dotbrains`
   - Repository: `eden`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. Save. The first tag push will succeed.

Repeat the steps on https://test.pypi.org for the `testpypi` environment if you want to dry-run release candidates.

## Test releases

Tag with a `-rc` suffix (for example, `v0.1.0-rc1`) to publish to TestPyPI instead of production PyPI. The release workflow's tag-pattern logic routes `-rc` tags to the test repository.

## See also

- [Development](development.md) — local setup, test markers, quality gates, and contributing.
- [CI workflow](../.github/workflows/ci.yml) — required checks before tagging.
- [Release workflow](../.github/workflows/release.yml) — tag-triggered publisher.

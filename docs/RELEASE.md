# Release Process

Two automated workflows, both version-driven. Never hand-edit `dist/` or
upload artifacts manually.

```
bump version + CHANGELOG  →  tag v<version>  →  release.yml  →  GitHub Release
                                                publish.yml (manual)  →  PyPI
```

## 1. Prepare the release

1. All tests and evals green locally:
   ```bash
   python -m pytest tests -q
   python -m evals.runner
   ```
2. Update `CHANGELOG.md`: rename `[Unreleased]` to `[<version>] - <YYYY-MM-DD>`
   (or add a new section). Release notes are extracted from here — a version
   without a changelog section fails the release.
3. Bump `version` in `pyproject.toml`.
4. Commit, push.

## 2. Tag and publish the GitHub Release

```bash
git tag v0.2.0
git push origin v0.2.0
```

`.github/workflows/release.yml` then:

1. Verifies the tag equals `pyproject.toml`'s version (mismatch = red X).
2. Extracts the `[<version>]` section of CHANGELOG.md as release notes
   (missing section = red X).
3. Builds sdist + wheel, smoke-installs the wheel and runs
   `regression-firewall --version`.
4. Creates the GitHub Release with both artifacts attached.

## 3. Publish to PyPI (optional, manual)

`.github/workflows/publish.yml` is a **manual** (`workflow_dispatch`) job
using PyPI Trusted Publishers (OIDC — no API token stored in the repo).
One-time setup:

1. On pypi.org → *Account settings → Publishing* (or the project's
   *Publishing* page), add a **pending Trusted Publisher**:
   - PyPI project name: `regression-firewall`
   - Owner: `Tong-bit-art` · Repository: `regression-firewall`
   - Workflow name: `publish.yml` · Environment: `pypi`
2. In this repository → *Settings → Environments*, create an environment
   named `pypi` (no protection rules needed; reviewers optional).

Then: *Actions → Publish to PyPI → Run workflow*. The workflow refuses to
run if the current `pyproject.toml` version has no git tag — always tag and
run `release.yml` first, so every PyPI upload corresponds to a public GitHub
Release.

## 4. After the release

- Update `HANDOFF.md` (current state table, remaining work).
- Keep the benchmark evidence honest: a release that changed detection
  behavior needs fresh eval/benchmark numbers, and the fresh-holdout corpus
  must be re-selected once consumed (see `docs/BENCHMARK_DESIGN.md`).

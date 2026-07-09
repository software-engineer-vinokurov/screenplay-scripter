# Release Rules
<!-- last-analyzed: 2026-07-09T13:34:00Z -->

## Version Sources
- `pyproject.toml` → `version = "X.Y.Z"` (single source of truth)
- `uv.lock` → updated automatically by `uv sync`/`uv lock` after version bump

## Release Trigger
Push an annotated git tag `vX.Y.Z` matching `pyproject.toml`'s version.
`.github/workflows/release.yml` runs on `push: tags: v[0-9]+.[0-9]+.[0-9]+` and
handles test, build, PyPI publish, GitHub release creation, and the Homebrew
tap update — fully automated, no manual steps remain. Verified end-to-end on
v0.5.1 (PyPI + GitHub release) and v0.5.2 (adds Homebrew tap automation).

## Test Gate
```
uv run pytest
```
Runs in CI (`release.yml`) on `macos-latest` before publish; also requires
`brew install cliclick` (one test shells out to the real binary). Run locally
before tagging too.

## Registry / Distribution
- **Homebrew**: `brew tap software-engineer-vinokurov/tap` + `brew install screenplay-scripter`
- **PyPI**: `uv tool install screenplay-scripter` or `pip install screenplay-scripter`
- CI publishes via `uv build && uv publish`, authenticated with the
  `PYPI_API_TOKEN` repo secret (`UV_PUBLISH_TOKEN` env var). Token is
  project-scoped ("Project: screenplay-scripter") on PyPI.
- PyPI project is under the personal account for now; a `sev` PyPI org invite
  is pending — transfer ownership via the PyPI web UI once accepted. If a new
  CI token is minted after the transfer, update `PYPI_API_TOKEN` accordingly.
- Homebrew formula lives in the `software-engineer-vinokurov/homebrew-tap` GitHub
  repo (`Formula/screenplay-scripter.rb`). CI's "Update Homebrew tap" step
  clones that repo, regex-replaces only the top-level `url`/`sha256` pair
  (leaves per-dependency `resource` blocks untouched), commits, and pushes
  straight to `main` using the `HOMEBREW_TAP_TOKEN` secret (fine-grained PAT,
  scoped only to `homebrew-tap`, Contents: read/write).
- This automation only bumps `url`/`sha256`. If a dependency version changes
  (i.e. `uv.lock` resolves a new version for something also pinned as a
  `resource` block in the formula), the formula's resource blocks need a
  manual refresh too — CI does not detect or handle that case.
- The tap step has `continue-on-error: true` and is the last step in the job:
  if `HOMEBREW_TAP_TOKEN` is ever missing/expired, it prints a `::warning::`
  and exits non-zero without failing the run — PyPI publish and the GitHub
  release have already succeeded by that point regardless.

## Release Notes Strategy
No CHANGELOG.md. CI creates the GitHub release with `gh release create --generate-notes`
(auto-generated from merged PRs/commits since the last tag). Edit the release body by hand
afterward if you want the "## What's new" style used in v0.1.0–v0.5.0.

## CI Workflow Files
- `.github/workflows/release.yml` — test, build, PyPI publish, GitHub release,
  Homebrew tap update, all on tag push.
- `.github/dependabot.yml` — weekly dependency PRs for the `uv` ecosystem and
  GitHub Actions versions used in `release.yml`. Email-on-PR-open is a
  per-user GitHub notification setting, not repo config (Settings > Notifications,
  or per-repo Watch > Custom > Pull requests).

## First-Time Setup Gaps
None remaining. Full pipeline (bump version → commit → tag → push) is
hands-off end to end, proven on v0.5.2.

## Current Release State
- Latest version: v0.5.2 (PyPI, GitHub release, Homebrew tap all in sync)
- Git tags: v0.1.0, v0.2.0, v0.3.0, v0.4.0, v0.5.0, v0.5.1, v0.5.2
- Required repo secrets (in `screenplay-scripter`): `PYPI_API_TOKEN`, `HOMEBREW_TAP_TOKEN`
- Standard release procedure going forward:
  1. Bump `version` in `pyproject.toml`
  2. `uv lock` (updates `uv.lock`)
  3. `uv run pytest` locally to confirm green before tagging
  4. Commit: `chore(release): bump version to vX.Y.Z`
  5. `git tag -a vX.Y.Z -m "vX.Y.Z"`
  6. `git push origin main && git push origin vX.Y.Z`
  7. CI takes over: tests, build, PyPI publish, GitHub release, Homebrew tap update
  8. Optionally hand-edit the GitHub release body for a curated "## What's new" section

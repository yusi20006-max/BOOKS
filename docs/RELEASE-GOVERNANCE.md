# Release Governance

## Canonical branches

- `main` is the canonical development and release branch.
- Feature/fix/chore work is merged through pull requests into `main`.
- Release tags must point to a verified commit reachable from `main`.
- The repository default branch must remain `main`.

## Protected-main policy

The repository settings must enforce the following on `main`:

- Require a pull request before merging.
- Require the repository CI status check to pass before merging.
- Block direct pushes.
- Block force-pushes and branch deletion.
- Keep administrators subject to the same merge requirements where GitHub permits this policy.

The exact required check name should match the stable CI check exposed by `.github/workflows/ci.yml` (currently the workflow's `Lint + tests + smoke` job, together with its required dependency `Docker build`).

## Version and tags

- The release version is defined by `src/books/__init__.py`.
- Packaging consumes that value through setuptools dynamic metadata.
- Release tags use the `vMAJOR.MINOR.PATCH` format.
- Each release tag must point to the exact verified release commit on `main` (the latest release is `v1.1.0`).
- Do not move or recreate an existing release tag.
- Never create a release tag from a feature branch.

## Release gate

Before creating a release tag, all of the following must be green on the exact release commit:

1. Ruff lint.
2. Full pytest suite.
3. Offline smoke and migration checks.
4. REST/MCP runtime checks.
5. Sync and backup release E2E coverage.
6. Reproducible sdist and wheel build.
7. Clean wheel installation outside the source tree.
8. Installed-package migration, health, OpenAPI, authenticated MCP, and sync checks.
9. Docker image build.
10. Final E2E audit with no unresolved release-blocking gaps.

The release gate is implemented by `scripts/release-gate.sh` and CI.

## Release checklist

- [ ] `main` is the repository default branch.
- [ ] `main` protection is enabled with required CI checks.
- [ ] Working tree is clean.
- [ ] Version source and package metadata agree.
- [ ] Full CI is green for the exact release commit.
- [ ] Final E2E audit is complete.
- [ ] Release notes/changelog are prepared.
- [ ] Create the release tag (currently `v1.1.0`) only after all checks above pass.
- [ ] Verify the tag points at the intended `main` commit.
- [ ] Publish the GitHub release from that tag.

## Current release boundary

Issue #291 established the governance contract and documentation. Releases `v1.0.0` and `v1.1.0` have since been created from verified `main` commits after the full gate passed. This checklist applies to the current release (`v1.1.0`) and to every subsequent tag.
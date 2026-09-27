# CI/CD

BOOKS uses GitHub Actions for pull requests and pushes to `main`.

## Required PR checks

The CI workflow runs:

1. `ruff check src tests`
2. `python -m pytest -q`
3. Offline SQLite smoke/migration check
4. Docker image build after tests pass

The job name to require in repository branch protection is:

- `test` — Lint + tests + smoke

The Docker job depends on `test`.

## Releases

Pushing a semantic tag matching `v*` starts the release workflow, which creates a GitHub Release with generated notes.

## Local equivalent

```bash
python -m pip install ".[dev]"
ruff check src tests
python -m pytest -q
docker build --tag books:local .
```

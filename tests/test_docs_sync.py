"""Documentation-drift guards for issue #340.

Docs are updated per release instead of per phase, so drift creeps in. These
tests fail when the environment-variable surface, the AI configuration, the
release version, or the required CI check name diverge between code and docs.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Quoted ALL_CAPS_WITH_UNDERSCORE literals in src/books that are not
# environment variables (validation field names). Anything else shaped like an
# env var must be documented in .env.example.
NON_ENV_LITERALS = frozenset({"ISBN_10", "ISBN_13"})

ENV_VAR_PATTERN = re.compile(r'"([A-Z][A-Z0-9_]*_[A-Z0-9_]+)"')


def _env_vars_in_source() -> set[str]:
    found: set[str] = set()
    for path in sorted((ROOT / "src" / "books").rglob("*.py")):
        found.update(ENV_VAR_PATTERN.findall(path.read_text(encoding="utf-8")))
    return found - NON_ENV_LITERALS


def _env_example_keys() -> set[str]:
    keys = set()
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def test_env_example_documents_every_variable_the_code_reads():
    missing = _env_vars_in_source() - _env_example_keys()
    assert not missing, f".env.example is missing: {sorted(missing)}"


def test_env_example_user_agent_matches_the_config_default():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    config = (ROOT / "src" / "books" / "config.py").read_text(encoding="utf-8")
    default = re.search(
        r'BOOKS_USER_AGENT",\s*\n\s*"([^"]+)"', config
    ).group(1)
    assert f"BOOKS_USER_AGENT={default}" in example


def test_readme_documents_the_ai_variables():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ai_vars = {name for name in _env_vars_in_source() if name.startswith("BOOKS_AI_")}
    assert ai_vars, "expected BOOKS_AI_* variables in src/books"
    missing = {name for name in ai_vars if name not in readme}
    assert not missing, f"README.md does not mention: {sorted(missing)}"


def test_release_notes_state_the_current_version():
    from books import __version__

    title = (ROOT / "RELEASE.md").read_text(encoding="utf-8").splitlines()[0]
    assert __version__ in title, f"RELEASE.md title is stale: {title!r}"


def test_ci_docs_agree_on_the_required_check_name():
    ci_cd = (ROOT / "docs" / "CI-CD.md").read_text(encoding="utf-8")
    governance = (ROOT / "docs" / "RELEASE-GOVERNANCE.md").read_text(encoding="utf-8")
    required = "Lint + tests + smoke"
    assert required in ci_cd
    assert required in governance
    # The workflow exposes this exact job name (id `test`).
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f"name: {required}" in workflow

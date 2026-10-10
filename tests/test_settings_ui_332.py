"""Settings panel regressions for issue #332.

«تنظیمات» must render a Persian, read-only panel of the effective
configuration — no issue-tracking text, the real database path, and never a
secret value (only configured/not-configured indicators).
"""

from __future__ import annotations

PLACEHOLDER = "تنظیمات برنامه در Issueهای مرتبط تکمیل می‌شود."

SECRET_VARS = {
    "GOOGLE_BOOKS_API_KEY": "dummy-google-key-123",
    "BOOKS_API_TOKEN": "dummy-api-token-456",
    "BOOKS_AI_API_KEY": "dummy-ai-key-789",
    "BOOKS_AI_FALLBACK_API_KEY": "dummy-fallback-key-000",
}

ELEMENT_KINDS = (
    "markdown",
    "caption",
    "subheader",
    "header",
    "text",
    "code",
    "info",
    "success",
    "warning",
    "error",
    "exception",
    "json",
    "html",
)


def _rendered_values(session) -> list[str]:
    values: list[str] = []
    for kind in ELEMENT_KINDS:
        for block in getattr(session.at, kind, []):
            value = getattr(block, "value", None)
            if isinstance(value, str):
                values.append(value)
    return values


def test_settings_panel_replaces_the_placeholder_and_hides_secrets(
    app_session, monkeypatch
):
    for name, secret in SECRET_VARS.items():
        monkeypatch.setenv(name, secret)

    session = app_session
    session.open("تنظیمات")
    values = _rendered_values(session)
    blob = "\n".join(values)

    assert not session.at.exception, session.at.exception
    # AC1: no placeholder, no issue-tracking text.
    assert PLACEHOLDER not in blob
    assert "Issue" not in blob
    assert "پیکربندی مؤثر برنامه" in blob
    # AC3: reflects load_settings() for the active BOOKS_DB_PATH.
    assert str(session.db_path) in blob
    assert "BOOKS_DB_PATH" in blob
    assert "BOOKS_HOST" in blob and "BOOKS_PORT" in blob
    assert "OPEN_LIBRARY_BASE_URL" in blob
    assert "BOOKS_AI_BASE_URL" in blob and "BOOKS_AI_MODEL" in blob
    # AC2: configured secrets are announced, never printed.
    assert "تنظیم شده" in blob
    for name, secret in SECRET_VARS.items():
        assert secret not in blob, f"secret {name} was rendered"
        assert f"`{name}`:" in blob


def test_settings_panel_renders_with_data_present(app_session):
    session = app_session
    session.seed_book(title="کتاب آزمون", authors=("نویسنده آزمون",))
    session.open("تنظیمات")

    values = _rendered_values(session)
    assert not session.at.exception, session.at.exception
    assert PLACEHOLDER not in "\n".join(values)
    assert str(session.db_path) in "\n".join(values)


def test_settings_panel_shows_unconfigured_state(app_session, monkeypatch):
    for name in SECRET_VARS:
        monkeypatch.delenv(name, raising=False)

    session = app_session
    session.open("تنظیمات")
    blob = "\n".join(_rendered_values(session))

    assert "تنظیم نشده" in blob
    assert "تنظیم شده" not in blob.replace("تنظیم نشده", "")

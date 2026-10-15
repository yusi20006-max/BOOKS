from __future__ import annotations

from books.db import Database
from books.settings_sync import SettingsSyncConflict
from books.settings_sync_ui import local_values, save_local_value


def _button(app_session, label: str):
    matches = [button for button in app_session.at.button if label in (button.label or "")]
    assert matches, f"button containing {label!r} not found"
    matches[0].click()
    app_session.at.run()
    assert not app_session.at.exception, app_session.at.exception
    return app_session.at


def _configure_sync(app_session, *, enabled=True):
    app_session.open("تنظیمات")
    at = app_session.at
    fields = {widget.label: widget for widget in at.text_input}
    enabled_widget = next(widget for widget in at.checkbox if widget.label == "فعال‌سازی همگام‌سازی (اختیاری)")
    enabled_widget.set_value(enabled)
    fields["نشانی سرویس همگام‌سازی"].set_value("https://sync.example.test")
    fields["شناسه این دستگاه"].set_value("phone")
    fields["Bearer token (فقط برای این نشست)"].set_value("ui-test-token")
    _button(app_session, "ذخیره تنظیمات همگام‌سازی")
    return app_session.at


def test_real_settings_ui_is_opt_in_and_does_not_show_or_persist_token(app_session):
    app_session.open("تنظیمات")
    assert any("همگام‌سازی غیرفعال است" in block.value for block in app_session.at.info)
    assert not any(button.label == "ارسال مقدار به دستگاه‌های دیگر" for button in app_session.at.button)

    _configure_sync(app_session)
    assert "settings_sync_token" in app_session.at.session_state
    assert app_session.at.session_state["settings_sync_token"] == "ui-test-token"
    with app_session.repository.db.connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'settings_sync_%'"
        ).fetchall()
        for row in rows:
            columns = {col["name"] for col in conn.execute(f"PRAGMA table_info({row['name']})")}
            assert "token" not in columns
            assert "bearer_token" not in columns
        persisted = conn.execute(
            "SELECT endpoint, device_id, enabled FROM settings_sync_ui_preferences WHERE id=1"
        ).fetchone()
        assert persisted["endpoint"] == "https://sync.example.test"
        assert persisted["device_id"] == "phone"
        assert persisted["enabled"] == 1

    visible = "\n".join(
        [block.value for block in app_session.at.markdown]
        + [block.value for block in app_session.at.caption]
        + [block.value for block in app_session.at.success]
        + [block.value for block in app_session.at.info]
        + [block.value for block in app_session.at.error]
    )
    assert "ui-test-token" not in visible


def test_real_settings_ui_push_and_pull_paths(app_session, monkeypatch):
    calls = {"push": [], "pull": []}

    class FakeClient:
        def __init__(self, endpoint, *, token, timeout):
            assert endpoint == "https://sync.example.test"
            assert token == "ui-test-token"
            assert timeout > 0

        def push(self, **kwargs):
            calls["push"].append(kwargs)
            return {"applied": True, "version": 1}

        def pull(self, since):
            calls["pull"].append(since)
            return {
                "revision": 2,
                "changes": [
                    {"key": "font_size", "value": 16, "version": 2},
                    {"key": "api-key", "value": "must-not-persist", "version": 3},
                ],
            }

    monkeypatch.setattr("books.settings_sync.SettingsSyncClient", FakeClient)
    _configure_sync(app_session)

    fields = {widget.label: widget for widget in app_session.at.text_input}
    fields["کلید تنظیم غیرمحرمانه"].set_value("theme")
    fields['مقدار به قالب JSON (مثلاً "dark"، 16 یا true)'].set_value('"dark"')
    _button(app_session, "ارسال مقدار به دستگاه‌های دیگر")
    assert calls["push"] == [
        {"device_id": "phone", "key": "theme", "value": "dark", "base_version": 0}
    ]
    assert any("مقدار ارسال و نسخه محلی به‌روزرسانی شد" in item.value for item in app_session.at.success)

    _button(app_session, "دریافت تغییرات از سرور")
    assert calls["pull"] == [0]
    values = __import__("books.settings_sync_ui", fromlist=["local_values"]).local_values(
        app_session.repository.db
    )
    assert values["theme"] == {"value": "dark", "version": 1}
    assert values["font_size"] == {"value": 16, "version": 2}
    assert "api-key" not in values
    from books.settings_sync_ui import load_sync_preferences
    assert load_sync_preferences(app_session.repository.db)["revision"] == 2


def test_real_settings_ui_conflict_preserves_local_value_and_offers_resolution(
    app_session, monkeypatch
):
    class FakeClient:
        def __init__(self, endpoint, *, token, timeout):
            pass

        def push(self, **kwargs):
            raise SettingsSyncConflict(
                key=kwargs["key"], current_version=2
            )

        def pull(self, since):
            return {
                "revision": 2,
                "changes": [{"key": "theme", "value": "remote", "version": 2}],
            }

    monkeypatch.setattr("books.settings_sync.SettingsSyncClient", FakeClient)
    _configure_sync(app_session)
    db = Database(app_session.db_path)
    save_local_value(db, key="theme", value="local", version=1)

    fields = {widget.label: widget for widget in app_session.at.text_input}
    fields["کلید تنظیم غیرمحرمانه"].set_value("theme")
    fields['مقدار به قالب JSON (مثلاً "dark"، 16 یا true)'].set_value('"local"')
    _button(app_session, "ارسال مقدار به دستگاه‌های دیگر")
    assert any("تعارض برای" in item.value for item in app_session.at.error)
    assert local_values(db)["theme"] == {"value": "local", "version": 1}

    _button(app_session, "دریافت تغییرات از سرور")
    assert any("انتخاب مقدار سرور" in (button.label or "") for button in app_session.at.button)
    assert local_values(db)["theme"] == {"value": "local", "version": 1}

    _button(app_session, "انتخاب مقدار سرور")
    assert local_values(db)["theme"] == {"value": "remote", "version": 2}
    assert "settings_sync_conflict" not in app_session.at.session_state

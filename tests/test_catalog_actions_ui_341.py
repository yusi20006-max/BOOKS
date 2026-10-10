"""Catalog action regressions for issue #341.

«مجموعه و ویرایش‌ها» must be actionable: create a series, attach a volume to
an edition, record a translation grouped by language in the view, and compare
an edition pair — with Persian errors for invalid input and a clean render on
an empty database.
"""

from __future__ import annotations

import sqlite3

EDITION_LABEL = "شازده کوچولو — انتشارات نمونه (1400)"
FIRST_EDITION_LABEL = "کتاب آزمون — بدون ناشر (—)"
SECOND_EDITION_LABEL = "کتاب دوم — بدون ناشر (—)"


def _markdown(session) -> list[str]:
    return [block.value for block in session.at.markdown]


def test_catalog_page_renders_with_empty_database(app_session):
    session = app_session
    session.open("مجموعه و ویرایش‌ها")

    assert not session.at.exception, session.at.exception
    assert any("هنوز مجموعه‌ای ثبت نشده است" in m for m in session.info_messages())
    assert any("ثبت مجموعه" in (b.label or "") for b in session.at.button)
    assert not any("جلدهای ثبت‌شده" in m for m in _markdown(session))


def test_series_volume_translation_lifecycle(app_session):
    session = app_session
    session.open("مجموعه و ویرایش‌ها")

    # AC1: create a series — success message, listing, and a DB row.
    session.set_field("نام مجموعه", "هری پاتر")
    session.set_field("توضیح مجموعه", "مجموعه جادو")
    session.click("ثبت مجموعه")
    assert not session.at.exception, session.at.exception
    assert any("هری پاتر" in m for m in session.success_messages())
    assert any("هری پاتر" in m for m in _markdown(session))
    with session.repository.db.connect() as conn:
        row = conn.execute("SELECT name, description FROM series").fetchone()
    assert row is not None
    assert row["name"] == "هری پاتر"
    assert row["description"] == "مجموعه جادو"

    # One edition to attach series artefacts to.
    session.set_field("عنوان اثر", "شازده کوچولو")
    session.set_field("ناشر", "انتشارات نمونه")
    session.set_field("سال انتشار", 1400)
    session.click("ثبت اثر و ویرایش")
    assert not session.at.exception, session.at.exception
    with session.repository.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0] == 1

    # AC2: attach a volume and see its number and title on the page.
    session.set_field("مجموعه", "هری پاتر")
    session.set_field("ویرایش", EDITION_LABEL)
    session.set_field("شماره جلد", 1)
    session.set_field("عنوان جلد", "جلد اول")
    session.click("افزودن جلد به مجموعه")
    assert not session.at.exception, session.at.exception
    with session.repository.db.connect() as conn:
        volume = conn.execute(
            "SELECT volume_number, title FROM series_volumes"
        ).fetchone()
    assert volume is not None
    assert volume["volume_number"] == 1
    assert volume["title"] == "جلد اول"
    assert any("جلد 1" in m and "جلد اول" in m for m in _markdown(session))

    # AC3: a translation for the edition, grouped by language in the view.
    session.set_field("ویرایش برای ترجمه", EDITION_LABEL)
    session.set_field("زبان", "fa")
    session.set_field("مترجمان (با ویرگول)", "tr-1")
    session.click("ثبت ترجمه")
    assert not session.at.exception, session.at.exception
    with session.repository.db.connect() as conn:
        translation = conn.execute("SELECT language FROM translations").fetchone()
    assert translation is not None
    assert translation["language"] == "fa"
    session.set_field("ترجمه‌های ویرایش", EDITION_LABEL)
    assert any("زبان: fa" in m for m in _markdown(session))
    assert any("مترجمان: tr-1" in m for m in _markdown(session))


def test_invalid_input_shows_persian_errors(app_session):
    session = app_session
    session.open("مجموعه و ویرایش‌ها")

    # Missing series name.
    session.click("ثبت مجموعه")
    assert not session.at.exception, session.at.exception
    assert any("نام مجموعه الزامی است" in e for e in session.error_messages())

    # Duplicate volume number: the same series, a second edition, same number.
    session.set_field("نام مجموعه", "مجموعه آزمون")
    session.click("ثبت مجموعه")
    session.set_field("عنوان اثر", "کتاب آزمون")
    session.click("ثبت اثر و ویرایش")
    session.click("افزودن جلد به مجموعه")  # (series, edition 1, number 1) succeeds
    session.set_field("عنوان اثر", "کتاب دوم")
    session.click("ثبت اثر و ویرایش")
    session.set_field("ویرایش", SECOND_EDITION_LABEL)
    session.click("افزودن جلد به مجموعه")  # number 1 already taken on this series
    assert not session.at.exception, session.at.exception
    assert any("شماره جلد" in e for e in session.error_messages())

    # The same edition cannot join the same series twice (the other UNIQUE path).
    session.set_field("ویرایش", FIRST_EDITION_LABEL)
    session.set_field("شماره جلد", 2)
    session.click("افزودن جلد به مجموعه")
    assert not session.at.exception, session.at.exception
    assert any("این ویرایش قبلاً" in e for e in session.error_messages())
    with session.repository.db.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM series_volumes").fetchone()[0]
    assert count == 1  # both failed attempts stored nothing


def test_catalog_error_mapper_translates_store_failures():
    from books.app import _catalog_error

    assert _catalog_error(ValueError("edition not found")) == "ویرایش موردنظر یافت نشد."
    assert _catalog_error(ValueError("work not found")) == "اثر موردنظر یافت نشد."
    assert (
        _catalog_error(ValueError("series name is required"))
        == "نام مجموعه الزامی است."
    )
    assert _catalog_error(ValueError("something new")) == "ورودی نامعتبر است."
    assert (
        _catalog_error(
            sqlite3.IntegrityError(
                "UNIQUE constraint failed: series_volumes.series_id, "
                "series_volumes.volume_number"
            )
        )
        == "شماره جلد برای این مجموعه قبلاً ثبت شده است."
    )
    assert (
        _catalog_error(
            sqlite3.IntegrityError(
                "UNIQUE constraint failed: series_volumes.series_id, "
                "series_volumes.edition_id"
            )
        )
        == "این ویرایش قبلاً به این مجموعه اضافه شده است."
    )


def test_compare_pair_shows_match_info(app_session):
    session = app_session
    session.open("مجموعه و ویرایش‌ها")

    session.set_field("عنوان اثر", "کتاب اول")
    session.set_field("ناشر", "انتشارات نمونه")
    session.set_field("سال انتشار", 1400)
    session.click("ثبت اثر و ویرایش")
    session.set_field("عنوان اثر", "کتاب دوم")
    session.set_field("ناشر", "انتشارات نمونه")
    session.set_field("سال انتشار", 1401)
    session.click("ثبت اثر و ویرایش")
    assert not session.at.exception, session.at.exception

    session.click("مقایسه ویرایش‌ها")
    assert not session.at.exception, session.at.exception
    assert any("امتیاز تطابق" in m for m in _markdown(session))
    assert any(
        "تکراری" in m
        for m in session.info_messages() + session.warning_messages()
    )

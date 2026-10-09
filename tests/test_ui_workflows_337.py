"""Behavioural Streamlit UI tests (issue #337).

Every user-visible workflow is driven through the rendered app with
``AppTest`` against a temporary database: tests assert what the user
sees (success/error/info messages) and the resulting SQLite state.
Nothing performs network I/O — provider calls are only reachable via
explicit search clicks that these tests never trigger (the AI action is
stubbed to a failure on purpose to cover the error path).
"""

from __future__ import annotations

import pytest

from books.app import PAGES

BOOK_ONE = {
    "title": "شازده کوچولو",
    "authors": ("آنتوان دو سنت‌اگزوپری",),
    "pages": 96,
    "publisher": "نگاه",
}
BOOK_TWO = {
    "title": "دنیای سوفی",
    "authors": ("یوستین گردر",),
    "pages": 320,
    "publisher": "نگاه",
}


# --- render smoke: every page, empty and seeded library ----------------------


@pytest.mark.parametrize("seed", [False, True], ids=["empty-db", "with-book"])
@pytest.mark.parametrize("page", list(PAGES))
def test_every_page_renders_without_exception(app_session, page, seed):
    if seed:
        app_session.seed_book(**BOOK_ONE)
    app_session.open(page)


# --- library ----------------------------------------------------------------


def test_library_search_narrows_results(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.seed_book(**BOOK_TWO)
    session.open("کتابخانه")
    assert "2 کتاب" in [block.value for block in session.at.subheader]
    session.set_field("جستجو در کتابخانه", "شازده")
    assert "1 کتاب" in [block.value for block in session.at.subheader]


# --- edit / delete -----------------------------------------------------------


def test_edit_book_updates_title_in_database(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("ویرایش کتاب")
    session.set_field("عنوان", "شازده کوچولو — ویرایش جدید")
    session.click("ذخیره ویرایش")
    assert "ویرایش کتاب با موفقیت ذخیره شد." in session.success_messages()
    rows = session.repository.list(limit=10)
    assert [row["title"] for row in rows] == ["شازده کوچولو — ویرایش جدید"]


def test_delete_book_removes_row_after_confirmation(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("حذف کتاب")
    session.set_field("تأیید می‌کنم این کتاب را حذف کنم.", True)
    session.click("حذف قطعی کتاب")
    assert "کتاب حذف شد." in session.success_messages()
    assert session.repository.list(limit=10) == []


# --- organization ------------------------------------------------------------


def test_tags_and_shelves_persist(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("برچسب و قفسه")
    session.set_field("برچسب‌ها — هر برچسب در یک خط", "ادبیات\nفارسی")
    session.set_field("قفسه‌ها — هر قفسه در یک خط", "علاقه‌مندی‌ها")
    session.click("ذخیره برچسب و قفسه")
    assert "برچسب‌ها و قفسه‌ها ذخیره شدند." in session.success_messages()
    book_id = session.repository.list(limit=10)[0]["id"]
    tags, shelves = session.repository.get_organization(book_id)
    assert tags == ("ادبیات", "فارسی")
    assert shelves == ("علاقه‌مندی‌ها",)


# --- reading status and progress ---------------------------------------------


def test_reading_status_start_and_progress_flow(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("مطالعه")
    session.set_field("وضعیت مطالعه", "reading")
    session.click("ذخیره وضعیت")
    assert "وضعیت مطالعه ذخیره شد." in session.success_messages()
    book_id = session.repository.list(limit=10)[0]["id"]
    assert session.repository.get(book_id)["reading_status"] == "reading"

    session.click("شروع مطالعه")
    assert any(
        message.startswith("شروع مطالعه ثبت شد") for message in session.success_messages()
    )

    session.set_field("صفحه فعلی از 96", 48)
    session.click("ذخیره پیشرفت")
    assert any(
        "پیشرفت به 50" in message for message in session.success_messages()
    )
    assert session.repository.get(book_id)["reading_progress"] == 50


# --- personal notes ----------------------------------------------------------


def test_personal_note_and_favorite_persist(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("یادداشت‌ها")
    session.set_field("⭐ مورد علاقه", True)
    session.set_field("یادداشت شخصی", "یادداشت آزمون")
    session.click("ذخیره اطلاعات شخصی")
    assert "امتیاز و اطلاعات شخصی ذخیره شد." in session.success_messages()
    book_id = session.repository.list(limit=10)[0]["id"]
    personal = session.repository.get_personal_data(book_id)
    assert personal is not None
    assert personal["note"] == "یادداشت آزمون"
    assert personal["favorite"] == 1


# --- knowledge ---------------------------------------------------------------


def test_knowledge_concept_is_registered_and_searchable(app_session):
    session = app_session
    session.open("دانش شخصی")
    session.set_field("مفهوم", "فلسفه وجود")
    session.click("ثبت مفهوم")
    assert "مفهوم ثبت شد." in session.success_messages()

    from books.db import Database
    from books.knowledge_store import KnowledgeStore

    nodes = KnowledgeStore(Database(session.db_path)).nodes()
    assert [node.label for node in nodes] == ["فلسفه وجود"]

    session.set_field(
        "جستجوی یکپارچه در یادداشت‌ها، نقل‌قول‌ها و مفاهیم",
        "فلسفه",
    )
    # The page rerenders with the unified search executed; the registered
    # concept stays visible in the footer listing.
    assert any("فلسفه وجود" in (block.value or "") for block in session.at.markdown)


# --- sessions ----------------------------------------------------------------


def test_reading_session_is_recorded(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("جلسات مطالعه")
    session.set_field("دقیقه", 45)
    session.set_field("صفحات", 12)
    session.set_field("یادداشت جلسه", "یادداشت جلسه آزمون")
    session.click("ثبت جلسه")
    assert "جلسه مطالعه در SQLite ثبت شد." in session.success_messages()
    book_id = session.repository.list(limit=10)[0]["id"]
    sessions = session.repository.list_reading_sessions(book_id)
    assert len(sessions) == 1
    assert sessions[0]["minutes"] == 45
    assert sessions[0]["pages"] == 12


# --- journal / goals ---------------------------------------------------------


def test_reading_goal_is_registered(app_session):
    session = app_session
    session.open("اهداف و تقویم مطالعه")
    session.set_field("هدف تعداد کتاب", 2)
    session.set_field("هدف تعداد صفحه", 200)
    session.click("ثبت هدف")
    assert "هدف مطالعه ثبت شد." in session.success_messages()

    from books.db import Database
    from books.reading_journal_store import ReadingJournalStore

    goals = ReadingJournalStore(Database(session.db_path)).goals()
    assert len(goals) == 1
    assert goals[0].target_books == 2
    assert goals[0].target_pages == 200


# --- audiobooks --------------------------------------------------------------


def test_audiobook_registration_persists(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("کتاب‌های صوتی")
    session.set_field("مسیر فایل صوتی", "/tmp/books-sample.mp3")
    session.set_field("مدت (ثانیه)", 120)
    session.click("ثبت کتاب صوتی")
    assert "فایل صوتی ثبت شد." in session.success_messages()
    book_id = session.repository.list(limit=10)[0]["id"]
    audiobooks = session.repository.list_audiobooks(book_id)
    assert len(audiobooks) == 1
    assert audiobooks[0]["duration_seconds"] == 120


# --- digital annotations -----------------------------------------------------


def test_digital_annotation_is_saved(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("حاشیه‌نویسی دیجیتال")
    session.set_field("مکان در فایل", "صفحه ۱۲")
    session.set_field("متن انتخاب‌شده", "متن نمونه")
    session.click("ذخیره")
    assert "حاشیه‌نویسی ذخیره شد." in session.success_messages()
    book_id = session.repository.list(limit=10)[0]["id"]
    annotations = session.repository.list_annotations(book_id)
    assert len(annotations) == 1
    assert annotations[0]["kind"] == "bookmark"


# --- transfer / backup / reports / statistics --------------------------------


def test_transfer_page_offers_export_buttons(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("انتقال داده")
    labels = [button.label for button in session.at.download_button]
    assert "دریافت JSON" in labels
    assert "دریافت CSV" in labels


def test_backup_is_created_from_the_ui(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("پشتیبان‌گیری")
    session.click("ساخت Backup")
    assert "Backup با integrity check موفق ساخته شد." in session.success_messages()


def test_reports_page_renders_export_buttons(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("گزارش‌ها")
    labels = [button.label for button in session.at.download_button]
    assert "JSON گزارش" in labels
    assert "CSV کتاب‌ها" in labels


def test_statistics_page_shows_book_count(app_session):
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("آمار مطالعه")
    labels = [metric.label for metric in session.at.metric]
    assert "تعداد کتاب" in labels


# --- AI assistant error path -------------------------------------------------


def test_ai_assistant_failure_shows_persian_error(app_session, monkeypatch):
    from books import ai_service

    def failing_action(self, action, title, context=""):
        raise RuntimeError("آزمون قطع ارتباط")

    monkeypatch.setattr(ai_service.BookAIService, "action", failing_action)
    session = app_session
    session.seed_book(**BOOK_ONE)
    session.open("دستیار هوشمند")
    session.click("اجرا")
    assert any(
        "اتصال به درگاه هوش مصنوعی ناموفق بود" in message
        for message in session.error_messages()
    )

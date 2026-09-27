from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import streamlit as st
from PIL import Image

from .backup import BackupService
from .config import load_settings
from .db import BookRepository, Database
from .discovery import DiscoveryService, MergedDiscoveryItem
from .enrichment import MetadataEnricher
from .models import Book
from .providers.google_books import GoogleBooksProvider
from .providers.open_library import OpenLibraryProvider
from .scanner import BarcodeScanner
from .transfer import BookTransferService

PAGES = {
    "کتابخانه": "نمایش و مدیریت کتاب‌های ذخیره‌شده",
    "افزودن کتاب": "جستجو و انتخاب کتاب از منابع مختلف",
    "تأیید و ویرایش": "اصلاح و اعتبارسنجی اطلاعات قبل از ذخیره",
    "ویرایش کتاب": "ویرایش کتاب‌های ذخیره‌شده",
    "حذف کتاب": "حذف امن کتاب و بررسی Duplicate",
    "برچسب و قفسه": "علاقه‌مندی، برچسب و قفسه‌های شخصی",
    "انتقال داده": "Import و Export امن کتابخانه",
    "پشتیبان‌گیری": "Backup و Restore امن SQLite",
    "آمار مطالعه": "داشبورد آمار کتابخانه و مطالعه",
    "مطالعه": "پیگیری وضعیت و پیشرفت مطالعه",
    "یادداشت‌ها": "یادداشت‌ها و نقل‌قول‌های شخصی",
    "دانش شخصی": "نقل‌قول، هایلایت، یادداشت و گراف دانش",
    "جلسات مطالعه": "ثبت جلسات مطالعه در SQLite",
    "کتاب‌های صوتی": "پخش و ثبت پیشرفت کتاب صوتی",
    "حاشیه‌نویسی دیجیتال": "نشانک، هایلایت و یادداشت در کتاب دیجیتال",
    "قرض‌ها": "مدیریت نسخه‌های فیزیکی و امانت",
    "اهداف و تقویم مطالعه": "هدف، جلسه، زنجیره و تقویم مطالعه",
    "مجموعه و ویرایش‌ها": "مجموعه‌ها، جلدها، ویرایش‌ها و ترجمه‌ها",
    "اسکن و OCR": "اسکن متن و اصلاح قبل از ذخیره",
    "گزارش‌ها": "گزارش موجودی و مطالعه",
    "دستیار هوشمند": "خلاصه، پرسش، پیشنهاد و برنامه مطالعه با AI",
    "جستجوی معنایی": "نمایه‌سازی، جستجوی معنایی و پیشنهاد مشابه",
    "تنظیمات": "تنظیمات برنامه و داده‌ها",
}


def configure_page() -> None:
    st.set_page_config(
        page_title="کتابخانه من | BOOKS",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        :root { color-scheme: light dark; }
        .stApp, .stApp [data-testid="stSidebar"] { direction: rtl; }
        .stApp [data-testid="stSidebar"] * { text-align: right; }
        .stApp input, .stApp textarea, .stApp [data-baseweb="select"] { direction: rtl; }
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 { line-height: 1.9; }
        .block-container { max-width: 1200px; padding: 2rem 1rem 4rem; }
        @media (max-width: 768px) {
            .block-container { padding: 1rem .75rem 3rem; }
            [data-testid="stSidebar"] { min-width: 15rem; max-width: 18rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> str:
    st.sidebar.title("📚 BOOKS")
    st.sidebar.caption("کتابخانه شخصی فارسی‌محور")
    return st.sidebar.radio(
        "بخش",
        list(PAGES),
        format_func=lambda page: page,
        label_visibility="collapsed",
    )


def candidate_summary(candidate: MergedDiscoveryItem) -> dict[str, str]:
    book = candidate.book
    return {
        "عنوان": book.title,
        "نویسنده": "، ".join(book.authors) or "—",
        "مترجم": "، ".join(book.translators) or "—",
        "ناشر": book.publisher or "—",
        "سال": str(book.publication_year) if book.publication_year else "—",
        "ISBN": book.isbn13 or book.isbn10 or "—",
        "منبع": "، ".join(p.provider for p in candidate.provenance) or "—",
        "اطمینان": f"{candidate.confidence:.0%}",
    }


def render_candidate(candidate: MergedDiscoveryItem, index: int) -> None:
    book = candidate.book
    left, right = st.columns([1, 3], gap="medium")
    with left:
        if book.cover_url:
            st.image(book.cover_url, use_container_width=True)
        else:
            st.caption("جلد موجود نیست")
    with right:
        st.subheader(book.title)
        st.write(f"**نویسنده:** {'، '.join(book.authors) or '—'}")
        st.write(f"**مترجم:** {'، '.join(book.translators) or '—'}")
        st.write(f"**ناشر:** {book.publisher or '—'}")
        st.write(
            f"**سال:** {book.publication_year or '—'}  ·  "
            f"**ISBN:** {book.isbn13 or book.isbn10 or '—'}"
        )
        sources = "، ".join(p.provider for p in candidate.provenance) or "—"
        st.caption(f"منبع: {sources} | اطمینان تطبیق: {candidate.confidence:.0%}")
        if st.button("انتخاب این کتاب", key=f"select-candidate-{index}", type="primary"):
            st.session_state["selected_candidate"] = candidate
            st.success("این نتیجه انتخاب شد؛ مرحله تأیید و ویرایش در Issue بعدی انجام می‌شود.")




def _split_lines(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.splitlines() if item.strip())


def build_edited_book(
    *,
    title: str,
    original_title: str,
    authors: str,
    translators: str,
    publisher: str,
    pages: int | None,
    publication_year: int | None,
    isbn10: str,
    isbn13: str,
    language: str,
    genres: str,
    subjects: str,
    summary: str,
    cover_url: str,
    source_ids: dict[str, str],
):
    from .models import Book

    return Book(
        title=title,
        original_title=original_title or None,
        authors=_split_lines(authors),
        translators=_split_lines(translators),
        publisher=publisher or None,
        pages=pages,
        publication_year=publication_year,
        isbn10=isbn10 or None,
        isbn13=isbn13 or None,
        language=language or None,
        genres=_split_lines(genres),
        subjects=_split_lines(subjects),
        summary=summary or None,
        cover_url=cover_url or None,
        source_ids=source_ids,
    )


def render_confirm_edit() -> None:
    candidate = st.session_state.get("selected_candidate")
    if candidate is None:
        st.info("ابتدا یک نتیجه را از جستجوی کتاب انتخاب کنید.")
        return

    book = candidate.book
    st.subheader("تأیید و ویرایش اطلاعات")
    st.caption("اطلاعات منبع قابل اصلاح است. ذخیره نهایی در مرحله بعد انجام می‌شود.")

    with st.form("confirm-edit-book"):
        title = st.text_input("عنوان", value=book.title)
        original_title = st.text_input("عنوان اصلی", value=book.original_title or "")
        authors = st.text_area("نویسندگان — هر نفر در یک خط", value="\n".join(book.authors))
        translators = st.text_area("مترجمان — هر نفر در یک خط", value="\n".join(book.translators))
        publisher = st.text_input("ناشر", value=book.publisher or "")

        col1, col2 = st.columns(2)
        with col1:
            pages = st.number_input(
                "تعداد صفحات",
                min_value=0,
                value=book.pages or 0,
                step=1,
            )
        with col2:
            publication_year = st.number_input(
                "سال انتشار",
                min_value=1,
                max_value=9999,
                value=book.publication_year or 1400,
                step=1,
            )

        isbn10 = st.text_input("ISBN-10", value=book.isbn10 or "")
        isbn13 = st.text_input("ISBN-13", value=book.isbn13 or "")
        language = st.text_input("زبان", value=book.language or "")
        genres = st.text_area("ژانرها — هر مورد در یک خط", value="\n".join(book.genres))
        subjects = st.text_area("موضوعات — هر مورد در یک خط", value="\n".join(book.subjects))
        summary = st.text_area("خلاصه", value=book.summary or "")
        cover_url = st.text_input("نشانی جلد", value=book.cover_url or "")

        submitted = st.form_submit_button("اعتبارسنجی و پیش‌نمایش", type="primary")

    if not submitted:
        return

    try:
        edited = build_edited_book(
            title=title,
            original_title=original_title,
            authors=authors,
            translators=translators,
            publisher=publisher,
            pages=int(pages),
            publication_year=int(publication_year),
            isbn10=isbn10,
            isbn13=isbn13,
            language=language,
            genres=genres,
            subjects=subjects,
            summary=summary,
            cover_url=cover_url,
            source_ids=dict(book.source_ids),
        )
    except (TypeError, ValueError) as exc:
        st.error(f"اطلاعات واردشده معتبر نیست: {exc}")
        return

    st.session_state["edited_candidate"] = edited
    st.success("اطلاعات معتبر است و پیش‌نمایش آماده شد.")
    _render_save_action(edited)
    with st.container(border=True):
        st.subheader(edited.title)
        st.write(f"**نویسنده:** {'، '.join(edited.authors) or '—'}")
        st.write(f"**مترجم:** {'، '.join(edited.translators) or '—'}")
        st.write(f"**ناشر:** {edited.publisher or '—'}")
        st.write(f"**ISBN:** {edited.isbn13 or edited.isbn10 or '—'}")
        st.write(f"**صفحات:** {edited.pages or '—'}")
        st.write(f"**سال انتشار:** {edited.publication_year or '—'}")
        st.write(f"**زبان:** {edited.language or '—'}")
        st.write(f"**ژانر:** {'، '.join(edited.genres) or '—'}")
        st.write(f"**موضوع:** {'، '.join(edited.subjects) or '—'}")
        st.write(f"**خلاصه:** {edited.summary or '—'}")


def row_to_book(row) -> Book:
    return Book(
        title=row["title"],
        original_title=row["original_title"],
        authors=tuple(json.loads(row["authors_json"] or "[]")),
        translators=tuple(json.loads(row["translators_json"] or "[]")),
        publisher=row["publisher"],
        pages=row["pages"],
        publication_year=row["publication_year"],
        isbn10=row["isbn10"],
        isbn13=row["isbn13"],
        language=row["language"],
        genres=tuple(json.loads(row["genres_json"] or "[]")),
        subjects=tuple(json.loads(row["subjects_json"] or "[]")),
        summary=row["summary"],
        cover_url=row["cover_url"],
        source_ids=json.loads(row["source_ids_json"] or "{}"),
        notes=row["notes"],
    )


def render_edit_book() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("کتابی برای ویرایش وجود ندارد.")
        return

    labels = {row["id"]: row["title"] for row in rows}
    selected_id = st.selectbox(
        "کتاب",
        list(labels),
        format_func=lambda book_id: labels[book_id],
    )
    row = repository.get(selected_id)
    if row is None:
        st.error("رکورد انتخاب‌شده پیدا نشد.")
        return

    book = row_to_book(row)

    refresh = st.button("تکمیل metadata از منابع", key="refresh-metadata")
    if refresh:
        settings = load_settings()
        enricher = MetadataEnricher(
            repository,
            [
                ("google_books", GoogleBooksProvider(settings)),
                ("open_library", OpenLibraryProvider(settings)),
            ],
        )
        with st.spinner("در حال تکمیل اطلاعات..."):
            enriched = enricher.enrich(book, language="fa", force_refresh=True)
        try:
            repository.update_book(selected_id, enriched)
        except sqlite3.IntegrityError:
            st.error("تکمیل metadata باعث ایجاد Duplicate شد و ذخیره نشد.")
        else:
            book = enriched
            st.success("metadata با fallback و refresh به‌روزرسانی شد.")

    with st.form("edit-library-book"):
        title = st.text_input("عنوان", value=book.title)
        original_title = st.text_input("عنوان اصلی", value=book.original_title or "")
        authors = st.text_area("نویسندگان — هر نفر در یک خط", value="\n".join(book.authors))
        translators = st.text_area("مترجمان — هر نفر در یک خط", value="\n".join(book.translators))
        publisher = st.text_input("ناشر", value=book.publisher or "")
        pages = st.number_input("تعداد صفحات", min_value=0, value=book.pages or 0, step=1)
        publication_year = st.number_input(
            "سال انتشار", min_value=1, max_value=9999,
            value=book.publication_year or 1400, step=1,
        )
        isbn10 = st.text_input("ISBN-10", value=book.isbn10 or "")
        isbn13 = st.text_input("ISBN-13", value=book.isbn13 or "")
        language = st.text_input("زبان", value=book.language or "")
        genres = st.text_area("ژانرها — هر مورد در یک خط", value="\n".join(book.genres))
        subjects = st.text_area("موضوعات — هر مورد در یک خط", value="\n".join(book.subjects))
        summary = st.text_area("خلاصه", value=book.summary or "")
        cover_url = st.text_input("نشانی جلد", value=book.cover_url or "")
        notes = st.text_area("یادداشت", value=book.notes or "")
        submitted = st.form_submit_button("ذخیره ویرایش", type="primary")

    if not submitted:
        return

    try:
        edited = build_edited_book(
            title=title,
            original_title=original_title,
            authors=authors,
            translators=translators,
            publisher=publisher,
            pages=int(pages),
            publication_year=int(publication_year),
            isbn10=isbn10,
            isbn13=isbn13,
            language=language,
            genres=genres,
            subjects=subjects,
            summary=summary,
            cover_url=cover_url,
            source_ids=dict(book.source_ids),
        )
        edited = Book(
            title=edited.title,
            original_title=edited.original_title,
            authors=edited.authors,
            translators=edited.translators,
            publisher=edited.publisher,
            pages=edited.pages,
            publication_year=edited.publication_year,
            isbn10=edited.isbn10,
            isbn13=edited.isbn13,
            language=edited.language,
            genres=edited.genres,
            subjects=edited.subjects,
            summary=edited.summary,
            cover_url=edited.cover_url,
            source_ids=edited.source_ids,
            notes=notes or None,
        )
    except (TypeError, ValueError) as exc:
        st.error(f"اطلاعات واردشده معتبر نیست: {exc}")
        return

    for isbn in (edited.isbn13, edited.isbn10):
        if isbn:
            existing = repository.get_by_isbn(isbn)
            if existing is not None and existing["id"] != selected_id:
                st.error("این ISBN متعلق به کتاب دیگری است و ویرایش انجام نشد.")
                return

    try:
        if repository.update_book(selected_id, edited):
            st.success("ویرایش کتاب با موفقیت ذخیره شد.")
        else:
            st.error("کتاب انتخاب‌شده دیگر وجود ندارد.")
    except sqlite3.IntegrityError:
        st.error("ویرایش باعث ایجاد Duplicate می‌شود و ذخیره نشد.")

def render_personal_data() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("کتابی برای یادداشت وجود ندارد.")
        return

    labels = {row["id"]: row["title"] for row in rows}
    selected_id = st.selectbox(
        "کتاب",
        list(labels),
        format_func=lambda book_id: labels[book_id],
    )
    personal = repository.get_personal_data(selected_id)
    current_rating = personal["rating"] if personal else None
    current_note = personal["note"] if personal else ""
    current_quote = personal["quote"] if personal else ""
    current_favorite = bool(personal["favorite"]) if personal else False

    favorite = st.checkbox("⭐ مورد علاقه", value=current_favorite)

    rating_options = [None, 1, 2, 3, 4, 5]
    rating = st.selectbox(
        "امتیاز شخصی",
        rating_options,
        index=rating_options.index(current_rating),
        format_func=lambda value: "بدون امتیاز" if value is None else f"{value} از ۵",
    )
    note = st.text_area("یادداشت شخصی", value=current_note or "", height=180)
    quote = st.text_area("نقل‌قول شخصی", value=current_quote or "", height=140)

    if st.button("ذخیره اطلاعات شخصی", type="primary"):
        try:
            repository.update_personal_data(
                selected_id,
                rating=rating,
                note=note,
                quote=quote,
            )
            repository.update_favorite(selected_id, favorite)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("امتیاز و اطلاعات شخصی ذخیره شد.")



def render_organization() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("کتابی برای سازمان‌دهی وجود ندارد.")
        return

    labels = {row["id"]: row["title"] for row in rows}
    selected_id = st.selectbox(
        "کتاب",
        list(labels),
        format_func=lambda book_id: labels[book_id],
    )
    current_tags, current_shelves = repository.get_organization(selected_id)
    tags = st.text_area(
        "برچسب‌ها — هر برچسب در یک خط",
        value="\n".join(current_tags),
    )
    shelves = st.text_area(
        "قفسه‌ها — هر قفسه در یک خط",
        value="\n".join(current_shelves),
    )

    if st.button("ذخیره برچسب و قفسه", type="primary"):
        repository.set_organization(
            selected_id,
            tags=tuple(tags.splitlines()),
            shelves=tuple(shelves.splitlines()),
        )
        st.success("برچسب‌ها و قفسه‌ها ذخیره شدند.")



def render_statistics() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    stats = repository.reading_statistics()

    st.subheader("نمای کلی")
    cols = st.columns(4)
    cols[0].metric("تعداد کتاب", stats["book_count"])
    cols[1].metric("تعداد نویسنده", stats["authors_count"])
    cols[2].metric("کل صفحات", stats["total_pages"])
    cols[3].metric("صفحات خوانده‌شده", stats["current_pages"])

    status_labels = {
        "unread": "نخوانده",
        "reading": "در حال مطالعه",
        "finished": "تمام‌شده",
        "abandoned": "رهاشده",
    }
    st.subheader("وضعیت مطالعه")
    for status, count in stats["status_counts"].items():
        st.write(f"**{status_labels.get(status, status)}:** {count}")

    st.subheader("روند میانگین پیشرفت")
    if stats["progress_trend"]:
        st.bar_chart(stats["progress_trend"])
    else:
        st.info("هنوز داده‌ای برای روند پیشرفت وجود ندارد.")



def render_backup() -> None:
    settings = load_settings()
    backup = BackupService(settings.db_path)

    st.subheader("Backup")
    if st.button("ساخت Backup", type="primary"):
        try:
            data = backup.create_backup_bytes()
        except (FileNotFoundError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.download_button(
                "دریافت فایل Backup",
                data=data,
                file_name=backup.backup_filename(),
                mime="application/x-sqlite3",
            )
            st.success("Backup با integrity check موفق ساخته شد.")

    st.subheader("Restore")
    uploaded = st.file_uploader(
        "فایل SQLite Backup را انتخاب کنید",
        type=("sqlite3", "db"),
        accept_multiple_files=False,
    )
    overwrite = st.checkbox(
        "تأیید می‌کنم Database فعلی با Backup جایگزین شود.",
        value=False,
    )
    if uploaded is not None and st.button(
        "Restore",
        type="primary",
        disabled=not overwrite,
    ):
        try:
            backup.restore_bytes(uploaded.getvalue(), overwrite=True)
        except (ValueError, OSError) as exc:
            st.error(f"Restore ناموفق بود: {exc}")
        else:
            st.success("Restore با موفقیت انجام شد. برای بارگذاری دوباره داده‌ها برنامه را Refresh کنید.")



def render_transfer() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    transfer = BookTransferService(repository)

    st.subheader("Export")
    st.download_button(
        "دریافت JSON",
        data=transfer.export_json(),
        file_name="books-export.json",
        mime="application/json",
    )
    st.download_button(
        "دریافت CSV",
        data=transfer.export_csv(),
        file_name="books-export.csv",
        mime="text/csv",
    )

    st.subheader("Import")
    uploaded = st.file_uploader(
        "فایل JSON یا CSV را انتخاب کنید",
        type=("json", "csv"),
        accept_multiple_files=False,
    )
    if uploaded is not None and st.button("Import در حالت Merge", type="primary"):
        try:
            payload = uploaded.getvalue()
            if uploaded.name.lower().endswith(".json"):
                count = transfer.import_json(payload.decode("utf-8-sig"))
            else:
                count = transfer.import_csv(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            st.error(f"Import ناموفق بود: {exc}")
        else:
            st.success(f"{count} کتاب جدید وارد شد؛ رکوردهای موجود overwrite نشدند.")



def render_reading_status() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("کتابی برای تغییر وضعیت مطالعه وجود ندارد.")
        return

    labels = {row["id"]: row["title"] for row in rows}
    selected_id = st.selectbox(
        "کتاب",
        list(labels),
        format_func=lambda book_id: labels[book_id],
    )
    row = repository.get(selected_id)
    if row is None:
        st.error("رکورد انتخاب‌شده پیدا نشد.")
        return

    current = row["reading_status"] or "unread"
    status_options = list(repository.READING_STATUSES)
    status = st.selectbox(
        "وضعیت مطالعه",
        status_options,
        index=status_options.index(current),
        format_func=repository.READING_STATUSES.get,
    )
    st.caption(f"وضعیت فعلی: {repository.READING_STATUSES.get(current, current)}")

    if st.button("ذخیره وضعیت", type="primary", key="save-reading-status"):
        if repository.update_reading_status(selected_id, status):
            st.success("وضعیت مطالعه ذخیره شد.")
        else:
            st.error("کتاب پیدا نشد.")

    if row["reading_started_at"]:
        st.caption(f"شروع مطالعه: {row['reading_started_at']}")
        if row["reading_finished_at"]:
            st.caption(f"پایان مطالعه: {row['reading_finished_at']}")
        elif st.button("ثبت پایان مطالعه", type="primary", key="finish-reading"):
            try:
                timestamp = repository.finish_reading(selected_id)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"پایان مطالعه ثبت شد: {timestamp}")
    elif st.button("شروع مطالعه", type="primary", key="start-reading"):
        try:
            timestamp = repository.start_reading(selected_id)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"شروع مطالعه ثبت شد: {timestamp}")

    total_pages = row["pages"]
    if total_pages:
        current_page = st.number_input(
            f"صفحه فعلی از {total_pages}",
            min_value=0,
            max_value=total_pages,
            value=row["reading_current_page"] or 0,
            step=1,
        )
        st.progress(
            (row["reading_progress"] or 0) / 100,
            text=f"پیشرفت: {row['reading_progress'] or 0}٪",
        )
        if st.button("ذخیره پیشرفت", type="primary", key="save-reading-progress"):
            try:
                progress = repository.update_reading_progress(selected_id, int(current_page))
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"پیشرفت به {progress}٪ رسید.")
    else:
        st.info("برای محاسبه پیشرفت، تعداد صفحات کتاب را در ویرایش کتاب وارد کنید.")



def render_delete_book() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("کتابی برای حذف وجود ندارد.")
        return

    labels = {row["id"]: row["title"] for row in rows}
    selected_id = st.selectbox(
        "کتاب",
        list(labels),
        format_func=lambda book_id: labels[book_id],
    )
    row = repository.get(selected_id)
    if row is None:
        st.error("رکورد انتخاب‌شده پیدا نشد.")
        return

    st.warning("حذف کتاب برگشت‌پذیر نیست.")
    st.write(f"**عنوان:** {row['title']}")
    st.write(f"**ISBN:** {row['isbn13'] or row['isbn10'] or '—'}")
    confirmed = st.checkbox("تأیید می‌کنم این کتاب را حذف کنم.", key="confirm-delete-book")
    if st.button("حذف قطعی کتاب", type="primary", disabled=not confirmed):
        if repository.delete(selected_id):
            st.success("کتاب حذف شد.")
        else:
            st.error("کتاب پیدا نشد یا قبلاً حذف شده است.")

def _render_save_action(book) -> None:
    st.divider()
    st.subheader("افزودن به کتابخانه")
    if st.button("ذخیره کتاب در کتابخانه", type="primary", key="save-confirmed-book"):
        settings = load_settings()
        db = Database(settings.db_path)
        db.migrate()
        repository = BookRepository(db)

        duplicates = repository.find_duplicates(book)
        if duplicates:
            st.warning("کتاب مشابهی در کتابخانه پیدا شد؛ ابتدا نتیجه را بررسی کنید.")
            for duplicate in duplicates:
                st.write(f"• {duplicate['title']} — {duplicate['isbn13'] or duplicate['isbn10'] or 'بدون ISBN'}")
            return

        try:
            book_id = repository.create_book(book)
        except sqlite3.IntegrityError:
            st.warning("رکورد مشابه قبلاً ذخیره شده است و از ایجاد Duplicate جلوگیری شد.")
            return

        st.session_state["saved_book_id"] = book_id
        st.success("کتاب با موفقیت در SQLite ذخیره شد.")

def library_row_summary(row) -> dict[str, str]:
    authors = "، ".join(json.loads(row["authors_json"] or "[]")) or "—"
    return {
        "title": row["title"],
        "authors": authors,
        "publisher": row["publisher"] or "—",
        "year": str(row["publication_year"]) if row["publication_year"] else "—",
        "isbn": row["isbn13"] or row["isbn10"] or "—",
    }


def render_library() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    query = st.text_input(
        "جستجو در کتابخانه",
        placeholder="عنوان، نویسنده، مترجم، ناشر یا ISBN",
    )
    all_rows = repository.list(limit=1000)
    publishers = sorted({row["publisher"] for row in all_rows if row["publisher"]})
    languages = sorted({row["language"] for row in all_rows if row["language"]})
    authors = sorted({
        author
        for row in all_rows
        for author in json.loads(row["authors_json"] or "[]")
        if author
    })
    genres = sorted({
        genre
        for row in all_rows
        for genre in json.loads(row["genres_json"] or "[]")
        if genre
    })
    years = sorted(
        {row["publication_year"] for row in all_rows if row["publication_year"]},
        reverse=True,
    )

    filter_cols = st.columns(4)
    with filter_cols[0]:
        selected_genre = st.selectbox("ژانر", ["همه"] + genres)
    with filter_cols[1]:
        selected_author = st.selectbox("نویسنده", ["همه"] + authors)
    with filter_cols[2]:
        selected_publisher = st.selectbox("ناشر", ["همه"] + publishers)
    with filter_cols[3]:
        selected_language = st.selectbox("زبان", ["همه"] + languages)

    year_options = ["همه"] + [str(year) for year in years]
    selected_year = st.selectbox("سال انتشار", year_options)

    sort_cols = st.columns(2)
    with sort_cols[0]:
        sort_label = st.selectbox(
            "مرتب‌سازی",
            ("آخرین تغییر", "عنوان", "سال انتشار", "ناشر"),
        )
    with sort_cols[1]:
        descending = st.toggle("نزولی", value=True)

    sort_map = {
        "آخرین تغییر": "updated_at",
        "عنوان": "title",
        "سال انتشار": "publication_year",
        "ناشر": "publisher",
    }

    if query.strip():
        try:
            rows = repository.search(query, limit=1000)
        except ValueError:
            rows = []
        if selected_genre != "همه":
            rows = [r for r in rows if selected_genre in json.loads(r["genres_json"] or "[]")]
        if selected_author != "همه":
            rows = [r for r in rows if selected_author in json.loads(r["authors_json"] or "[]")]
        if selected_publisher != "همه":
            rows = [r for r in rows if r["publisher"] == selected_publisher]
        if selected_language != "همه":
            rows = [r for r in rows if r["language"] == selected_language]
        if selected_year != "همه":
            rows = [r for r in rows if str(r["publication_year"]) == selected_year]
        rows.sort(
            key=lambda r: (
                r[sort_map[sort_label]] is None,
                r[sort_map[sort_label]] or "",
            ),
            reverse=descending,
        )
    else:
        rows = repository.filter_books(
            genre=None if selected_genre == "همه" else selected_genre,
            author=None if selected_author == "همه" else selected_author,
            publisher=None if selected_publisher == "همه" else selected_publisher,
            language=None if selected_language == "همه" else selected_language,
            publication_year=None if selected_year == "همه" else int(selected_year),
            sort_by=sort_map[sort_label],
            descending=descending,
            limit=1000,
        )

    if not rows:
        st.info("کتابخانه هنوز خالی است. از بخش «افزودن کتاب» یک کتاب انتخاب و ذخیره کنید.")
        return

    view = st.radio(
        "نحوه نمایش",
        ("شبکه‌ای", "فهرستی"),
        horizontal=True,
        label_visibility="collapsed",
    )
    st.subheader(f"{len(rows)} کتاب")

    if view == "فهرستی":
        for row in rows:
            with st.container(border=True):
                cols = st.columns([1, 5])
                with cols[0]:
                    if row["cover_url"]:
                        st.image(row["cover_url"], use_container_width=True)
                with cols[1]:
                    st.subheader(row["title"])
                    summary = library_row_summary(row)
                    st.write(f"**نویسنده:** {summary['authors']}")
                    st.write(f"**ناشر:** {summary['publisher']}")
                    st.write(
                        f"**سال:** {summary['year']} · "
                        f"**ISBN:** {summary['isbn']}"
                    )
                    st.caption(f"وضعیت مطالعه: {BookRepository.READING_STATUSES.get(row['reading_status'], 'نخوانده')} · پیشرفت: {row['reading_progress'] or 0}٪")
    else:
        columns = st.columns(3)
        for index, row in enumerate(rows):
            with columns[index % 3], st.container(border=True):
                    if row["cover_url"]:
                        st.image(row["cover_url"], use_container_width=True)
                    st.subheader(row["title"])
                    summary = library_row_summary(row)
                    st.write(summary["authors"])
                    st.caption(f"ISBN: {summary['isbn']}")
                    st.caption(f"وضعیت مطالعه: {BookRepository.READING_STATUSES.get(row['reading_status'], 'نخوانده')}")

def render_discovery() -> None:
    settings = load_settings()

    st.subheader("اسکن ISBN")
    camera = st.camera_input("بارکد پشت جلد را روبه‌روی دوربین بگیرید.")
    if camera is not None:
        try:
            image = Image.open(camera)
            result = BarcodeScanner().scan(image)
        except (OSError, ValueError) as exc:
            st.error(f"خواندن تصویر ناموفق بود: {exc}")
        else:
            if result.isbn:
                st.session_state["scanned_isbn"] = result.isbn
                st.success(f"{result.format} شناسایی شد: {result.isbn}")
            else:
                st.warning(result.error or "ISBN معتبر پیدا نشد.")

    scanned_isbn = st.session_state.get("scanned_isbn")
    if scanned_isbn:
        st.info(f"ISBN اسکن‌شده: {scanned_isbn}")
        scan_search = st.button("جستجوی ISBN اسکن‌شده", type="primary")
    else:
        scan_search = False

    query = st.text_input("عنوان، نویسنده یا ISBN", placeholder="مثلاً شازده کوچولو")
    limit = st.slider("تعداد نتایج", min_value=1, max_value=20, value=10)
    search = st.button("جستجوی کتاب", type="primary", disabled=not query.strip())

    if scan_search:
        query = scanned_isbn
        search = True

    if search:
        service = DiscoveryService(
            [
                ("google_books", GoogleBooksProvider(settings)),
                ("open_library", OpenLibraryProvider(settings)),
            ]
        )
        with st.spinner("در حال جستجو در منابع کتاب..."):
            response = service.search_merged(query.strip(), language="fa", limit=limit)
        st.session_state["discovery_candidates"] = response

    candidates = st.session_state.get("discovery_candidates", ())
    if not candidates:
        st.info("برای شروع، عنوان، نام نویسنده یا ISBN را جستجو کنید.")
        return

    st.subheader(f"{len(candidates)} نتیجه")
    for index, candidate in enumerate(candidates):
        with st.container(border=True):
            render_candidate(candidate, index)




def render_annotations() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("ابتدا یک کتاب به کتابخانه اضافه کنید.")
        return
    labels = {row["id"]: row["title"] for row in rows}
    book_id = st.selectbox("کتاب", list(labels), format_func=lambda value: labels[value], key="annotation-book")
    st.subheader("حاشیه‌نویسی دیجیتال")
    with st.form("annotation-form"):
        kind = st.selectbox("نوع", ("bookmark", "highlight", "note"), format_func=lambda x: {"bookmark":"نشانک","highlight":"هایلایت","note":"یادداشت"}[x])
        locator = st.text_input("مکان در فایل", placeholder="صفحه ۱۲ یا فصل ۳")
        text = st.text_area("متن انتخاب‌شده")
        note = st.text_area("یادداشت تکمیلی")
        save = st.form_submit_button("ذخیره", type="primary")
    if save:
        from uuid import uuid4
        try:
            repository.add_annotation(str(uuid4()), book_id, kind, locator, text or None, note or None)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("حاشیه‌نویسی ذخیره شد.")
    annotations = repository.list_annotations(book_id)
    st.dataframe([dict(row) for row in annotations], use_container_width=True)



def render_catalog_editions() -> None:
    settings = load_settings()
    store = __import__("books.catalog_store", fromlist=["CatalogStore"]).CatalogStore(Database(settings.db_path))
    store.db.migrate()
    st.subheader("مجموعه‌ها و ویرایش‌ها")
    series = store.list_series()
    if series:
        for item in series:
            st.write(f"**{item['name']}** — {item['description'] or 'بدون توضیح'}")
    else:
        st.info("هنوز مجموعه‌ای ثبت نشده است.")
    st.caption("ترجمه‌های هر ویرایش مستقل نگهداری می‌شوند و در لایه نمایش بر اساس زبان گروه‌بندی می‌شوند.")



def render_reading_journal() -> None:
    settings = load_settings()
    from .reading_journal import ReadingGoal
    from .reading_journal_store import ReadingJournalStore
    store = ReadingJournalStore(Database(settings.db_path))
    store.db.migrate()
    st.subheader("اهداف و تقویم مطالعه")
    with st.form("reading-goal"):
        books_target = st.number_input("هدف تعداد کتاب", min_value=0, value=1)
        pages_target = st.number_input("هدف تعداد صفحه", min_value=0, value=100)
        start = st.date_input("شروع هدف")
        end = st.date_input("پایان هدف")
        if st.form_submit_button("ثبت هدف", type="primary"):
            try:
                store.add_goal(ReadingGoal(str(__import__("uuid").uuid4()), int(books_target), int(pages_target), start, end))
                st.success("هدف مطالعه ثبت شد.")
            except ValueError as exc: st.error(str(exc))
    goals=store.goals(); goal=goals[0] if goals else None; dashboard=store.dashboard(goal)
    c1,c2,c3=st.columns(3); c1.metric("دقیقه",dashboard["minutes"]); c2.metric("صفحه",dashboard["pages"]); c3.metric("زنجیره روزانه",dashboard["streak"])
    if goal: st.json(dashboard["goal_progress"])
    st.write("نقاط عطف:", "، ".join(map(str,dashboard["milestones"])) or "هنوز ثبت نشده")
    st.dataframe([{"تاریخ":k.isoformat(),"دقیقه":v} for k,v in dashboard["calendar"].items()], use_container_width=True)



def render_knowledge_base() -> None:
    settings = load_settings()
    from .knowledge import KnowledgeNode
    from .knowledge_store import KnowledgeStore
    store = KnowledgeStore(Database(settings.db_path)); store.db.migrate()
    st.subheader("دانش شخصی، نقل‌قول و مفاهیم")
    query = st.text_input("جستجوی یکپارچه در یادداشت‌ها، نقل‌قول‌ها و مفاهیم", key="knowledge-search")
    rows = store.search(query) if query else []
    if rows: st.dataframe([{"نوع":type(x).__name__,"متن":getattr(x,"text",getattr(x,"label","")),"صفحه":getattr(x,"page",None)} for x in rows],use_container_width=True)
    with st.form("knowledge-node"):
        label=st.text_input("مفهوم"); kind=st.text_input("نوع",value="concept"); save=st.form_submit_button("ثبت مفهوم")
        if save:
            try: store.add_node(KnowledgeNode(str(__import__("uuid").uuid4()),label,kind)); st.success("مفهوم ثبت شد.")
            except ValueError as exc: st.error(str(exc))
    st.write("مفاهیم ثبت‌شده:", "، ".join(node.label for node in store.nodes()) or "—")



def render_ai_assistant() -> None:
    from .ai_service import BookAIService, local_first_provider
    settings = load_settings(); repository = BookRepository(Database(settings.db_path)); repository.db.migrate()
    rows=repository.list(limit=1000)
    st.subheader("دستیار هوشمند کتاب")
    if not rows: st.info("ابتدا کتابی به کتابخانه اضافه کنید."); return
    labels={r["id"]:r["title"] for r in rows}; book_id=st.selectbox("کتاب",list(labels),format_func=lambda x:labels[x],key="ai-book")
    action=st.selectbox("عمل",("summary","questions","recommendation","insights"),format_func=lambda x:{"summary":"خلاصه","questions":"پرسش و پاسخ","recommendation":"پیشنهاد","insights":"بینش"}[x])
    context=st.text_area("زمینه یا پرسش")
    if st.button("اجرا",type="primary"):
        try: st.write(BookAIService(local_first_provider()).action(action,labels[book_id],context))
        except RuntimeError as exc: st.error(f"اتصال به درگاه هوش مصنوعی ناموفق بود: {exc}")
    with st.expander("خلاصه فصل/کتاب و برنامه مطالعه"):
        text=st.text_area("متن",key="ai-text"); chapter=st.text_input("عنوان فصل",key="ai-chapter"); goal=st.text_input("هدف مطالعه",key="ai-goal")
        if text and st.button("خلاصه کتاب"): st.write(BookAIService(local_first_provider()).summarize(labels[book_id],text))
        if text and chapter and st.button("خلاصه فصل"): st.write(BookAIService(local_first_provider()).summarize_chapter(labels[book_id],chapter,text))
        if goal and st.button("ساخت برنامه مطالعه"): st.write(BookAIService(local_first_provider()).reading_plan("\n".join(r["title"] for r in rows),goal))



def render_semantic_search() -> None:
    from .semantic_service import SemanticLibraryService
    settings=load_settings(); service=SemanticLibraryService(Database(settings.db_path)); service.db.migrate()
    st.subheader("جستجوی معنایی و پیشنهاد کتاب")
    if st.button("بازسازی نمایه معنایی"): st.success(f"{service.rebuild()} کتاب نمایه شد.")
    query=st.text_input("جستجوی معنایی",placeholder="مثلاً فلسفه و اندیشه")
    if query:
        try:
            results=service.search(query,limit=10)
            st.dataframe([{"کتاب":r.title,"امتیاز ترکیبی":round(r.score,3),"شباهت معنایی":round(r.semantic,3),"امتیاز واژگانی":round(r.lexical,3)} for r in results],use_container_width=True)
        except ValueError as exc: st.error(str(exc))
    rows=service._documents()
    if rows:
        labels={item_id:text[:80] for item_id,text in rows}; selected=st.selectbox("برای پیشنهاد مشابه انتخاب کنید",list(labels),format_func=lambda x:labels[x])
        if st.button("پیشنهاد کتاب‌های مشابه"): st.write([r.book_id for r in service.recommend(selected,5)])


def render_reading_sessions() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("ابتدا یک کتاب به کتابخانه اضافه کنید.")
        return
    labels = {row["id"]: row["title"] for row in rows}
    book_id = st.selectbox("کتاب", list(labels), format_func=lambda value: labels[value])
    with st.form("reading-session"):
        started_at = st.date_input("تاریخ جلسه")
        minutes = st.number_input("دقیقه", min_value=0, value=30)
        pages = st.number_input("صفحات", min_value=0, value=0)
        note = st.text_area("یادداشت جلسه")
        save = st.form_submit_button("ثبت جلسه", type="primary")
    if save:
        from uuid import uuid4
        repository.add_reading_session(str(uuid4()), book_id, started_at.isoformat(), int(minutes), int(pages), note or None)
        st.success("جلسه مطالعه در SQLite ثبت شد.")
    sessions = repository.list_reading_sessions(book_id)
    st.dataframe([dict(row) for row in sessions], use_container_width=True)

def render_audiobooks() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("ابتدا یک کتاب اضافه کنید.")
        return

    labels = {row["id"]: row["title"] for row in rows}
    book_id = st.selectbox(
        "کتاب",
        list(labels),
        format_func=lambda value: labels[value],
        key="audiobook-book",
    )
    audiobooks = repository.list_audiobooks(book_id)
    st.subheader("کتاب‌های صوتی ثبت‌شده")
    if not audiobooks:
        st.info("برای این کتاب هنوز فایل صوتی ثبت نشده است.")
    for audio in audiobooks:
        st.write(f"**{audio['path']}** · {audio['format'].upper()}")
        if Path(audio["path"]).is_file():
            st.audio(audio["path"])
        else:
            st.warning("فایل صوتی در مسیر ثبت‌شده پیدا نشد.")
        duration = audio["duration_seconds"]
        position = audio["position_seconds"]
        progress = (position / duration) if duration else 0.0
        st.progress(min(progress, 1.0), text=f"پیشرفت: {position} از {duration} ثانیه")
        with st.form(f"audiobook-progress-{audio['id']}"):
            new_position = st.number_input(
                "موقعیت پخش (ثانیه)",
                min_value=0,
                max_value=duration,
                value=position,
                step=1,
            )
            speed = st.number_input(
                "سرعت پخش",
                min_value=0.25,
                max_value=4.0,
                value=float(audio["speed"]),
                step=0.05,
            )
            if st.form_submit_button("ذخیره پیشرفت"):
                repository.update_audiobook_progress(
                    audio["id"],
                    position_seconds=int(new_position),
                    speed=float(speed),
                )
                st.success("پیشرفت کتاب صوتی ذخیره شد.")

    with st.expander("افزودن فایل صوتی"):
        path = st.text_input("مسیر فایل صوتی", key="new-audiobook-path")
        audio_format = st.selectbox(
            "قالب",
            ("mp3", "m4a", "ogg", "wav", "aac", "flac"),
            key="new-audiobook-format",
        )
        duration = st.number_input(
            "مدت (ثانیه)",
            min_value=0,
            value=0,
            step=1,
            key="new-audiobook-duration",
        )
        if st.button("ثبت کتاب صوتی", type="primary"):
            from uuid import uuid4
            try:
                repository.add_audiobook(
                    str(uuid4()),
                    book_id,
                    path,
                    audio_format,
                    int(duration),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success("فایل صوتی ثبت شد.")

def render_loans() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=1000)
    if not rows:
        st.info("ابتدا یک کتاب اضافه کنید.")
        return
    labels = {row["id"]: row["title"] for row in rows}
    book_id = st.selectbox("کتاب برای نسخه فیزیکی", list(labels), format_func=lambda value: labels[value])
    copy_id = st.text_input("شناسه نسخه")
    borrower_id = st.text_input("شناسه امانت‌گیرنده")
    due_on = st.date_input("تاریخ سررسید")
    if st.button("ثبت نسخه و امانت", type="primary"):
        from uuid import uuid4
        repository.add_copy(copy_id, book_id)
        repository.add_loan(str(uuid4()), copy_id, borrower_id, __import__("datetime").date.today().isoformat(), due_on.isoformat())
        st.success("نسخه و امانت در SQLite ثبت شد.")
    st.dataframe([dict(row) for row in repository.list_loans()], use_container_width=True)


def render_ocr() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    st.subheader("OCR")
    text = st.text_area("متن OCR یا صفحه مشخصات کتاب", height=220)
    if not text:
        st.info("متن OCR را وارد کنید تا پیش‌نمایش قابل اصلاح ساخته شود.")
        return
    from .ocr import scan_to_book_draft
    draft = scan_to_book_draft(text)
    title = st.text_input("عنوان اصلاح‌شده", value=str(draft["title"]))
    publisher = st.text_input("ناشر اصلاح‌شده", value=str(draft["publisher"]))
    isbn = st.text_input("ISBN اصلاح‌شده", value=str(draft["isbn"]))
    if st.button("ذخیره نتیجه OCR", type="primary"):
        book = Book(title=title, publisher=publisher or None, isbn13=isbn if len(isbn.replace("-", "")) == 13 else None, isbn10=isbn if len(isbn.replace("-", "")) == 10 else None)
        repository.create_book(book)
        st.success("نتیجه OCR پس از اصلاح در SQLite ذخیره شد.")

def render_reports() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = [dict(row) for row in repository.list(limit=1000)]
    from .reports import inventory_analytics, report_csv, report_json
    metrics = inventory_analytics(rows)
    st.json(metrics)
    st.download_button("JSON گزارش", report_json(metrics), "books-report.json", "application/json")
    st.download_button("CSV کتاب‌ها", report_csv(rows), "books.csv", "text/csv")

def render_page(page: str) -> None:
    st.title(page)
    st.caption(PAGES[page])

    if page == "کتابخانه":
        render_library()
    elif page == "افزودن کتاب":
        render_discovery()
    elif page == "تأیید و ویرایش":
        render_confirm_edit()
    elif page == "ویرایش کتاب":
        render_edit_book()
    elif page == "حذف کتاب":
        render_delete_book()
    elif page == "مطالعه":
        render_reading_status()
    elif page == "یادداشت‌ها":
        render_personal_data()
    elif page == "دانش شخصی":
        render_knowledge_base()
    elif page == "جلسات مطالعه":
        render_reading_sessions()
    elif page == "اهداف و تقویم مطالعه":
        render_reading_journal()
    elif page == "کتاب‌های صوتی":
        render_audiobooks()
    elif page == "حاشیه‌نویسی دیجیتال":
        render_annotations()
    elif page == "قرض‌ها":
        render_loans()
    elif page == "مجموعه و ویرایش‌ها":
        render_catalog_editions()
    elif page == "اسکن و OCR":
        render_ocr()
    elif page == "گزارش‌ها":
        render_reports()
    elif page == "دستیار هوشمند":
        render_ai_assistant()
    elif page == "جستجوی معنایی":
        render_semantic_search()
    elif page == "برچسب و قفسه":
        render_organization()
    elif page == "انتقال داده":
        render_transfer()
    elif page == "پشتیبان‌گیری":
        render_backup()
    elif page == "آمار مطالعه":
        render_statistics()
    else:
        settings = load_settings()
        st.info("تنظیمات برنامه در Issueهای مرتبط تکمیل می‌شود.")
        st.code(str(settings.db_path), language="text")


def main() -> None:
    configure_page()
    page = render_sidebar()
    render_page(page)


if __name__ == "__main__":
    main()

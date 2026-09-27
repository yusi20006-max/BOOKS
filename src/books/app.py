from __future__ import annotations

import json
import sqlite3

import streamlit as st

from .config import load_settings
from .db import BookRepository, Database
from .discovery import DiscoveryService, MergedDiscoveryItem
from .providers.google_books import GoogleBooksProvider
from .providers.open_library import OpenLibraryProvider


PAGES = {
    "کتابخانه": "نمایش و مدیریت کتاب‌های ذخیره‌شده",
    "افزودن کتاب": "جستجو و انتخاب کتاب از منابع مختلف",
    "تأیید و ویرایش": "اصلاح و اعتبارسنجی اطلاعات قبل از ذخیره",
    "مطالعه": "پیگیری وضعیت و پیشرفت مطالعه",
    "یادداشت‌ها": "یادداشت‌ها و نقل‌قول‌های شخصی",
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


def _render_save_action(book) -> None:
    st.divider()
    st.subheader("افزودن به کتابخانه")
    if st.button("ذخیره کتاب در کتابخانه", type="primary", key="save-confirmed-book"):
        settings = load_settings()
        db = Database(settings.db_path)
        db.migrate()
        repository = BookRepository(db)

        existing = None
        if book.isbn13:
            existing = repository.get_by_isbn(book.isbn13)
        if existing is None and book.isbn10:
            existing = repository.get_by_isbn(book.isbn10)

        if existing is not None:
            st.warning("این کتاب با همین ISBN قبلاً در کتابخانه وجود دارد و دوباره ذخیره نشد.")
            st.session_state["saved_book_id"] = existing["id"]
            return

        try:
            book_id = repository.create_book(book)
        except sqlite3.IntegrityError:
            st.warning("رکورد مشابه قبلاً ذخیره شده است و از ایجاد Duplicate جلوگیری شد.")
            return

        st.session_state["saved_book_id"] = book_id
        st.success("کتاب با موفقیت در SQLite ذخیره شد.")

def render_library() -> None:
    settings = load_settings()
    repository = BookRepository(Database(settings.db_path))
    repository.db.migrate()
    rows = repository.list(limit=100)

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
                    authors = "، ".join(json.loads(row["authors_json"] or "[]")) or "—"
                    st.write(f"**نویسنده:** {authors}")
                    st.write(f"**ناشر:** {row['publisher'] or '—'}")
                    st.write(
                        f"**سال:** {row['publication_year'] or '—'} · "
                        f"**ISBN:** {row['isbn13'] or row['isbn10'] or '—'}"
                    )
                    st.caption("وضعیت مطالعه در Phase Reading Management تکمیل می‌شود.")
    else:
        columns = st.columns(3)
        for index, row in enumerate(rows):
            with columns[index % 3]:
                with st.container(border=True):
                    if row["cover_url"]:
                        st.image(row["cover_url"], use_container_width=True)
                    st.subheader(row["title"])
                    authors = "، ".join(json.loads(row["authors_json"] or "[]")) or "—"
                    st.write(authors)
                    st.caption(f"ISBN: {row['isbn13'] or row['isbn10'] or '—'}")
                    st.caption("وضعیت مطالعه: در فاز بعد")

def render_discovery() -> None:
    settings = load_settings()
    query = st.text_input("عنوان، نویسنده یا ISBN", placeholder="مثلاً شازده کوچولو")
    limit = st.slider("تعداد نتایج", min_value=1, max_value=20, value=10)
    search = st.button("جستجوی کتاب", type="primary", disabled=not query.strip())

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


def render_page(page: str) -> None:
    st.title(page)
    st.caption(PAGES[page])

    if page == "کتابخانه":
        render_library()
    elif page == "افزودن کتاب":
        render_discovery()
    elif page == "تأیید و ویرایش":
        render_confirm_edit()
    elif page == "مطالعه":
        st.info("مدیریت مطالعه در Phaseهای Reading Management تکمیل می‌شود.")
    elif page == "یادداشت‌ها":
        st.info("یادداشت و نقل‌قول در Phaseهای دانش شخصی تکمیل می‌شود.")
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

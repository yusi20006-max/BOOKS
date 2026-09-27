from __future__ import annotations

import json
import sqlite3

import streamlit as st

from .config import load_settings
from .db import BookRepository, Database
from .models import Book
from .discovery import DiscoveryService, MergedDiscoveryItem
from .providers.google_books import GoogleBooksProvider
from .providers.open_library import OpenLibraryProvider


PAGES = {
    "کتابخانه": "نمایش و مدیریت کتاب‌های ذخیره‌شده",
    "افزودن کتاب": "جستجو و انتخاب کتاب از منابع مختلف",
    "تأیید و ویرایش": "اصلاح و اعتبارسنجی اطلاعات قبل از ذخیره",
    "ویرایش کتاب": "ویرایش کتاب‌های ذخیره‌شده",
    "حذف کتاب": "حذف امن کتاب و بررسی Duplicate",
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
                    st.caption("وضعیت مطالعه در Phase Reading Management تکمیل می‌شود.")
    else:
        columns = st.columns(3)
        for index, row in enumerate(rows):
            with columns[index % 3]:
                with st.container(border=True):
                    if row["cover_url"]:
                        st.image(row["cover_url"], use_container_width=True)
                    st.subheader(row["title"])
                    summary = library_row_summary(row)
                    st.write(summary["authors"])
                    st.caption(f"ISBN: {summary['isbn']}")
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
    elif page == "ویرایش کتاب":
        render_edit_book()
    elif page == "حذف کتاب":
        render_delete_book()
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

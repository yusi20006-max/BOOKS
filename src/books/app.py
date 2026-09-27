from __future__ import annotations

import streamlit as st

from .config import load_settings
from .discovery import DiscoveryService, MergedDiscoveryItem
from .providers.google_books import GoogleBooksProvider
from .providers.open_library import OpenLibraryProvider


PAGES = {
    "کتابخانه": "نمایش و مدیریت کتاب‌های ذخیره‌شده",
    "افزودن کتاب": "جستجو و انتخاب کتاب از منابع مختلف",
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
        st.info("کتاب‌های شما در این بخش نمایش داده می‌شوند.")
    elif page == "افزودن کتاب":
        render_discovery()
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

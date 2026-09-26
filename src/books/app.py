from __future__ import annotations

import streamlit as st

from .config import load_settings


PAGES = {
    "کتابخانه": "نمایش و مدیریت کتاب‌های ذخیره‌شده",
    "افزودن کتاب": "افزودن کتاب از منابع مختلف",
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


def render_page(page: str) -> None:
    st.title(page)
    st.caption(PAGES[page])

    if page == "کتابخانه":
        st.info("کتاب‌های شما در این بخش نمایش داده می‌شوند.")
    elif page == "افزودن کتاب":
        st.info("افزودن کتاب در Issueهای Discovery تکمیل می‌شود.")
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

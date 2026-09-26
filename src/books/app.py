from __future__ import annotations

import streamlit as st

from .config import load_settings


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
        html, body, [class*="css"] { direction: rtl; }
        .block-container { max-width: 1200px; padding-top: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    configure_page()
    settings = load_settings()

    st.title("📚 کتابخانه من")
    st.caption("BOOKS — کتابخانه شخصی فارسی‌محور و آفلاین‌محور")
    st.sidebar.header("منو")
    st.sidebar.radio("بخش", ["کتابخانه", "افزودن کتاب", "تنظیمات"], label_visibility="collapsed")

    st.info("اسکلت اولیه آماده است. قابلیت‌های کتابخانه در Issueهای بعدی تکمیل می‌شوند.")
    st.subheader("شروع")
    st.write("از اینجا مدیریت کتاب‌های شخصی، مطالعه و دانش شما ساخته خواهد شد.")
    st.caption(f"مسیر پایگاه‌داده: {settings.db_path}")


if __name__ == "__main__":
    main()

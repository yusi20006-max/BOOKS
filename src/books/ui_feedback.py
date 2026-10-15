from __future__ import annotations

import sqlite3


def error_feedback(error: Exception) -> tuple[str, str]:
    """Return a safe Persian message and a concrete recovery hint.

    Raw exception text is intentionally omitted because it may contain local
    paths, provider details, or other implementation-specific information.
    """
    if isinstance(error, ConnectionError):
        return (
            "ارتباط با سرویس برقرار نشد.",
            "اتصال شبکه یا نشانی سرویس را بررسی کنید و پس از رفع مشکل دوباره تلاش کنید.",
        )
    if isinstance(error, FileNotFoundError):
        return (
            "فایل یا مسیر موردنیاز پیدا نشد.",
            "فایل انتخاب‌شده و مسیر ذخیره‌سازی را بررسی کنید.",
        )
    if isinstance(error, PermissionError):
        return (
            "دسترسی لازم به فایل یا مسیر وجود ندارد.",
            "مجوزهای فایل و پوشه را بررسی کنید؛ در صورت نیاز مسیر دیگری انتخاب کنید.",
        )
    if isinstance(error, sqlite3.IntegrityError):
        return (
            "داده با محدودیت‌های کتابخانه سازگار نیست یا رکورد تکراری است.",
            "شناسه، ISBN و رکوردهای مشابه را بررسی کنید و سپس دوباره تلاش کنید.",
        )
    if isinstance(error, (UnicodeDecodeError, ValueError, TypeError, KeyError)):
        return (
            "ساختار یا مقدار ورودی معتبر نیست.",
            "قالب فایل و فیلدهای واردشده را بررسی کنید؛ سپس دوباره تلاش کنید.",
        )
    if isinstance(error, OSError):
        return (
            "خواندن یا نوشتن فایل کامل نشد.",
            "فضای ذخیره‌سازی، سلامت فایل و مجوزهای مسیر را بررسی کنید.",
        )
    if isinstance(error, RuntimeError):
        return (
            "قابلیت یا سرویس موردنیاز در دسترس نیست.",
            "تنظیمات سرویس و وابستگی‌های لازم را بررسی کنید و دوباره تلاش کنید.",
        )
    return (
        "عملیات به‌دلیل یک خطای پیش‌بینی‌نشده انجام نشد.",
        "وضعیت داده‌ها را بررسی کنید؛ اگر مشکل ادامه داشت، گزارش خطا را بدون اطلاعات محرمانه ثبت کنید.",
    )


def show_recoverable_error(error: Exception, operation: str, *, recovery: str | None = None) -> None:
    import streamlit as st

    message, hint = error_feedback(error)
    if operation.endswith("ناموفق بود"):
        st.error(f"{operation}: {message}")
    else:
        st.error(f"{operation} انجام نشد: {message}")
    st.caption(recovery or hint)


def show_empty_state(message: str, *, next_step: str | None = None) -> None:
    import streamlit as st

    st.info(message)
    if next_step:
        st.caption(f"اقدام پیشنهادی: {next_step}")

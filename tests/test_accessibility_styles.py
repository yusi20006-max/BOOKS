from pathlib import Path

from books.rtl import RTL_STYLESHEET


def test_keyboard_focus_is_visible_and_not_reset():
    assert ".stApp :focus-visible" in RTL_STYLESHEET
    assert "outline: 3px solid Highlight;" in RTL_STYLESHEET
    assert "outline-offset: 3px;" in RTL_STYLESHEET
    assert "outline: none" not in RTL_STYLESHEET.lower()


def test_forced_colors_mode_keeps_system_focus_color():
    assert "@media (forced-colors: active)" in RTL_STYLESHEET
    assert "outline-color: Highlight;" in RTL_STYLESHEET


def test_reduced_motion_preference_is_respected():
    assert "@media (prefers-reduced-motion: reduce)" in RTL_STYLESHEET
    assert "animation-duration: .01ms !important;" in RTL_STYLESHEET
    assert "transition-duration: .01ms !important;" in RTL_STYLESHEET
    assert "scroll-behavior: auto !important;" in RTL_STYLESHEET


def test_accessibility_styles_are_used_by_the_streamlit_app():
    app_path = Path(__file__).resolve().parents[1] / "src" / "books" / "app.py"
    source = app_path.read_text(encoding="utf-8")
    assert "from books.rtl import RTL_STYLESHEET" in source
    assert "st.markdown(RTL_STYLESHEET, unsafe_allow_html=True)" in source

from pathlib import Path

from books.rtl import RTL_STYLESHEET


def test_streamlit_canvas_stays_ltr_while_main_and_sidebar_are_rtl():
    assert ".stApp { direction: ltr; }" in RTL_STYLESHEET
    assert ".stApp .main .block-container" in RTL_STYLESHEET
    assert "direction: rtl;" in RTL_STYLESHEET
    assert '[data-testid="stSidebarContent"]' in RTL_STYLESHEET


def test_persian_text_and_form_controls_are_right_aligned():
    assert ".stApp input," in RTL_STYLESHEET
    assert ".stApp textarea," in RTL_STYLESHEET
    assert "text-align: right;" in RTL_STYLESHEET
    assert ".stApp th," in RTL_STYLESHEET
    assert ".stApp td," in RTL_STYLESHEET


def test_machine_oriented_values_are_ltr_and_bidi_isolated():
    for selector in (
        'input[type="number"]',
        'input[type="url"]',
        'input[type="email"]',
        'input[type="password"]',
        ".stApp code",
        ".stApp pre",
        '.stApp [dir="ltr"]',
    ):
        assert selector in RTL_STYLESHEET
    assert "unicode-bidi: isolate;" in RTL_STYLESHEET


def test_rtl_stylesheet_is_used_by_the_actual_app_entrypoint():
    app_path = Path(__file__).resolve().parents[1] / "src" / "books" / "app.py"
    app_source = app_path.read_text(encoding="utf-8")
    assert "from books.rtl import RTL_STYLESHEET" in app_source
    assert "st.markdown(RTL_STYLESHEET, unsafe_allow_html=True)" in app_source


def test_small_screen_spacing_remains_defined():
    assert "@media (max-width: 768px)" in RTL_STYLESHEET
    assert "padding: 1rem .75rem 3rem;" in RTL_STYLESHEET

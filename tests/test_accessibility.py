from books.accessibility import validate_ui_contract

def test_persian_ui_contract_is_rtl_and_keyboard_accessible():
    c=validate_ui_contract()
    assert c.rtl and c.keyboard_navigation and c.semantic_labels and c.mobile_layout

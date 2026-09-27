from books.search_ranking import rank

def test_title_exact_match_has_priority():
    assert rank("شازده کوچولو", title="شازده کوچولو") > rank("شازده کوچولو", authors=("نویسنده",))

def test_zwnj_and_space_are_tolerant():
    assert rank("می روم", title="می‌روم") > 0

import pytest

import pytest
from books.db import BookRepository, Database
from books.models import Book


def test_digital_annotations_persist_and_are_scoped(tmp_path):
    db=Database(str(tmp_path/"books.sqlite3")); db.migrate(); repo=BookRepository(db)
    first=repo.create_book(Book(title="کتاب اول")); second=repo.create_book(Book(title="کتاب دوم"))
    repo.add_annotation("a1", first, "highlight", "page:12", "متن مهم", "یادداشت")
    repo.add_annotation("a2", second, "bookmark", "chapter:3")
    rows=repo.list_annotations(first)
    assert len(rows)==1 and rows[0]["kind"]=="highlight" and rows[0]["text"]=="متن مهم"
    assert repo.list_annotations(second)[0]["kind"]=="bookmark"
    with pytest.raises(ValueError): repo.add_annotation("bad", first, "invalid", "page:1")

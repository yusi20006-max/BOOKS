from datetime import date

from books.db import BookRepository, Database
from books.models import Book
from books.reading_journal import ReadingGoal
from books.reading_journal_store import ReadingJournalStore


def test_phase12_goals_sessions_streak_and_calendar(tmp_path):
    db=Database(tmp_path/"books.sqlite3"); db.migrate(); repo=BookRepository(db); bid=repo.create_book(Book(title="کتاب")); store=ReadingJournalStore(db)
    store.add_goal(ReadingGoal("g",5,100,date(2026,9,1),date(2026,9,30)))
    repo.add_reading_session("s1",bid,"2026-09-25",30,4); repo.add_reading_session("s2",bid,"2026-09-26",20,6)
    dash=store.dashboard(store.goals()[0]); assert dash["streak"]==2 and dash["pages"]==10 and dash["goal_progress"]["pages"]==10.0

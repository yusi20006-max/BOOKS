from __future__ import annotations

import sqlite3
from datetime import date
from uuid import uuid4

from .db import Database, transaction
from .reading_journal import ReadingGoal, ReadingSession, calendar_sessions, goal_progress, milestones, streak_days


class ReadingJournalStore:
    def __init__(self, db: Database): self.db=db
    def add_goal(self, goal: ReadingGoal) -> str:
        with transaction(self.db) as conn:
            conn.execute("INSERT INTO reading_goals(id,target_books,target_pages,start_date,end_date) VALUES(?,?,?,?,?)", (goal.id,goal.target_books,goal.target_pages,goal.start.isoformat() if goal.start else None,goal.end.isoformat() if goal.end else None))
        return goal.id
    def goals(self) -> list[ReadingGoal]:
        with self.db.connect() as conn:
            rows=conn.execute("SELECT * FROM reading_goals ORDER BY start_date DESC,id").fetchall()
        return [ReadingGoal(r["id"],r["target_books"],r["target_pages"],date.fromisoformat(r["start_date"]) if r["start_date"] else None,date.fromisoformat(r["end_date"]) if r["end_date"] else None) for r in rows]
    def sessions(self, book_id: str | None = None) -> list[ReadingSession]:
        with self.db.connect() as conn:
            if book_id:
                rows=conn.execute("SELECT * FROM reading_sessions WHERE book_id=? ORDER BY started_at",(book_id,)).fetchall()
            else:
                rows=conn.execute("SELECT * FROM reading_sessions ORDER BY started_at").fetchall()
        return [ReadingSession(r["id"],r["book_id"],date.fromisoformat(r["started_at"][:10]),r["minutes"],r["pages"],r["note"]) for r in rows]
    def dashboard(self, goal: ReadingGoal | None = None) -> dict[str, object]:
        sessions=self.sessions(); days={s.started_at for s in sessions}; pages=sum(s.pages for s in sessions); books=len({s.book_id for s in sessions})
        result={"minutes":sum(s.minutes for s in sessions),"pages":pages,"books":books,"streak":streak_days(days),"milestones":milestones(streak_days(days)),"calendar":calendar_sessions(sessions)}
        if goal: result["goal_progress"]=goal_progress(goal,books,pages)
        return result

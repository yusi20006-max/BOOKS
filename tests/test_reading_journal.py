from datetime import date

from books.reading_journal import ReadingGoal, ReadingSession, calendar_sessions, goal_progress, milestones, streak_days


def test_goal_and_progress():
 g=ReadingGoal("g",10,1000,date(2026,1,1),date(2026,12,31)); assert goal_progress(g,2,250)=={"books":20.0,"pages":25.0}
def test_session_calendar_and_streak():
 ss=[ReadingSession("1","b",date(2026,9,25),30,4),ReadingSession("2","b",date(2026,9,26),20,2)]
 assert calendar_sessions(ss)[date(2026,9,25)]==30; assert streak_days({x.started_at for x in ss})==2
def test_milestones(): assert milestones(31)==(7,14,30)

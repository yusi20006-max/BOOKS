from datetime import date
import sqlite3

from books.ai import FailoverAI, book_assistant, personalized_reading_plan, summarize_book, summarize_chapter
from books.digital import Annotation
from books.edition_compare import compare_editions, is_duplicate_edition
from books.knowledge import KnowledgeEdge, KnowledgeNode, Note, Quote, knowledge_search
from books.reading_journal import ReadingGoal, ReadingSession, calendar_sessions, goal_progress, milestones, streak_days
from books.search_ranking import rank
from books.semantic import HashEmbeddingProvider, VectorStore, hybrid_score, recommend_similar, semantic_search
from books.series import Series, Volume
from books.translation_views import TranslationView, group_by_translation, translation_view
from books.catalog import Edition, Translation


class Provider:
    def __init__(self, name, result="ok", fail=False):
        self.name, self.result, self.fail = name, result, fail
    def complete(self, prompt):
        if self.fail:
            raise RuntimeError("down")
        return self.result


def test_phase_10_to_15_acceptance_contracts():
    annotation = Annotation("a1", "highlight", "page:12", "متن", "یادداشت")
    assert annotation.kind == "highlight"

    left = Edition("e1", "w1", "ناشر", 1400, isbn13="9786000000000")
    right = Edition("e2", "w1", "ناشر", 1400, isbn13="9786000000000")
    assert is_duplicate_edition(left, right)
    assert compare_editions(left, right).score >= 100

    series = Series("s1", " مجموعه بنیاد ")
    assert Volume("v1", series.id, right.id, 1).number == 1
    tr = Translation("t1", right.id, "fa", ("tr1",))
    assert isinstance(translation_view(right, tr), TranslationView)
    assert list(group_by_translation(right, [tr])) == ["fa"]

    goal = ReadingGoal("g1", 10, 1000, date(2026, 1, 1), date(2026, 12, 31))
    sessions = [ReadingSession("s1", "b1", date(2026, 9, 26), 30, 5)]
    assert goal_progress(goal, 2, 250)["pages"] == 25.0
    assert calendar_sessions(sessions)[date(2026, 9, 26)] == 30
    assert streak_days({date(2026, 9, 25), date(2026, 9, 26)}) == 2
    assert milestones(31) == (7, 14, 30)

    quote = Quote("q1", "b1", "کتابخانه شخصی", 10)
    note = Note("n1", "b1", "یادداشت مهم", 11)
    node = KnowledgeNode("k1", "کتابخانه")
    assert isinstance(KnowledgeEdge("k1", "q1", "مرتبط"), KnowledgeEdge)
    assert knowledge_search("کتابخانه", [quote], [note], [node]) == [quote, node]

    local = Provider("local", "پاسخ")
    cloud = Provider("cloud", "ابر")
    assert FailoverAI([local, cloud]).complete("x") == "پاسخ"
    assert FailoverAI([Provider("local", fail=True), cloud]).complete("x") == "ابر"
    assert book_assistant(local, "summary", "کتاب") == "پاسخ"
    assert summarize_book(local, "کتاب", "متن") == "پاسخ"
    assert summarize_chapter(local, "کتاب", "فصل ۱", "متن") == "پاسخ"
    assert personalized_reading_plan(local, "کتاب‌ها", "هفته‌ای یک کتاب") == "پاسخ"

    provider = HashEmbeddingProvider(32)
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE embeddings(item_id TEXT PRIMARY KEY,text TEXT,vector_json TEXT NOT NULL)")
    store = VectorStore(conn)
    store.put("b1", "کتاب فارسی", provider.embed("کتاب فارسی"))
    store.put("b2", "مهندسی نرم افزار", provider.embed("مهندسی نرم افزار"))
    assert store.search(provider.embed("کتاب فارسی"), 1)[0][1] == "b1"
    assert semantic_search("کتاب فارسی", [("b1", "کتاب فارسی"), ("b2", "نرم افزار")], provider)[0][1] == "b1"
    assert recommend_similar("b1", [("b1", "کتاب فارسی"), ("b2", "کتاب فارسی"), ("b3", "آشپزی")], provider, 1)[0][1] == "b2"
    assert hybrid_score(1, 0) == 0.45
    assert rank("می روم", title="می‌روم") > 0

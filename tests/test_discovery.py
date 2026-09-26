from dataclasses import dataclass

from books.discovery import DiscoveryService


@dataclass
class Page:
    items: tuple
    total_items: int


class FakeProvider:
    def __init__(self, items=(), error=None):
        self.items = tuple(items)
        self.error = error
        self.calls = 0

    def search(self, query, *, language, start_index, limit):
        self.calls += 1
        if self.error:
            raise RuntimeError(self.error)
        return Page(self.items, len(self.items))


def test_parallel_strategy_is_provider_agnostic():
    google = FakeProvider(("g",))
    open_library = FakeProvider(("o",))
    response = DiscoveryService(
        [("google", google), ("open_library", open_library)]
    ).search("کتاب")

    assert [r.provider for r in response.results] == ["google", "open_library"]
    assert response.results[0].items == ("g",)
    assert response.failures == ()


def test_sequential_strategy_falls_back_after_failure():
    failing = FakeProvider(error="temporary failure")
    working = FakeProvider(("ok",))
    response = DiscoveryService(
        [("first", failing), ("second", working)]
    ).search("کتاب", strategy="sequential")

    assert response.results[0].error == "temporary failure"
    assert response.results[1].items == ("ok",)
    assert [f.provider for f in response.failures] == ["first"]


def test_parallel_failure_does_not_hide_success():
    response = DiscoveryService(
        [("bad", FakeProvider(error="down")), ("good", FakeProvider(("ok",)))]
    ).search("کتاب", strategy="parallel")

    assert len(response.failures) == 1
    assert response.results[1].items == ("ok",)

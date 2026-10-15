from books.cache import TTLCache


def test_ttl_cache_expires_entries_using_monotonic_clock():
    now = [10.0]
    cache = TTLCache[str, str](ttl_seconds=5, clock=lambda: now[0])
    cache.set("key", "value")
    assert cache.get("key") == "value"
    now[0] = 15.0
    assert cache.get("key") is None
    assert len(cache) == 0


def test_ttl_cache_evicts_least_recently_used_entry():
    cache = TTLCache[str, int](max_entries=2, ttl_seconds=30)
    cache.set("first", 1)
    cache.set("second", 2)
    assert cache.get("first") == 1  # promote first to most-recently used
    cache.set("third", 3)
    assert cache.get("first") == 1
    assert cache.get("second") is None
    assert cache.get("third") == 3


def test_ttl_cache_rejects_invalid_capacity_and_ttl():
    import pytest

    with pytest.raises(ValueError, match="max_entries"):
        TTLCache(max_entries=0)
    with pytest.raises(ValueError, match="ttl_seconds"):
        TTLCache(ttl_seconds=0)

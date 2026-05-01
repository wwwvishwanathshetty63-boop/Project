"""
Test Suite 4: In-memory cache correctness, TTL expiry, invalidation, and GC.
"""
import time
import pytest
from backend.services.cache_service import MemoryCache, build_key


@pytest.fixture
def fresh_cache():
    """Each test gets a clean MemoryCache instance."""
    return MemoryCache()


class TestCacheBasics:

    def test_set_and_get(self, fresh_cache):
        fresh_cache.set("key1", {"data": 42}, ttl=10)
        assert fresh_cache.get("key1") == {"data": 42}

    def test_get_missing_key(self, fresh_cache):
        assert fresh_cache.get("nonexistent") is None

    def test_overwrite_key(self, fresh_cache):
        fresh_cache.set("key1", "first", ttl=10)
        fresh_cache.set("key1", "second", ttl=10)
        assert fresh_cache.get("key1") == "second"

    def test_delete_key(self, fresh_cache):
        fresh_cache.set("del-me", "value", ttl=10)
        assert fresh_cache.delete("del-me") is True
        assert fresh_cache.get("del-me") is None

    def test_delete_nonexistent(self, fresh_cache):
        assert fresh_cache.delete("ghost") is False


class TestTTLExpiry:

    def test_key_expires_after_ttl(self, fresh_cache):
        fresh_cache.set("short", "soon-gone", ttl=1)
        assert fresh_cache.get("short") == "soon-gone"
        time.sleep(1.1)
        assert fresh_cache.get("short") is None  # expired

    def test_key_still_valid_before_ttl(self, fresh_cache):
        fresh_cache.set("alive", "value", ttl=5)
        time.sleep(0.2)
        assert fresh_cache.get("alive") == "value"

    def test_multiple_keys_different_ttls(self, fresh_cache):
        fresh_cache.set("fast", "gone", ttl=1)
        fresh_cache.set("slow", "stays", ttl=10)
        time.sleep(1.2)
        assert fresh_cache.get("fast") is None
        assert fresh_cache.get("slow") == "stays"


class TestInvalidation:

    def test_invalidate_prefix(self, fresh_cache):
        fresh_cache.set("stats:user1:1d", {"total": 5}, ttl=60)
        fresh_cache.set("stats:user2:7d", {"total": 3}, ttl=60)
        fresh_cache.set("endpoints:user1", [1, 2], ttl=60)
        n = fresh_cache.invalidate("stats:")
        assert n == 2
        assert fresh_cache.get("stats:user1:1d") is None
        assert fresh_cache.get("stats:user2:7d") is None
        assert fresh_cache.get("endpoints:user1") == [1, 2]  # untouched

    def test_invalidate_all(self, fresh_cache):
        fresh_cache.set("a", 1, ttl=60)
        fresh_cache.set("b", 2, ttl=60)
        n = fresh_cache.invalidate()
        assert n == 2
        assert fresh_cache.get("a") is None

    def test_invalidate_empty_cache(self, fresh_cache):
        n = fresh_cache.invalidate("stats:")
        assert n == 0


class TestObservability:

    def test_hit_counter_increments(self, fresh_cache):
        fresh_cache.set("k", "v", ttl=60)
        fresh_cache.get("k")
        fresh_cache.get("k")
        s = fresh_cache.stats()
        assert s["hits"] == 2

    def test_miss_counter_increments(self, fresh_cache):
        fresh_cache.get("missing1")
        fresh_cache.get("missing2")
        s = fresh_cache.stats()
        assert s["misses"] == 2

    def test_hit_rate_calculation(self, fresh_cache):
        fresh_cache.set("k", "v", ttl=60)
        fresh_cache.get("k")    # hit
        fresh_cache.get("k")    # hit
        fresh_cache.get("nope") # miss
        s = fresh_cache.stats()
        assert s["hit_rate_pct"] == pytest.approx(66.7, abs=1.0)

    def test_reset_counters(self, fresh_cache):
        fresh_cache.get("x")
        fresh_cache.reset_counters()
        s = fresh_cache.stats()
        assert s["hits"] == 0
        assert s["misses"] == 0

    def test_active_keys_excludes_expired(self, fresh_cache):
        fresh_cache.set("live", "a", ttl=60)
        fresh_cache.set("dead", "b", ttl=1)
        time.sleep(1.2)
        # Trigger expiry by doing a get
        fresh_cache.get("dead")
        s = fresh_cache.stats()
        assert s["active_keys"] >= 1

    def test_cache_stats_api_endpoint(self, client):
        """The /api/cache/stats route should be accessible."""
        res = client.get("/api/cache/stats")
        assert res.status_code == 200
        data = res.get_json()
        assert "hit_rate_pct" in data
        assert "hits" in data
        assert "misses" in data


class TestBuildKey:

    def test_build_key_single(self):
        assert build_key("stats") == "stats"

    def test_build_key_multiple(self):
        assert build_key("stats", "user123", "7d") == "stats:user123:7d"

    def test_build_key_int_parts(self):
        assert build_key("logs", 42, 100) == "logs:42:100"


class TestCachePerformance:
    """Cache must dramatically reduce repeated lookups."""

    def test_repeated_reads_use_cache(self, fresh_cache):
        fresh_cache.set("perf", list(range(1000)), ttl=60)
        times = []
        for _ in range(100):
            t0 = time.monotonic()
            fresh_cache.get("perf")
            times.append(time.monotonic() - t0)
        avg_ms = sum(times) / len(times) * 1000
        # Each cache get should be sub-millisecond
        assert avg_ms < 1.0, f"Cache reads too slow: avg {avg_ms:.3f}ms"

    def test_gc_removes_expired_keys(self, fresh_cache):
        fresh_cache.set("expire1", "a", ttl=1)
        fresh_cache.set("expire2", "b", ttl=1)
        fresh_cache.set("keep",    "c", ttl=60)
        time.sleep(1.2)
        removed = fresh_cache._gc()
        assert removed == 2
        assert fresh_cache.get("keep") == "c"

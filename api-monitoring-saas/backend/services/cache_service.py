"""In-memory cache with TTL for Supabase/PostgreSQL data to reduce database round-trips.

Features
--------
- Thread-safe reads and writes via a single lock
- Per-key TTL with lazy expiry on read + periodic background GC
- Hit / miss counters for observability
- prefix-scoped invalidation for grouped key namespaces
- Decorator helpers: `cached` and `invalidates`
"""
import time
import threading
import logging

logger = logging.getLogger(__name__)

# ── Default TTLs (seconds) ────────────────────────────────────────────────────
TTL_STATS        = 20   # dashboard /stats
TTL_CHART        = 15   # response-time charts
TTL_ENDPOINTS    = 20   # endpoint list
TTL_ANALYTICS    = 30   # company analytics (heavy query)
TTL_LOGS         = 10   # per-endpoint log pages
TTL_PROFILE      = 60   # user profile (changes rarely)
TTL_EMPLOYEES         = 30   # employee list under a company
TTL_COMPANY_ACTIVITY  = 30   # per-employee activity on company dashboard
TTL_SHORT        = 10   # generic short-lived data

# GC: remove expired keys every N seconds to avoid unbounded memory growth
_GC_INTERVAL_SECONDS = 120


class MemoryCache:
    """Thread-safe in-memory cache with per-key TTL and observability counters."""

    def __init__(self):
        self._store: dict = {}          # key -> {"value": ..., "expires_at": float}
        self._lock  = threading.Lock()
        self._hits  = 0
        self._misses = 0
        self._start_gc_thread()

    # ── Core API ──────────────────────────────────────────────────────────────

    def get(self, key: str):
        """Return cached value or None (on miss / expiry)."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.monotonic() > entry["expires_at"]:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry["value"]

    def set(self, key: str, value, ttl: int = TTL_SHORT) -> None:
        """Store *value* under *key* with a TTL in seconds."""
        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": time.monotonic() + ttl,
            }

    def delete(self, key: str) -> bool:
        """Remove a single key. Returns True if it existed."""
        with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
            return existed

    def invalidate(self, prefix: str | None = None) -> int:
        """Clear cache entries.

        If *prefix* is given only keys that **start with** that prefix are
        removed.  Returns the number of keys deleted.
        """
        with self._lock:
            if prefix:
                keys = [k for k in self._store if k.startswith(prefix)]
            else:
                keys = list(self._store.keys())
            for k in keys:
                del self._store[k]
            if keys:
                logger.debug(
                    "Cache invalidated %d key(s) [prefix=%r]", len(keys), prefix
                )
            return len(keys)

    # ── Observability ─────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return live cache statistics."""
        with self._lock:
            now = time.monotonic()
            total  = len(self._store)
            active = sum(1 for e in self._store.values() if now < e["expires_at"])
            total_req = self._hits + self._misses
            hit_rate  = round(self._hits / total_req * 100, 1) if total_req else 0
            return {
                "total_keys":  total,
                "active_keys": active,
                "hits":        self._hits,
                "misses":      self._misses,
                "hit_rate_pct": hit_rate,
            }

    def reset_counters(self) -> None:
        """Reset hit/miss counters (e.g. between test runs)."""
        with self._lock:
            self._hits = 0
            self._misses = 0

    # ── Background GC ─────────────────────────────────────────────────────────

    def _gc(self) -> int:
        """Remove all expired entries. Returns count of removed keys."""
        with self._lock:
            now  = time.monotonic()
            dead = [k for k, e in self._store.items() if now > e["expires_at"]]
            for k in dead:
                del self._store[k]
            if dead:
                logger.debug("Cache GC: evicted %d expired key(s)", len(dead))
            return len(dead)

    def _start_gc_thread(self) -> None:
        """Start a daemon thread that runs GC periodically."""
        def _loop():
            while True:
                time.sleep(_GC_INTERVAL_SECONDS)
                try:
                    self._gc()
                except Exception:
                    pass  # never crash the GC thread

        t = threading.Thread(target=_loop, name="cache-gc", daemon=True)
        t.start()


# ── Global singleton ───────────────────────────────────────────────────────────
cache = MemoryCache()


# ── Convenience helpers ────────────────────────────────────────────────────────

def build_key(*parts) -> str:
    """Join parts with ':' to build a structured cache key.

    Example::

        build_key("stats", user_id, "7d")  →  "stats:<uid>:7d"
    """
    return ":".join(str(p) for p in parts)

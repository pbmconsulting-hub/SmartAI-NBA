"""utils/cache.py – Tiered TTL in-memory cache."""
import time
import threading
from utils.logger import get_logger

_logger = get_logger(__name__)

CACHE_TIERS = {
    "live": 30,
    "odds": 120,
    "stats": 900,
    "projections": 3600,
    "static": 86400,
}

_store: dict = {}
_lock = threading.Lock()


def cache_get(key: str, tier: str = "stats"):
    """Retrieve a value from cache if not expired.

    Args:
        key: Cache key.
        tier: One of the CACHE_TIERS keys (determines TTL).

    Returns:
        Cached value or None if missing/expired.
    """
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        ttl = CACHE_TIERS.get(tier, 900)
        if time.time() - entry["ts"] > ttl:
            _store.pop(key, None)
            return None
        return entry["value"]


def cache_set(key: str, value, tier: str = "stats") -> None:
    """Store a value in cache.

    Args:
        key: Cache key.
        value: Value to store.
        tier: Cache tier (controls TTL on retrieval).
    """
    with _lock:
        _store[key] = {"value": value, "ts": time.time(), "tier": tier}


def cache_invalidate(key: str) -> None:
    """Remove a single key from cache.

    Args:
        key: Cache key to remove.
    """
    with _lock:
        _store.pop(key, None)


def cache_clear_tier(tier: str) -> int:
    """Remove all keys belonging to a specific tier.

    Args:
        tier: Cache tier name.

    Returns:
        Number of keys removed.
    """
    with _lock:
        keys = [k for k, v in _store.items() if v.get("tier") == tier]
        for k in keys:
            _store.pop(k, None)
        return len(keys)


def get_cache_stats() -> dict:
    """Return cache statistics.

    Returns:
        Dict with total keys and per-tier counts.
    """
    with _lock:
        tier_counts: dict = {}
        now = time.time()
        expired = 0
        for entry in _store.values():
            t = entry.get("tier", "unknown")
            tier_counts[t] = tier_counts.get(t, 0) + 1
            ttl = CACHE_TIERS.get(t, 900)
            if now - entry["ts"] > ttl:
                expired += 1
        return {"total": len(_store), "tiers": tier_counts, "expired": expired}

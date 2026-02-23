"""
Memory Cache Implementation

Provides efficient memory cache with LRU eviction strategy.
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry."""

    value: T
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0


class MemoryCache:
    """Memory cache.

    Provides LRU cache functionality with:
    - Maximum capacity limit
    - TTL expiration
    - Batch clearing by key prefix
    - Statistics
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int | None = None,
    ):
        """Initialize cache.

        Args:
            max_size: Maximum cache entry count
            default_ttl_seconds: Default TTL (seconds), None means never expire
        """
        self._max_size = max_size
        self._default_ttl = timedelta(seconds=default_ttl_seconds) if default_ttl_seconds else None
        self._cache: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value, or None if not exists or expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check if expired
            if self._is_expired(entry):
                del self._cache[key]
                self._misses += 1
                return None

            # Update access info (LRU)
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set cache value.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL (seconds), None means use default TTL
        """
        with self._lock:
            now = datetime.now()

            # Check if eviction needed
            if key not in self._cache and len(self._cache) >= self._max_size:
                self._evict_lru()

            entry = CacheEntry(
                value=value,
                created_at=now,
                last_accessed=now,
                access_count=0,
            )

            self._cache[key] = entry
            self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Delete cache entry.

        Args:
            key: Cache key

        Returns:
            Whether deletion was successful
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def clear_by_prefix(self, prefix: str) -> int:
        """Clear cache by key prefix.

        Args:
            prefix: Key prefix

        Returns:
            Number of entries cleared
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def has(self, key: str) -> bool:
        """Check if key exists and not expired.

        Args:
            key: Cache key

        Returns:
            Whether key exists and not expired
        """
        with self._lock:
            if key not in self._cache:
                return False

            if self._is_expired(self._cache[key]):
                del self._cache[key]
                return False

            return True

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], T],
        ttl_seconds: int | None = None,
    ) -> T:
        """Get cached value, compute and cache if not exists.

        Args:
            key: Cache key
            compute_fn: Compute function
            ttl_seconds: TTL (seconds)

        Returns:
            Cached value or computed result
        """
        value = self.get(key)
        if value is not None:
            return value

        value = compute_fn()
        self.set(key, value, ttl_seconds)
        return value

    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary containing statistics
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }

    def cleanup_expired(self) -> int:
        """Clean up expired cache entries.

        Returns:
            Number of entries cleaned
        """
        with self._lock:
            if self._default_ttl is None:
                return 0

            expired_keys = [k for k, v in self._cache.items() if self._is_expired(v)]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def _is_expired(self, entry: CacheEntry[Any]) -> bool:
        """Check if entry is expired."""
        if self._default_ttl is None:
            return False

        age = datetime.now() - entry.created_at
        return age > self._default_ttl

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            self._cache.popitem(last=False)


# Global singleton cache instance
_global_cache: MemoryCache | None = None
_cache_lock = threading.Lock()


def get_global_cache(max_size: int = 1000, ttl_seconds: int | None = None) -> MemoryCache:
    """Get global cache instance.

    Args:
        max_size: Maximum cache size
        ttl_seconds: Default TTL

    Returns:
        Global cache instance
    """
    global _global_cache

    with _cache_lock:
        if _global_cache is None:
            _global_cache = MemoryCache(
                max_size=max_size,
                default_ttl_seconds=ttl_seconds,
            )

        return _global_cache


def reset_global_cache() -> None:
    """Reset global cache."""
    global _global_cache

    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
        _global_cache = None

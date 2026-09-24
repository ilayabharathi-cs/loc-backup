"""Bounded LRU Cache with Checksum Verification for Instant Virtual Recovery."""

import threading
import hashlib
from collections import OrderedDict
from typing import Optional, Dict, Any, Tuple
from app.services.v12.virtual_recovery.provider_base import IntegrityVerificationError


class BoundedLruCache:
    """
    Thread-safe, bounded in-memory LRU cache.
    Enforces maximum byte capacity and strict checksum validation.
    """

    def __init__(self, max_size_bytes: int = 100 * 1024 * 1024):  # Default 100MB
        self.max_size_bytes = max_size_bytes
        self.current_bytes = 0
        self._lock = threading.Lock()
        # Key: (session_id, logical_path) -> (data_bytes, sha256)
        self._cache: OrderedDict[Tuple[str, str], Tuple[bytes, str]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, session_id: str, logical_path: str) -> Optional[bytes]:
        """
        Retrieves cached bytes with strict checksum validation.
        Moves accessed item to most-recently-used position.
        """
        key = (session_id, logical_path)
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            data, expected_sha = self._cache[key]
            # Move to MRU
            self._cache.move_to_end(key)

            # Integrity verification
            actual_sha = hashlib.sha256(data).hexdigest()
            if actual_sha.lower() != expected_sha.lower():
                # Poisoned cache entry detected; evict immediately and record miss
                del self._cache[key]
                self.current_bytes -= len(data)
                self.misses += 1
                raise IntegrityVerificationError(
                    f"Cache poisoning detected for '{logical_path}': expected {expected_sha}, got {actual_sha}"
                )

            self.hits += 1
            return data

    def put(self, session_id: str, logical_path: str, data: bytes, expected_sha: str) -> bool:
        """
        Inserts bytes into cache with LRU eviction if capacity would be exceeded.
        """
        item_size = len(data)
        if item_size > self.max_size_bytes:
            # Single item larger than entire cache; do not store in cache
            return False

        # Validate checksum before caching
        actual_sha = hashlib.sha256(data).hexdigest()
        if expected_sha and actual_sha.lower() != expected_sha.lower():
            raise IntegrityVerificationError(
                f"Cannot cache corrupt payload for '{logical_path}': expected {expected_sha}, got {actual_sha}"
            )

        key = (session_id, logical_path)
        with self._lock:
            # If already present, remove old size
            if key in self._cache:
                old_data, _ = self._cache[key]
                self.current_bytes -= len(old_data)
                del self._cache[key]

            # Evict LRU items until room is available
            while self.current_bytes + item_size > self.max_size_bytes and self._cache:
                evicted_key, (evicted_data, _) = self._cache.popitem(last=False)
                self.current_bytes -= len(evicted_data)
                self.evictions += 1

            self._cache[key] = (data, actual_sha)
            self.current_bytes += item_size
            return True

    def invalidate_session(self, session_id: str) -> int:
        """
        Removes all cached entries for a finished or unmounted session.
        """
        removed = 0
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k[0] == session_id]
            for k in keys_to_remove:
                data, _ = self._cache.pop(k)
                self.current_bytes -= len(data)
                removed += 1
        return removed

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_ratio = (self.hits / total) if total > 0 else 0.0
            return {
                "max_size_bytes": self.max_size_bytes,
                "current_bytes": self.current_bytes,
                "cached_items_count": len(self._cache),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_ratio": round(hit_ratio, 4)
            }


# Global singleton cache instance for virtual recovery
_global_ivr_cache: Optional[BoundedLruCache] = None

def get_ivr_cache(max_size_bytes: int = 100 * 1024 * 1024) -> BoundedLruCache:
    global _global_ivr_cache
    if _global_ivr_cache is None:
        _global_ivr_cache = BoundedLruCache(max_size_bytes=max_size_bytes)
    return _global_ivr_cache

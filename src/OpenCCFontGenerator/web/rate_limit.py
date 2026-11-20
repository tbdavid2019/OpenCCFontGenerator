"""In-memory sliding-window rate limiter keyed by client IP."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Deque, Dict, Optional


@dataclass(frozen=True)
class RateLimitResult:
    """Decision returned by the sliding-window limiter."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class SlidingWindowRateLimiter:
    """Thread-safe 60-second sliding-window limiter with bounded key capacity."""

    def __init__(
        self,
        limit_per_minute: int,
        window_seconds: int = 60,
        max_keys: int = 4096,
        prune_interval_seconds: float = 15.0,
    ) -> None:
        self.limit = max(0, limit_per_minute)
        self.window_seconds = window_seconds
        self.max_keys = max(1, max_keys)
        self.prune_interval_seconds = max(0.0, prune_interval_seconds)
        self._hits: Dict[str, Deque[float]] = {}
        self._last_prune: float = 0.0
        self._lock = threading.Lock()

    def _prune_stale_unlocked(self, cutoff: float, current: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]
        for stale_key in stale:
            del self._hits[stale_key]
        self._last_prune = current

    def check_and_record(self, key: str, now: Optional[float] = None) -> RateLimitResult:
        """Record a request if under the limit; otherwise report retry_after seconds."""
        if self.limit <= 0:
            return RateLimitResult(allowed=True, limit=0, remaining=0, retry_after=0)

        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds

        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                if len(self._hits) >= self.max_keys:
                    self._prune_stale_unlocked(cutoff, current)
                    while len(self._hits) >= self.max_keys:
                        oldest_key = min(
                            self._hits.items(),
                            key=lambda kv: kv[1][-1] if kv[1] else -1.0,
                        )[0]
                        del self._hits[oldest_key]
                bucket = deque()
                self._hits[key] = bucket

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(1, int(bucket[0] + self.window_seconds - current) + 1)
                return RateLimitResult(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    retry_after=retry_after,
                )

            bucket.append(current)
            if len(self._hits) > 1024 and (current - self._last_prune) >= self.prune_interval_seconds:
                self._prune_stale_unlocked(cutoff, current)

            remaining = max(0, self.limit - len(bucket))
            return RateLimitResult(allowed=True, limit=self.limit, remaining=remaining, retry_after=0)

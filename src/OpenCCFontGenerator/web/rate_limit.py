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
    """Thread-safe 60-second sliding-window limiter."""

    def __init__(self, limit_per_minute: int, window_seconds: int = 60) -> None:
        self.limit = max(0, limit_per_minute)
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, key: str, now: Optional[float] = None) -> RateLimitResult:
        """Record a request if under the limit; otherwise report retry_after seconds."""
        if self.limit <= 0:
            return RateLimitResult(allowed=True, limit=0, remaining=0, retry_after=0)

        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds

        with self._lock:
            bucket = self._hits.setdefault(key, deque())
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
            # Prune stale buckets periodically when map grows
            if len(self._hits) > 1024:
                stale = [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]
                for stale_key in stale:
                    del self._hits[stale_key]

            remaining = max(0, self.limit - len(bucket))
            return RateLimitResult(allowed=True, limit=self.limit, remaining=remaining, retry_after=0)

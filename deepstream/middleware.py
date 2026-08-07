"""Request-guard middleware for the Deepstream HTTP server.

Centralizes the hardening concerns (request body caps, per-IP rate
limiting, security headers) that the local dev backend applies to every
response. Production uses the same policies at the edge / Netlify
Functions layer.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from deepstream import config

# Cap request bodies so a hostile client cannot exhaust memory with a huge
# Content-Length (webhooks are small JSON documents).
MAX_BODY_BYTES = 1_048_576  # 1 MiB

# Security headers applied to every response (static pages + JSON endpoints).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class RateLimiter:
    """Simple in-memory sliding-window rate limiter, keyed by client IP.

    Best-effort guard for the local dev backend; production should add an
    edge-level (CDN/WAF) rate limit in front of the Netlify Functions.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True


# Per-IP budgets. Generous so legitimate polls/retries are never blocked.
RATE_LIMITS = {
    config.CREATE_ORDER_API_PATH: RateLimiter(20, 60),   # 20 order creations/min
    config.CASHFREE_WEBHOOK_PATH: RateLimiter(120, 60),  # webhook retries must never be dropped
    config.ACCESS_API_PATH: RateLimiter(240, 60),        # success page polls every 2s
}

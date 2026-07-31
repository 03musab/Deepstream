"""HTTP server for the Deepstream landing site and JSON endpoints."""

from __future__ import annotations

import http.server
import json
import re
import threading
import time
import urllib.parse
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from deepstream import config
from deepstream.chart_data import build_chart_data
from deepstream.logging_setup import setup_logging
from deepstream.payments import (
    create_cashfree_order,
    handle_webhook_request,
    payments_config,
    SubscriptionStore,
)
logger = setup_logging()

# ---------------------------------------------------------------------------
# Request guards (hardening)
# ---------------------------------------------------------------------------

# Cap request bodies so a hostile client cannot exhaust memory with a huge
# Content-Length (webhooks are small JSON documents).
MAX_BODY_BYTES = 1_048_576  # 1 MiB

# Emails/order ids are validated server-side (never trust the client alone).
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ORDER_ID_RE = re.compile(r"^ds_[0-9a-f]{16}$")

# Simple in-memory sliding-window rate limiter, keyed by client IP. This is a
# best-effort guard for the local dev backend; production should add an
# edge-level (CDN/WAF) rate limit in front of the Netlify Functions.
class _RateLimiter:
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
    config.CREATE_ORDER_API_PATH: _RateLimiter(20, 60),   # 20 order creations/min
    config.CASHFREE_WEBHOOK_PATH: _RateLimiter(120, 60),  # webhook retries must never be dropped
    config.ACCESS_API_PATH: _RateLimiter(240, 60),        # success page polls every 2s
}


class DeepstreamHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the landing site and the machine-readable signal endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(config.BASE_DIR / "signal_site"), **kwargs)

    # -- hardened plumbing --------------------------------------------------

    def end_headers(self) -> None:
        # Security headers on every response (static pages + JSON endpoints).
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def _allowed_origin(self) -> str:
        """The origin we are willing to share data with, if any.

        Defaults to the configured landing-site origin (``CASHFREE_SITE_URL``).
        When empty (no site configured) cross-origin reads are refused.
        """
        import os
        site = os.environ.get(config.CASHFREE_SITE_URL_ENV, "").strip().rstrip("/")
        if not site:
            return ""
        try:
            parts = urllib.parse.urlparse(site)
            return f"{parts.scheme}://{parts.netloc}".lower()
        except ValueError:
            return ""

    def _apply_cors(self) -> None:
        """Echo ``Access-Control-Allow-Origin`` only for the trusted origin."""
        request_origin = self.headers.get("Origin", "")
        allowed = self._allowed_origin()
        if request_origin and allowed and request_origin.strip().lower() == allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
        # No Origin header → same-origin/non-browser request → CORS not required.

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def _rate_limited(self, path: str) -> bool:
        limiter = RATE_LIMITS.get(path)
        return bool(limiter and not limiter.allow(f"{path}:{self._client_ip()}"))

    def _read_body(self) -> Optional[bytes]:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or 0)
        except (TypeError, ValueError):
            length = 0
        if length > MAX_BODY_BYTES:
            return None
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        if self.path == "/latest_signal.json":
            self._serve_json(config.SITE_SIGNAL_FILE)
            return
        if self.path == "/track_record.json":
            self._serve_json(config.SITE_TRACK_FILE)
            return
        if self.path == "/chart_data.json":
            self._serve_json_obj(build_chart_data())
            return
        if self.path.startswith(config.ACCESS_API_PATH):
            self._serve_access_lookup(self.path)
            return
        if self.path == config.PAYMENTS_CONFIG_API_PATH:
            self._serve_json_obj(payments_config())
            return
        super().do_GET()

    def do_POST(self):
        if self.path == config.CASHFREE_WEBHOOK_PATH:
            self._serve_cashfree_webhook()
            return
        if self.path == config.CREATE_ORDER_API_PATH:
            self._serve_create_order()
            return
        self.send_error(404)

    def _serve_cashfree_webhook(self):
        if self._rate_limited(config.CASHFREE_WEBHOOK_PATH):
            self._serve_json_obj({"error": "too many requests"}, status=429)
            return
        raw = self._read_body()
        if raw is None:
            self._serve_json_obj({"error": "body too large"}, status=413)
            return
        status, body = handle_webhook_request(raw, dict(self.headers))
        self._serve_json_obj(body, status=status)

    def _serve_create_order(self):
        if self._rate_limited(config.CREATE_ORDER_API_PATH):
            self._serve_json_obj({"error": "too many requests"}, status=429)
            return
        raw = self._read_body()
        if raw is None:
            self._serve_json_obj({"error": "body too large"}, status=413)
            return
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, ValueError):
            self._serve_json_obj({"error": "invalid body"}, status=400)
            return
        customer_email = (payload.get("customer_email") or "").strip()
        customer_phone = (payload.get("customer_phone") or "").strip()
        if not customer_email or len(customer_email) > 254 or not EMAIL_RE.match(customer_email):
            self._serve_json_obj({"error": "customer_email required"}, status=400)
            return
        if len(customer_phone) > 20:
            self._serve_json_obj({"error": "customer_phone invalid"}, status=400)
            return
        try:
            order = create_cashfree_order(customer_email, customer_phone)
        except Exception:
            logger.exception("Failed to create Cashfree order")
            self._serve_json_obj({"error": "order creation failed"}, status=502)
            return
        self._serve_json_obj(order)

    def _serve_access_lookup(self, path: str):
        if self._rate_limited(config.ACCESS_API_PATH):
            self._serve_json_obj({"error": "too many requests"}, status=429)
            return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        order_id = (query.get("order_id") or [""])[0].strip()
        if not order_id or len(order_id) > 64 or not ORDER_ID_RE.match(order_id):
            self._serve_json_obj({"error": "order_id invalid"}, status=400)
            return
        self._serve_json_obj(SubscriptionStore().access_for_order(order_id))

    def _serve_json(self, path: Path):
        if not path.exists():
            self.send_response(404)
            self._apply_cors()
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
            return
        payload = json.loads(path.read_text())
        self._serve_json_obj(payload)

    def _serve_json_obj(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._apply_cors()
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = http.server.ThreadingHTTPServer((host, port), DeepstreamHandler)
    logger.info("Deepstream site serving on http://localhost:%s", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped.")


if __name__ == "__main__":
    serve()

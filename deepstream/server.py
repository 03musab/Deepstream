"""HTTP server for the Deepstream landing site and JSON endpoints."""

from __future__ import annotations

import http.server
import json
import os
import urllib.parse
from pathlib import Path
from typing import Optional

from deepstream import config
from deepstream.chart_data import build_chart_data
from deepstream.logging_setup import setup_logging
from deepstream.middleware import MAX_BODY_BYTES, RATE_LIMITS, SECURITY_HEADERS
from deepstream.payments import (
    CashfreeError,
    create_cashfree_order,
    handle_webhook_request,
    payments_config,
    SubscriptionStore,
)
from deepstream.validation import (
    normalize_phone,
    valid_email,
    valid_order_id,
    valid_phone_digits,
)
logger = setup_logging()


class DeepstreamHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the landing site and the machine-readable signal endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(config.BASE_DIR / "signal_site"), **kwargs)

    # -- hardened plumbing --------------------------------------------------

    def end_headers(self) -> None:
        # Security headers on every response (static pages + JSON endpoints).
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def _allowed_origin(self) -> str:
        """The origin we are willing to share data with, if any.

        Defaults to the configured landing-site origin (``CASHFREE_SITE_URL``).
        When empty (no site configured) cross-origin reads are refused.
        """
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
        customer_phone = normalize_phone(payload.get("customer_phone") or "")
        if not valid_email(customer_email):
            self._serve_json_obj({"error": "customer_email required"}, status=400)
            return
        if not valid_phone_digits(customer_phone):
            self._serve_json_obj(
                {"error": "customer_phone required (10-15 digits)"}, status=400
            )
            return
        try:
            order = create_cashfree_order(customer_email, customer_phone)
        except CashfreeError as exc:
            # Provider rejected the order — surface the real reason (e.g. the
            # merchant sandbox account rejecting order creation) so operators
            # can diagnose it from the browser/console instead of a bare 502.
            logger.exception("Failed to create Cashfree order")
            self._serve_json_obj(
                {"error": "order creation failed", "detail": str(exc)},
                status=502,
            )
            return
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
        if not valid_order_id(order_id):
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

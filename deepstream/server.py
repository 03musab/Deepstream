"""HTTP server for the Deepstream landing site and JSON endpoints."""

from __future__ import annotations

import http.server
import json
import urllib.parse
from pathlib import Path

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


class DeepstreamHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the landing site and the machine-readable signal endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(config.BASE_DIR / "signal_site"), **kwargs)

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

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _serve_cashfree_webhook(self):
        raw = self._read_body()
        status, body = handle_webhook_request(raw, dict(self.headers))
        self._serve_json_obj(body, status=status)

    def _serve_create_order(self):
        raw = self._read_body()
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, ValueError):
            self._serve_json_obj({"error": "invalid body"}, status=400)
            return
        customer_email = (payload.get("customer_email") or "").strip()
        customer_phone = (payload.get("customer_phone") or "").strip()
        if not customer_email:
            self._serve_json_obj({"error": "customer_email required"}, status=400)
            return
        try:
            order = create_cashfree_order(customer_email, customer_phone)
        except Exception:
            logger.exception("Failed to create Cashfree order")
            self._serve_json_obj({"error": "order creation failed"}, status=502)
            return
        self._serve_json_obj(order)

    def _serve_access_lookup(self, path: str):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        order_id = (query.get("order_id") or [""])[0]
        if not order_id:
            self._serve_json_obj({"error": "order_id required"}, status=400)
            return
        self._serve_json_obj(SubscriptionStore().access_for_order(order_id))

    def _serve_json(self, path: Path):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
            return
        payload = json.loads(path.read_text())
        self._serve_json_obj(payload)

    def _serve_json_obj(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
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

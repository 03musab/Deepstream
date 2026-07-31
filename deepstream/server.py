"""HTTP server for the Deepstream landing site and JSON endpoints."""

from __future__ import annotations

import http.server
import json
import os
import urllib.parse
from pathlib import Path

from deepstream import config
from deepstream.chart_data import build_chart_data
from deepstream.logging_setup import setup_logging
from deepstream.payments import handle_webhook_request, SubscriptionStore
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
        if self.path == config.GUMROAD_CONFIG_API_PATH:
            self._serve_gumroad_config()
            return
        super().do_GET()

    def do_POST(self):
        if self.path == config.GUMROAD_WEBHOOK_PATH:
            self._serve_gumroad_webhook()
            return
        self.send_error(404)

    def _serve_gumroad_webhook(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        status, body = handle_webhook_request(raw, self.headers.get("Content-Type", ""))
        self._serve_json_obj(body, status=status)

    def _serve_access_lookup(self, path: str):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        sale_id = (query.get("sale_id") or [""])[0]
        if not sale_id:
            self._serve_json_obj({"error": "sale_id required"}, status=400)
            return
        self._serve_json_obj(SubscriptionStore().access_for_sale(sale_id))

    def _serve_gumroad_config(self):
        checkout_url = os.environ.get(config.GUMROAD_CHECKOUT_URL_ENV, "")
        if not checkout_url:
            self._serve_json_obj({"configured": False}, status=503)
            return
        self._serve_json_obj({
            "configured": True,
            "checkout_url": checkout_url,
        })

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

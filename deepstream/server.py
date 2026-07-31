"""HTTP server for the Deepstream landing site and JSON endpoints."""

from __future__ import annotations

import http.server
import json
from pathlib import Path

from deepstream import config
from deepstream.chart_data import build_chart_data
from deepstream.logging_setup import setup_logging

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
        super().do_GET()

    def _serve_json(self, path: Path):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
            return
        payload = json.loads(path.read_text())
        self._serve_json_obj(payload)

    def _serve_json_obj(self, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(200)
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

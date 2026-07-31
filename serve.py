import http.server
import json
import os
import shutil

SIGNAL_SITE = "signal_site"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SIGNAL_SITE, **kwargs)

    def do_GET(self):
        if self.path == "/latest_signal.json":
            src = "latest_signal.json"
            if os.path.exists(src):
                with open(src) as f:
                    data = json.load(f)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
                return
            self.send_response(404)
            self.end_headers()
            return
        super().do_GET()

if __name__ == "__main__":
    port = 8080
    server = http.server.HTTPServer(("0.0.0.0", port), Handler)
    print(f"Deepstream site running at http://localhost:{port}")
    server.serve_forever()

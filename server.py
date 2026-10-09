"""Routine Radar dev server: stdlib only, binds 127.0.0.1:4272. Serves web/ and /dist/."""
import http.server
import json
import os
import socketserver

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("RR_PORT", os.environ.get("PORT", 4272)))


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(HERE, "web"), **k)

    def do_GET(self):
        if self.path.split("?")[0] in ("/health", "/healthz"):
            body = json.dumps({"ok": True, "app": "routine-radar", "port": PORT}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def translate_path(self, path):
        p = path.split("?")[0]
        if p.startswith("/dist/"):
            return os.path.join(HERE, "dist", os.path.basename(p))
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Routine Radar on http://127.0.0.1:{PORT}/  (offline: /dist/routine-radar.html)", flush=True)
    S(("127.0.0.1", PORT), H).serve_forever()

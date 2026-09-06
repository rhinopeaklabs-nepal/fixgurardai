"""Static server for the FixGuard testbed, with a POST /submit that works.

    python testbed/server.py            # http://127.0.0.1:8080
"""
from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def do_GET(self):  # noqa: N802 - stdlib naming
        # Simulates a region block, for the reachability check (T-07).
        if self.path.startswith("/blocked"):
            body = b"Access denied from your region."
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802 - stdlib naming
        if self.path != "/submit":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        print(f"[testbed] received submission: {body[:300]}")
        payload = json.dumps({"ok": True, "received": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[testbed] {fmt % args}")


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"[testbed] serving {ROOT} on http://127.0.0.1:{PORT}")
        print("[testbed]   /           silent-failure form + console errors")
        print("[testbed]   /good.html  working form (control case)")
        print("[testbed]   /loop.html  navigation loop")
        httpd.serve_forever()

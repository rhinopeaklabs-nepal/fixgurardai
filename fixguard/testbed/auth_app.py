"""A tiny site with a login, for testing authenticated audits.

    python testbed/auth_app.py        # http://127.0.0.1:8081

Sign in at /login with demo / demo to get a session cookie, or just request
/session to be handed one. Everything under /app requires it.

It deliberately includes the two links an authenticated crawler must refuse to
follow: a logout, and a delete that works over GET.
"""
from __future__ import annotations

import http.server
import socketserver
import urllib.parse
from http import cookies

PORT = 8081
SESSION = "fixguard-demo-session"
VALID = "valid-session-token"

# Mutable so a wrongly-followed delete link is actually observable.
INVOICES = {"1": "Acme Ltd - $400", "2": "Globex - $1,250", "3": "Initech - $90"}

NAV = """
<nav>
  <a href="/app">Dashboard</a>
  <a href="/app/invoices">Invoices</a>
  <a href="/app/settings">Settings</a>
  <a href="/app/team">Team</a>
  <a href="/logout">Sign out</a>
</nav>
"""

STYLE = """
<style>
 body{font-family:system-ui,sans-serif;max-width:680px;margin:0 auto;padding:2rem;color:#111}
 nav a{margin-right:1rem}
 .card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}
 label{display:block;font-size:.85rem;font-weight:600;margin:.6rem 0 .2rem}
 input{width:100%;padding:.5rem;box-sizing:border-box}
 button{margin-top:.8rem;background:#0055FF;color:#fff;border:0;padding:.6rem 1.2rem;
        border-radius:6px;font-weight:600;cursor:pointer}
 .danger{color:#b00}
</style>
"""


def page(title: str, body: str, signed_in: bool = True) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{STYLE}</head><body>
{NAV if signed_in else ''}
{body}
</body></html>""".encode()


class Handler(http.server.BaseHTTPRequestHandler):
    # ---------------------------------------------------------------- utils
    def _send(self, body: bytes, status: int = 200, extra: list[tuple] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra or []:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to: str, extra: list[tuple] | None = None):
        self.send_response(302)
        self.send_header("Location", to)
        for k, v in extra or []:
            self.send_header(k, v)
        self.end_headers()

    def _signed_in(self) -> bool:
        raw = self.headers.get("Cookie")
        if not raw:
            return False
        jar = cookies.SimpleCookie()
        jar.load(raw)
        return SESSION in jar and jar[SESSION].value == VALID

    # ----------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        path = url.path.rstrip("/") or "/"

        if path == "/":
            return self._send(page(
                "Demo App",
                "<h1>Demo App</h1><p>Everything useful is behind the login.</p>"
                '<p><a href="/login">Sign in</a></p>',
                signed_in=False,
            ))

        if path == "/login":
            return self._send(page(
                "Sign in",
                """<h1>Sign in</h1>
                <form method="post" action="/login" class="card">
                  <label for="u">Username</label><input id="u" name="username">
                  <label for="p">Password</label><input id="p" name="password" type="password">
                  <button type="submit">Sign in</button>
                </form>
                <p style="font-size:.85rem;color:#666">demo / demo</p>""",
                signed_in=False,
            ))

        # Convenience: hands out a session without a form, so a tester can grab
        # the cookie without typing a password anywhere.
        if path == "/session":
            return self._redirect("/app", [
                ("Set-Cookie", f"{SESSION}={VALID}; Path=/; SameSite=Lax"),
            ])

        if path == "/logout":
            return self._redirect("/", [
                ("Set-Cookie", f"{SESSION}=; Path=/; Max-Age=0"),
            ])

        # ---- everything below needs a session --------------------------
        if path.startswith("/app"):
            if not self._signed_in():
                return self._redirect("/login")

            if path == "/app":
                return self._send(page("Dashboard", """
                    <h1>Dashboard</h1>
                    <p>Signed in as <strong>demo@example.com</strong></p>
                    <div class="card"><h3>This month</h3><p>3 open invoices.</p></div>"""))

            if path == "/app/invoices":
                rows = "".join(
                    f'<li>{v} &mdash; <a class="danger" href="/app/invoices/{k}/delete">'
                    f"Delete</a></li>"
                    for k, v in INVOICES.items()
                )
                return self._send(page("Invoices", f"""
                    <h1>Invoices</h1>
                    <ul>{rows or '<li>All invoices were deleted.</li>'}</ul>
                    <p style="font-size:.85rem;color:#666">
                      Those delete links are plain GET requests. A crawler that
                      follows them destroys the data.</p>"""))

            if path.startswith("/app/invoices/") and path.endswith("/delete"):
                inv = path.split("/")[3]
                INVOICES.pop(inv, None)
                return self._send(page("Deleted", f"""
                    <h1 class="danger">Invoice {inv} deleted</h1>
                    <p>If FixGuard reached this page, the crawl guard failed.</p>"""))

            if path == "/app/settings":
                # A form behind a login that changes state rather than sending
                # a message - exactly why submitting is opt-in.
                return self._send(page("Settings", """
                    <h1>Settings</h1>
                    <form method="post" action="/app/settings" class="card">
                      <h3>Company name</h3>
                      <label for="n">Name</label><input id="n" name="company" value="Acme Ltd">
                      <button type="submit">Save changes</button>
                    </form>"""))

            if path == "/app/team":
                return self._send(page("Team", """
                    <h1>Team</h1>
                    <ul><li>demo@example.com (owner)</li><li>sam@example.com</li></ul>
                    <p><img src="/avatar-missing.png" width="40" height="40"></p>"""))

            return self._send(page("Not found", "<h1>404</h1>"), 404)

        return self._send(page("Not found", "<h1>404</h1>", signed_in=False), 404)

    # ---------------------------------------------------------------- POST
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        url = urllib.parse.urlparse(self.path)

        if url.path == "/login":
            return self._redirect("/app", [
                ("Set-Cookie", f"{SESSION}={VALID}; Path=/; SameSite=Lax"),
            ])
        if url.path == "/app/settings":
            return self._send(page("Saved", "<h1>Settings saved</h1>"))
        return self._send(page("Not found", "<h1>404</h1>"), 404)

    def log_message(self, fmt, *args):
        print(f"[auth-app] {fmt % args}")


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"[auth-app] http://127.0.0.1:{PORT}")
        print(f"[auth-app]   /session  -> hands you {SESSION}={VALID}")
        print("[auth-app]   /app/*    -> requires it")
        httpd.serve_forever()

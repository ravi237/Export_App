#!/usr/bin/env python3
"""
Local server for the India-UK Export Duty Finder.

Serves the app's static files (index.html, config.js) AND proxies calls to
the authenticated UK Trade Tariff API, holding your client_secret here on
this machine only — it is never sent to the browser.

Usage:
    python3 server.py

Then open:
    http://localhost:8934/index.html
"""
import http.server
import json
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from proxy_secrets import CLIENT_ID, CLIENT_SECRET
except ImportError:
    CLIENT_ID = ""
    CLIENT_SECRET = ""

PORT = 8934
TOKEN_URL = "https://auth.id.trade-tariff.service.gov.uk/oauth2/token"
API_BASE = "https://api.trade-tariff.service.gov.uk/uk/api"
ACCEPT = "application/vnd.hmrc.2.0+json"

_token_cache = {"token": None, "expires_at": 0}


def get_token():
    if _token_cache["token"] and _token_cache["expires_at"] > time.time():
        return _token_cache["token"]
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read())
    _token_cache["token"] = payload["access_token"]
    _token_cache["expires_at"] = time.time() + payload.get("expires_in", 3600) - 60
    return _token_cache["token"]


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/proxy/commodities/"):
            code = self.path.rsplit("/", 1)[-1]
            self.handle_commodity(code)
        else:
            super().do_GET()

    def handle_commodity(self, code):
        if not CLIENT_ID or not CLIENT_SECRET:
            self.send_json_error(500, "Proxy has no credentials configured — see proxy_secrets.py")
            return
        try:
            token = get_token()
            req = urllib.request.Request(
                f"{API_BASE}/commodities/{code}",
                headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            self.send_json_error(e.code, e.read().decode(errors="replace"))
        except Exception as e:
            self.send_json_error(502, str(e))

    def send_json_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def log_message(self, fmt, *args):
        pass  # quiet by default; comment out to see request logs


if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Note: no credentials in proxy_secrets.py — the app will still work,")
        print("      just via the public API instead of the authenticated one.\n")
    print(f"Serving the app at: http://localhost:{PORT}/index.html")
    print("Press Ctrl+C to stop.\n")
    http.server.HTTPServer(("localhost", PORT), Handler).serve_forever()

"""
Vercel serverless function: proxies authenticated UK Trade Tariff API calls.

Route: /api/commodity?code=<10-digit CTH>

Credentials are read from Vercel environment variables (set in the project
dashboard, never committed to git) — this file never sees them in plaintext
in the repo, and the browser never sees them at all.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

CLIENT_ID = os.environ.get("TRADE_TARIFF_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("TRADE_TARIFF_CLIENT_SECRET", "")

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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = (query.get("code") or [""])[0]
        if not code:
            self.send_json_error(400, "Missing ?code= parameter")
            return
        if not CLIENT_ID or not CLIENT_SECRET:
            self.send_json_error(500, "Proxy has no credentials configured — set TRADE_TARIFF_CLIENT_ID / TRADE_TARIFF_CLIENT_SECRET in Vercel project settings")
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

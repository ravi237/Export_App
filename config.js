// Points the app at the local proxy (server.py) for the authenticated,
// higher-rate-limit Trade Tariff API. No secret lives here — the proxy holds
// your client_id/client_secret server-side (see proxy_secrets.py) and this
// file just tells the page where to find it.
//
// - Running the app via `python3 server.py`: leave this as "/proxy" (same-origin).
// - Opening index.html directly as a file (no proxy running): this URL simply
//   won't resolve, and the app quietly falls back to the public API — no need
//   to change anything.

window.TRADE_TARIFF_PROXY_URL = "/proxy";

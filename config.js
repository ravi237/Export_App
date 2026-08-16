// Points the app at the authenticated-API proxy (api/commodity.py), deployed
// as a Vercel serverless function alongside this page. No secret lives here —
// the proxy reads your client_id/client_secret from Vercel environment
// variables (set in the project dashboard, never committed to git).
//
// Same-origin on Vercel, so this relative path just works. If this endpoint
// isn't deployed or isn't reachable, the app quietly falls back to the
// public (unauthenticated) API — no need to change anything.

window.TRADE_TARIFF_PROXY_URL = "/api/commodity";

// UK trade-value data (world vs India import value) — HMRC's free public
// Overseas Trade Statistics API, proxied the same way since it also has no
// direct-browser (CORS) access. No credentials needed for this one.
window.TRADE_VALUE_URL = "/api/tradevalue";

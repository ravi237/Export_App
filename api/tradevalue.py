"""
Vercel serverless function: UK import value (world vs India) for a commodity,
for the last complete calendar year, sourced from HMRC's free public
Overseas Trade Statistics API (api.uktradeinfo.com) — no credentials needed.

Route: /api/tradevalue?code=<CTH or CN8 code>

That API classifies commodities by 8-digit CN code, one level coarser than
the 10-digit UK tariff codes used elsewhere in this app, so only the first
8 digits of the given code are used — several named 10-digit sub-varieties
of the same CTH can share one trade-value figure.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

OTS_BASE = "https://api.uktradeinfo.com"
INDIA_COUNTRY_ID = 664
IMPORT_FLOW_TYPES = (1, 3)  # EU Imports, Non-EU Imports — together, imports from the world
TOP_N = 3

_year_cache = {"year": None, "checked_at": 0}
_country_cache = {"map": None, "checked_at": 0}


def api_get(path):
    # Human-readable OData paths (with literal spaces) go in; this is the one place
    # that encodes them, preserving the OData syntax characters ($ ? ( ) = , &).
    url = OTS_BASE + urllib.parse.quote(path, safe="/?$()=,&")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def last_complete_calendar_year():
    if _year_cache["year"] and time.time() - _year_cache["checked_at"] < 3600:
        return _year_cache["year"]
    data = api_get("/OTS?$apply=aggregate(MonthId with max as LatestMonth)")
    latest = data["value"][0]["LatestMonth"]
    year, month = latest // 100, latest % 100
    complete_year = year if month == 12 else year - 1
    _year_cache["year"] = complete_year
    _year_cache["checked_at"] = time.time()
    return complete_year


def country_name_map():
    # Static reference data (263 countries) — cache for the life of the warm instance.
    if _country_cache["map"] is not None and time.time() - _country_cache["checked_at"] < 86400:
        return _country_cache["map"]
    data = api_get("/Country")
    m = {c["CountryId"]: (c.get("CountryName") or "").strip() for c in data.get("value", [])}
    _country_cache["map"] = m
    _country_cache["checked_at"] = time.time()
    return m


def country_breakdown(cn8, year):
    # One grouped query gives every country's import value for this commodity+year —
    # world total, India's figure, and the top suppliers all derive from this single result.
    flow_filter = " or ".join(f"FlowTypeId eq {f}" for f in IMPORT_FLOW_TYPES)
    filter_expr = f"CommodityId eq {cn8} and MonthId ge {year}01 and MonthId le {year}12 and ({flow_filter})"
    query = f"/OTS?$apply=filter({filter_expr})/groupby((CountryId),aggregate(Value with sum as Total))"
    data = api_get(query)
    return [(r["CountryId"], r.get("Total") or 0.0) for r in data.get("value", [])]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = (query.get("code") or [""])[0]
        if not code:
            self.send_json_error(400, "Missing ?code= parameter")
            return
        cn8 = code[:8]
        try:
            year = last_complete_calendar_year()
            rows = country_breakdown(cn8, year)
            world = sum(v for _, v in rows)
            india = next((v for cid, v in rows if cid == INDIA_COUNTRY_ID), 0.0)

            names = country_name_map()
            top_rows = sorted(rows, key=lambda r: -r[1])[:TOP_N]
            top_countries = [
                {
                    "name": names.get(cid, f"Country {cid}"),
                    "value": value,
                    "sharePct": (value / world * 100) if world else None,
                }
                for cid, value in top_rows if value > 0
            ]

            result = {
                "cn8": cn8,
                "year": year,
                "worldValue": world,
                "indiaValue": india,
                "indiaSharePct": (india / world * 100) if world else None,
                "topCountries": top_countries,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except urllib.error.HTTPError as e:
            self.send_json_error(e.code, e.read().decode(errors="replace"))
        except Exception as e:
            self.send_json_error(502, str(e))

    def send_json_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

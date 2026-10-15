"""Small sequential, read-only survey. Python 3.14; stdlib only.

No bookings, paid providers, redirects, retries, or website scraping.
Only these fixed public API hosts and explicitly enabled free Geoapify are used.
"""
from __future__ import annotations

import argparse
import hashlib
from http.client import HTTPException
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = {"apikey", "api_key", "key", "token", "access_token", "authorization",
                "client_secret", "client_id", "username", "password", "x-api-key"}
FIELDS = ("external_id", "name", "category", "latitude", "longitude", "address",
          "description", "website_url", "image_url", "rating", "price_amount",
          "price_currency", "price_period_or_total", "availability", "country_code",
          "timezone", "cuisine", "opening_hours", "entrance_fee")
ALLOWED_HOSTS = {"geocoding-api.open-meteo.com", "overpass-api.de", "api.geoapify.com",
                 "secure.geonames.org", "api.frankfurter.dev", "www.six-group.com", "raw.githubusercontent.com", "api.opentripmap.com"}
OSM_TAGS = {"name", "name:en", "name:fr", "tourism", "historic", "leisure", "amenity",
            "natural", "cuisine", "opening_hours", "fee", "charge", "website",
            "contact:website", "image", "wikimedia_commons", "wikidata", "wikipedia",
            "description", "addr:street", "addr:housenumber", "addr:city", "addr:postcode"}
DOC_ONLY = {
    "amadeus": "Official portal confirms Self-Service decommissioned July 17, 2026; Enterprise only. No token request.",
    "foursquare": "New API and paid overage; documentation only, no confirmed free account quota.",
    "google": "Billing account and SKU-dependent charges; documentation only.",
    "tripadvisor": "Legacy Content API sunset; Terra has separate paid packages/rights. Documentation only.",
    "yelp": "Evaluation trial and storage restrictions; documentation only.",
    "booking": "Managed affiliate contract, token and affiliate ID required; documentation only.",
    "expedia": "Partner access and agreed terms required; documentation only.",
    "sherpa": "Sandbox requires partner key; schema/documentation only; no passport profile sent.",
    "visafar": "Manually issued key, current API price not confirmed; documentation only; no passport profile sent.",
    "timezonefinder": "Local polygon lookup assessed in documentation; not installed or benchmarked.",
    "government": "Official entry-information pages assessed manually; no website parsing or automated visa decision.",
}


def moscow_today() -> date:
    # No tzdata dependency needed on Windows; Moscow UTC+3 at survey date.
    return datetime.now(timezone(timedelta(hours=3))).date()


def stay_dates(today: date) -> dict:
    checkin = today + timedelta(days=30)
    return {"check_in": checkin.isoformat(), "check_out": (checkin + timedelta(days=2)).isoformat(),
            "adults": 2, "rooms": 1, "nights": 2}


def load_env(path: Path) -> None:
    """Simple KEY=value only, no shell execution or interpolation; OS env wins."""
    if not path.is_file():
        return
    permitted = {"GEOAPIFY_API_KEY", "GEOAPIFY_FREE_PLAN", "GEONAMES_USERNAME", "OPENTRIPMAP_API_KEY", "OPENTRIPMAP_FREE_PLAN"}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key in permitted:
            os.environ.setdefault(key, value.strip("\"'"))


def scrub(value, secrets=()):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in SECRET_NAMES else scrub(v, secrets)
                for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        # URL credentials and query parameters may occur inside arbitrary strings.
        value = re.sub(r"(?i)([?&](?:apikey|api_key|key|token|access_token|username)=)[^&#\s]+",
                       r"\1[REDACTED]", value)
        return value
    return value


def public_url(value):
    """Keep only public web links; remove query, fragment and userinfo."""
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value)
        if p.scheme not in {"https", "http"} or not p.hostname or p.username or p.password:
            return None
        return urlunsplit((p.scheme, p.netloc, p.path, "", ""))
    except ValueError:
        return None


def leaf_fields(obj, prefix=""):
    fields = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            fields.add(path)
            fields.update(leaf_fields(v, path))
    elif isinstance(obj, list):
        for v in obj[:20]:
            fields.update(leaf_fields(v, prefix + "[]"))
    return fields


def present(value):
    return value is not None and value != "" and value != [] and value != {}


def coverage(rows):
    return {field: {"filled": sum(present(row.get(field)) for row in rows), "total": len(rows)}
            for field in FIELDS}


def normalize_osm(item, category, retrieved):
    tags = item.get("tags", {})
    center = item.get("center", {})
    address = " ".join(tags[k] for k in ("addr:housenumber", "addr:street", "addr:postcode", "addr:city") if tags.get(k))
    row = dict.fromkeys(FIELDS)
    row.update(provider="overpass", external_id=f"{item.get('type')}/{item.get('id')}",
               name=tags.get("name"), category=category,
               latitude=item.get("lat", center.get("lat")), longitude=item.get("lon", center.get("lon")),
               address=address or None, description=tags.get("description"),
               website_url=public_url(tags.get("website") or tags.get("contact:website")),
               image_url=public_url(tags.get("image")), cuisine=tags.get("cuisine"),
               opening_hours=tags.get("opening_hours"), entrance_fee=tags.get("fee"),
               source_url=f"https://www.openstreetmap.org/{item.get('type')}/{item.get('id')}",
               retrieved_at=retrieved, raw_fields=sorted(leaf_fields(item)))
    # fee=yes / charge=... are unstructured facts, never a numeric ticket price.
    return row


def normalize_geoapify(item, category, retrieved):
    p = item.get("properties", {})
    datasource = p.get("datasource") or {}
    raw = datasource.get("raw") or {}
    row = dict.fromkeys(FIELDS)
    row.update(provider="geoapify", external_id=p.get("place_id"), name=p.get("name"), category=category,
               latitude=p.get("lat"), longitude=p.get("lon"), address=p.get("formatted"),
               country_code=p.get("country_code"), description=p.get("description") or raw.get("description"),
               website_url=public_url(p.get("website") or (p.get("contact") or {}).get("website") or raw.get("website")),
               image_url=public_url((p.get("wiki_and_media") or {}).get("image") or raw.get("image")), cuisine=raw.get("cuisine"),
               opening_hours=p.get("opening_hours") or raw.get("opening_hours"), entrance_fee=raw.get("fee"),
               timezone=(p.get("timezone") or {}).get("name"),
               source_provider="openstreetmap" if geoapify_osm_reference(item) else None,
               source_external_id=geoapify_osm_reference(item),
               source_url=public_url(datasource.get("url")),
               retrieved_at=retrieved, raw_fields=sorted(leaf_fields(item)))
    return row


def geoapify_osm_reference(item):
    """Public source identity can remain stable when opaque Geoapify lookup IDs differ."""
    raw = ((item.get("properties") or {}).get("datasource") or {}).get("raw") or {}
    kind = {"n": "node", "w": "way", "r": "relation", "node": "node", "way": "way", "relation": "relation"}.get(raw.get("osm_type"))
    identifier = raw.get("osm_id")
    if not kind or isinstance(identifier, bool) or not str(identifier).isdigit() or int(identifier) < 1:
        return None
    return f"{kind}/{identifier}"


def normalize_otm(item, category, retrieved):
    row = dict.fromkeys(FIELDS)
    point = item.get("point") or {}
    row.update(provider="opentripmap", external_id=item.get("xid"), name=item.get("name"), category=category,
               latitude=point.get("lat"), longitude=point.get("lon"), address=item.get("address"),
               description=(item.get("wikipedia_extracts") or {}).get("text"),
               website_url=public_url(item.get("url")), image_url=public_url((item.get("preview") or {}).get("source")),
               source_url=public_url(item.get("otm")), retrieved_at=retrieved,
               raw_fields=sorted(leaf_fields(item)))
    # OpenTripMap rate is tourism significance, not a user-review rating.
    return row


def normalize_geonames(item, category, retrieved):
    """Reference currency is separate from the currency of a priced offer."""
    tz = item.get("timezone") or {}
    row = dict.fromkeys(FIELDS)
    row.update(provider="geonames", external_id=item.get("geonameId"), category=category,
               name=item.get("name") or item.get("countryName"),
               latitude=float(item["lat"]) if item.get("lat") is not None else None,
               longitude=float(item["lng"]) if item.get("lng") is not None else None,
               country_code=item.get("countryCode"), currency_code=item.get("currencyCode"),
               timezone=item.get("timezoneId") or tz.get("timeZoneId"),
               source_url=f"https://www.geonames.org/{item['geonameId']}" if item.get("geonameId") else "https://www.geonames.org/",
               retrieved_at=retrieved, raw_fields=sorted(leaf_fields(item)))
    return row


def safe_sample(item, kind):
    """Allowlist values rather than persisting arbitrary POI contacts/personal data."""
    if kind == "osm":
        out = {k: item[k] for k in ("type", "id", "lat", "lon", "center") if k in item}
        out["tags"] = {k: (public_url(v) if k in {"website", "contact:website", "image"} else v)
                       for k, v in item.get("tags", {}).items() if k in OSM_TAGS}
        return out
    if kind == "geoapify":
        p = item.get("properties", {})
        keys = {"name", "place_id", "lat", "lon", "formatted", "categories", "country_code", "description", "opening_hours", "timezone"}
        out = {k: v for k, v in p.items() if k in keys}
        if "website" in p:
            out["website"] = public_url(p["website"])
        if isinstance(p.get("wiki_and_media"), dict):
            out["wiki_and_media"] = {k: public_url(v) if k == "image" else v for k, v in p["wiki_and_media"].items()
                                     if k in {"image", "wikidata", "wikipedia", "wikimedia_commons"}}
        out["datasource"] = {"raw": {k: (public_url(v) if k in {"website", "contact:website", "image"} else v)
                                     for k, v in ((p.get("datasource") or {}).get("raw") or {}).items() if k in OSM_TAGS | {"osm_id", "osm_type"}}}
        for key in ("attribution", "license", "sourcename"):
            if key in (p.get("datasource") or {}):
                out["datasource"][key] = p["datasource"][key]
        out["datasource"]["url"] = public_url((p.get("datasource") or {}).get("url"))
        return {"type": item.get("type"), "properties": out, "geometry": item.get("geometry")}
    if kind == "otm":
        return {k: v for k, v in item.items() if k in {"xid", "name", "kinds", "rate", "point", "dist", "osm", "wikidata", "wikipedia", "otm", "address", "wikipedia_extracts", "preview"}}
    if kind == "geonames":
        return {k: v for k, v in item.items() if k in {
            "geonameId", "name", "toponymName", "asciiName", "lat", "lng", "countryCode", "countryName",
            "currencyCode", "timezone", "timezoneId", "fcode", "fcl", "population", "adminName1", "adminName2"}}
    return item


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, timeout=20.0, delay=2.0):
        self.timeout, self.delay, self.last_end = timeout, delay, 0.0
        self.opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        self.blocked = set()

    def get(self, provider, endpoint, params):
        if urlsplit(endpoint).hostname not in ALLOWED_HOSTS or urlsplit(endpoint).scheme != "https":
            raise ValueError("Endpoint outside fixed HTTPS allowlist")
        if provider in self.blocked:
            return {"status": "skipped", "reason": "Provider circuit open after HTTP 401/403/429", "http_status": None, "duration_ms": None}, None
        time.sleep(max(0.0, self.delay - (time.monotonic() - self.last_end)))
        start = time.perf_counter()
        meta = {"status": "network_error", "http_status": None, "duration_ms": None}
        try:
            url = endpoint + ("?" + urlencode(params) if params else "")
            req = Request(url, headers={"User-Agent": "TripFlow-Academic-Survey/1.0 (small sequential read-only experiment)",
                                        "Accept": "application/json, application/xml;q=0.8"})
            with self.opener.open(req, timeout=self.timeout) as response:
                meta["http_status"] = response.status
                meta["content_type"] = response.headers.get("Content-Type")
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    meta.update(status="response_too_large", reason="2 MB response limit")
                    return meta, None
                if not body.strip():
                    meta.update(status="empty", reason="Empty HTTP body")
                    return meta, None
                meta["response_sha256"] = hashlib.sha256(body).hexdigest()
                if "xml" in (meta["content_type"] or "") or body.lstrip().startswith(b"<?xml"):
                    parsed = ET.fromstring(body)
                else:
                    parsed = json.loads(body)
                meta["status"] = "ok"
                return meta, parsed
        except HTTPError as exc:
            meta.update(status="http_error", http_status=exc.code,
                        reason={401: "Unauthorized", 403: "Forbidden", 404: "Not found",
                                429: "Rate limited; no automatic retry"}.get(exc.code, "HTTP error; no retry"))
            if exc.code in {401, 403, 429}:
                self.blocked.add(provider)
            exc.close()
            return meta, None
        except (ValueError, ET.ParseError, UnicodeError):
            meta.update(status="invalid_response", reason="Response is not valid JSON/XML; no body persisted")
            return meta, None
        except (URLError, TimeoutError, OSError, socket.timeout, HTTPException) as exc:
            # Do not log arbitrary exception strings containing request URLs/keys.
            reason = getattr(exc, "reason", exc)
            meta.update(reason=type(reason).__name__)
            return meta, None
        finally:
            meta["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
            self.last_end = time.monotonic()


class Survey:
    def __init__(self, args):
        self.args = args
        self.client = Client(args.timeout, args.delay)
        self.results = []
        self.secrets = [os.getenv(k, "") for k in ("GEOAPIFY_API_KEY", "GEONAMES_USERNAME", "OPENTRIPMAP_API_KEY")]
        self.now = datetime.now(timezone.utc).isoformat()
        self.received_at = self.now
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.context = {"city": "Paris", "country": "France", "country_code": "FR",
                        "run_date_moscow": moscow_today().isoformat(), "stay": stay_dates(moscow_today()),
                        "radius_metres": getattr(args, "radius", 3000),
                        "coordinates": None, "coordinate_source": None}

    def skip(self, provider, name, reason, endpoint=None, params=None):
        self.results.append(dict(provider=provider, name=name, endpoint=endpoint, params=params or {},
                                 status="skipped", reason=reason, http_status=None, duration_ms=None,
                                 count=None, actual_fields=[], coverage={}, evidence="not_called"))
        print(f"{provider:14} {name:18} skipped: {reason}")

    def call(self, provider, name, endpoint, params, selector, normalizer=None, kind=None, gate=None):
        if self.args.offline or (self.args.providers and provider not in self.args.providers):
            self.skip(provider, name, "Offline or not selected", endpoint, params)
            return []
        if gate:
            self.skip(provider, name, gate, endpoint, params)
            return []
        meta, payload = self.client.get(provider, endpoint, params)
        self.received_at = datetime.now(timezone.utc).isoformat()
        result = dict(provider=provider, name=name, endpoint=endpoint, params=scrub(params, self.secrets),
                      **meta, count=None, actual_fields=[], coverage={}, evidence=("not_called" if meta["status"] == "skipped" else
                          "live_http" if meta["http_status"] is not None else "network_attempt"))
        result["retrieved_at_utc"] = self.received_at
        rows, normalized = [], []
        if payload is not None:
            try:
                # HTTP 200 can still carry provider errors (including Overpass partial results).
                if isinstance(payload, dict) and (payload.get("error") or payload.get("status") or payload.get("remark")):
                    result.update(status="provider_error", reason="Provider-level error/remark in HTTP body; partial data excluded")
                else:
                    rows = selector(payload)
                    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                        raise ValueError("Expected list of objects")
                    result.update(count=len(rows), status="ok" if rows else "empty",
                                  actual_fields=sorted(set().union(*(leaf_fields(r) for r in rows))))
                    if normalizer:
                        normalized = [normalizer(r) for r in rows]
                    result["coverage"] = coverage(normalized)
                    result["sample"] = {"evidence": "live_response", "retrieved_at": self.received_at,
                                        "selection": "First two results; values allowlisted; URLs cleaned",
                                        "raw": [safe_sample(r, kind) for r in rows[:2]],
                                        "normalized": normalized[:2]}
                    if isinstance(payload, dict) and "osm3s" in payload:
                        result["source_metadata"] = payload["osm3s"]
            except (KeyError, TypeError, ValueError, AttributeError):
                result.update(status="schema_error", reason="Unexpected provider schema; no raw body persisted", count=None)
                rows = []
        self.results.append(result)
        print(f"{provider:14} {name:18} {result['status']:18} HTTP={result['http_status']} n={result['count']} {result['duration_ms']}ms")
        return rows

    def run(self):
        city = self.call("open_meteo", "city_search", "https://geocoding-api.open-meteo.com/v1/search",
                         {"name": "Paris", "countryCode": "FR", "language": "en", "count": 10},
                         lambda d: d["results"] if "results" in d else [],
                         lambda r: {**dict.fromkeys(FIELDS), **{k: r.get(k) for k in ("name", "latitude", "longitude", "country_code", "timezone")},
                                    "provider": "open_meteo", "external_id": r.get("id"), "category": "city", "retrieved_at": self.received_at,
                                    "source_url": "https://open-meteo.com/en/docs/geocoding-api", "raw_fields": sorted(leaf_fields(r))})
        chosen = next((r for r in city if r.get("country_code") == "FR" and r.get("feature_code") == "PPLC" and r.get("name") == "Paris"), None)
        if chosen:
            lat, lon = chosen["latitude"], chosen["longitude"]
            self.context.update(coordinates={"latitude": lat, "longitude": lon}, coordinate_source="open_meteo/city_search id=" + str(chosen["id"]))
        else:
            lat, lon = None, None
        filters = {
            "museums": '["tourism"="museum"]',
            "historic": '["historic"]',
            "nature": '["leisure"="park"];nwr{area}["tourism"="viewpoint"];nwr{area}["natural"="wood"]',
            "restaurants": '["amenity"~"^(restaurant|cafe)$"]',
            "hotels": '["tourism"~"^(hotel|hostel|guest_house)$"]',
        }
        categories = {"museums": "entertainment.museum", "historic": "tourism.sights",
                      "nature": "leisure.park,natural,tourism.attraction.viewpoint",
                      "restaurants": "catering.restaurant,catering.cafe", "hotels": "accommodation.hotel,accommodation.hostel,accommodation.guest_house"}
        for category, tag_filter in filters.items():
            if category not in getattr(self.args, "categories", filters):
                continue
            radius = getattr(self.args, "radius", 3000)
            area = f"(around:{radius},{lat},{lon})" if chosen else f"(around:{radius},<latitude>,<longitude>)"
            clause = tag_filter.replace("{area}", area)
            query = f"[out:json][timeout:15];(nwr{area}{clause};);out center {self.args.limit};"
            self.call("overpass", category, "https://overpass-api.de/api/interpreter", {"data": query},
                      lambda d: d["elements"], lambda r, c=category: normalize_osm(r, c, self.received_at), "osm",
                      gate=None if chosen else "No verified Paris coordinates; dependent query skipped")
        geo_key = None if self.args.no_keys else os.getenv("GEOAPIFY_API_KEY")
        geo_gate = ("Missing GEOAPIFY_API_KEY" if not geo_key else
                    "Free plan not explicitly confirmed (GEOAPIFY_FREE_PLAN=1)" if os.getenv("GEOAPIFY_FREE_PLAN") != "1" else
                    "No verified Paris coordinates" if not chosen else None)
        geo_rows = []
        for category, api_categories in categories.items():
            if category not in getattr(self.args, "categories", categories):
                continue
            rows = self.call("geoapify", category, "https://api.geoapify.com/v2/places",
                             {"categories": api_categories, "filter": f"circle:{lon},{lat},{getattr(self.args, 'radius', 3000)}", "limit": self.args.limit,
                              "lang": "en", "apiKey": geo_key or ""},
                             lambda d: d["features"], lambda r, c=category: normalize_geoapify(r, c, self.received_at), "geoapify", gate=geo_gate)
            geo_rows.extend(rows)
        for i, item in enumerate(geo_rows[:2]):
            self.call("geoapify", f"details_{i+1}", "https://api.geoapify.com/v2/place-details",
                      {"id": item["properties"]["place_id"], "features": "details", "apiKey": geo_key},
                      lambda d: d["features"], lambda r: normalize_geoapify(r, "details", self.received_at), "geoapify", gate=geo_gate)
        otm_key = None if self.args.no_keys else os.getenv("OPENTRIPMAP_API_KEY")
        otm_gate = ("Missing OPENTRIPMAP_API_KEY" if not otm_key else
                    "Non-commercial Free plan not confirmed (OPENTRIPMAP_FREE_PLAN=1)" if os.getenv("OPENTRIPMAP_FREE_PLAN") != "1" else
                    "No verified Paris coordinates" if not chosen else None)
        otm_rows = []
        for category, kinds in {"museums": "museums", "historic": "historic,cultural", "nature": "natural,gardens_and_parks", "restaurants": "restaurants,cafes"}.items():
            if category not in getattr(self.args, "categories", filters):
                continue
            rows = self.call("opentripmap", category, "https://api.opentripmap.com/0.1/en/places/radius",
                             {"lat": lat, "lon": lon, "radius": getattr(self.args, "radius", 3000), "kinds": kinds,
                              "limit": self.args.limit, "format": "json", "apikey": otm_key or ""},
                             lambda d: d, lambda r, c=category: normalize_otm(r, c, self.received_at), "otm", gate=otm_gate)
            otm_rows.extend(rows)
        for i, item in enumerate(otm_rows[:2]):
            xid = item.get("xid")
            if not isinstance(xid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", xid):
                self.skip("opentripmap", f"details_{i+1}", "Missing or invalid xid")
                continue
            self.call("opentripmap", f"details_{i+1}", f"https://api.opentripmap.com/0.1/en/places/xid/{xid}", {"apikey": otm_key},
                      lambda d: [d], lambda r: normalize_otm(r, "details", self.received_at), "otm", gate=otm_gate)
        username = None if self.args.no_keys else os.getenv("GEONAMES_USERNAME")
        gate = "Missing GEONAMES_USERNAME" if not username else "Demo account forbidden for tests" if username == "demo" else None
        self.call("geonames", "city_search", "https://secure.geonames.org/searchJSON",
                  {"name_equals": "Paris", "country": "FR", "featureCode": "PPLC", "maxRows": 10, "style": "FULL", "username": username or ""},
                  lambda d: d["geonames"], lambda r: normalize_geonames(r, "city", self.received_at), "geonames", gate=gate)
        self.call("geonames", "country_info", "https://secure.geonames.org/countryInfoJSON",
                  {"country": "FR", "username": username or ""}, lambda d: d["geonames"],
                  lambda r: normalize_geonames(r, "country", self.received_at), "geonames", gate=gate)
        self.call("geonames", "timezone", "https://secure.geonames.org/timezoneJSON",
                  {"lat": lat, "lng": lon, "username": username or ""}, lambda d: [d],
                  lambda r: normalize_geonames(r, "timezone", self.received_at), "geonames",
                  gate=gate or (None if chosen else "No verified coordinates"))
        self.call("frankfurter", "eur_rub_v2", "https://api.frankfurter.dev/v2/rate/EUR/RUB", {}, lambda d: [d])
        self.call("frankfurter", "eur_rub_v1", "https://api.frankfurter.dev/v1/latest", {"base": "EUR", "symbols": "RUB"}, lambda d: [d])
        def france_currency(tree):
            return [{child.tag: child.text for child in entry} for entry in tree.findall(".//CcyNtry") if entry.findtext("CtryNm") == "FRANCE"]
        self.call("six", "france_currency", "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml", {}, france_currency)
        def cldr_france(data):
            supplemental = data["supplemental"]
            today = self.context["run_date_moscow"]
            result = []
            for entry in supplemental["currencyData"]["region"]["FR"]:
                for code, validity in entry.items():
                    if (validity.get("_tender") != "false" and validity.get("_from", "0000") <= today
                            and validity.get("_to", "9999") >= today):
                        result.append({"country_code": "FR", "currency_code": code, "validity": validity,
                                       "version": supplemental["version"]})
            return result
        self.call("cldr", "france_currency", "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/cldr-core/supplemental/currencyData.json", {}, cldr_france)
        for provider, reason in DOC_ONLY.items():
            self.skip(provider, "documentation", reason)
        self.save()

    def save(self):
        report_dir = ROOT / "reports" / "runs" / self.run_id
        sample_dir = ROOT / "data" / "samples" / self.run_id
        report_dir.mkdir(parents=True, exist_ok=False)
        sample_dir.mkdir(parents=True, exist_ok=False)
        for result in self.results:
            sample = result.pop("sample", None)
            if sample is not None:
                path = sample_dir / f"{result['provider']}_{result['name']}.json"
                path.write_text(json.dumps(scrub(sample, self.secrets), ensure_ascii=False, indent=2), encoding="utf-8")
                result["sample_file"] = path.relative_to(ROOT).as_posix()
                if self.args.show_samples:
                    print(json.dumps(scrub(sample, self.secrets), ensure_ascii=False, indent=2))
        document = {"run_id": self.run_id, "retrieved_at_utc": self.now, "python": __import__("sys").version,
                    "offline": self.args.offline, "no_keys": self.args.no_keys,
                    "timeout_seconds": self.args.timeout, "minimum_gap_seconds": self.args.delay,
                    "context": self.context, "results": self.results,
                    "attribution": "OSM contributors / ODbL; Open-Meteo + GeoNames; Geoapify if used; SIX currency reference; Unicode CLDR / Unicode-3.0; Frankfurter blended rates"}
        document = scrub(document, self.secrets)
        (report_dir / "results.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        (report_dir / "live-results.md").write_text(render_report(document), encoding="utf-8")
        print("\nReports:", report_dir)
        print("Samples:", sample_dir)


def render_report(doc):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["# Фактический запуск", "", f"Run: `{doc['run_id']}`. UTC: {doc['retrieved_at_utc']}.",
             f"Offline: {doc['offline']}; без ключей: {doc['no_keys']}.", "",
             "Результат `ok` подтверждает только этот ответ. `skipped` не означает неисправность API.",
             "Доли заполнения относятся к первым N объектам запроса, не ко всему городу. 0/0 = нет измерения.",
             "Поле address может быть частичным; image_url означает ссылку, не проверенную лицензию изображения.",
             "Категория normalizer — группа запроса; исходные теги/категории находятся в примере JSON.", "",
             "```json", json.dumps(doc["context"], ensure_ascii=False, indent=2), "```", "",
             "| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |",
             "|---|---|---|---|---|---|---|"]
    for r in doc["results"]:
        lines.append("| " + " | ".join(cell(r.get(k, "")) for k in ("provider", "name", "status", "http_status", "duration_ms", "count", "reason")) + " |")
    for r in doc["results"]:
        lines.extend(["", f"## {r['provider']} / {r['name']}", "", f"Evidence: `{r['evidence']}`; endpoint: `{r['endpoint']}`.",
                      "", "Параметры / фильтры:", "```json", json.dumps(r["params"], ensure_ascii=False, indent=2), "```", "",
                      "Фактические поля: " + (", ".join(f"`{k}`" for k in r["actual_fields"]) or "не измерены") + "."])
        if r.get("sample_file"):
            lines.extend(["", f"Пример: [{r['sample_file']}](../../../{r['sample_file']})."])
        if r["coverage"] and any(v["total"] for v in r["coverage"].values()):
            lines.extend(["", "| Нормализованное поле | Заполнено | Доля |", "|---|---|---|"])
            for field, stats in r["coverage"].items():
                n, total = stats["filled"], stats["total"]
                lines.append(f"| {field} | {n}/{total} | {n/total:.0%} |")
        if r.get("source_metadata"):
            lines.extend(["", "Метаданные источника: `" + json.dumps(r["source_metadata"], ensure_ascii=False) + "`."])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="TripFlow read-only data source survey (no paid calls)")
    parser.add_argument("--no-keys", action="store_true", help="Ignore local key variables and .env")
    parser.add_argument("--offline", action="store_true", help="No network; save a skip report")
    parser.add_argument("--providers", nargs="+", choices=["open_meteo", "overpass", "geoapify", "opentripmap", "geonames", "frankfurter", "six", "cldr"], help="Subset; POI requires open_meteo in the same run")
    parser.add_argument("--categories", nargs="+", choices=["museums", "historic", "nature", "restaurants", "hotels"], default=["museums", "historic", "nature", "restaurants", "hotels"])
    parser.add_argument("--radius", type=int, choices=range(500, 3001), default=3000, metavar="500..3000")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=10)
    parser.add_argument("--show-samples", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 30 or not 1 <= args.delay <= 30:
        parser.error("timeout must be 1..30 seconds; delay must be 1..30 seconds")
    if not args.no_keys:
        load_env(ROOT / ".env")
    survey = Survey(args)
    survey.run()
    # Exit 0 means a report was written, not that providers succeeded. Use results.json statuses.
    return 0

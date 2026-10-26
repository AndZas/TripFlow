"""Bounded, sequential research run. No external requests unless --live is given."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "data-source-survey"
SAMPLES = PREVIOUS / "data" / "samples" / "20261015T150210175612Z"
RUNS = HERE / "reports" / "runs"
GEO_URL = "https://api.geoapify.com/v1/geocode/search"
OTM_URL = "https://api.opentripmap.com/0.1/en/places"
OTM_CATALOG = "https://dev.opentripmap.org/en/catalog.tree.json"
FRANK_URL = "https://api.frankfurter.dev/v2/rate/TRY/RUB"
WD_URL = "https://www.wikidata.org/w/api.php"
COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
CITY_KEYS = ("paris", "moscow", "istanbul", "suzdal")
CATEGORIES = {"museums": "museums", "historic": "historic", "nature": "natural"}
FIELDS_GEO = ("name", "country", "country_code", "latitude", "longitude", "city", "state", "timezone", "result_type", "place_id", "currency")
FIELDS_POI = ("xid", "name", "kinds", "latitude", "longitude", "address", "description", "image_url", "wikipedia", "wikidata", "website", "language", "rate", "price_amount", "availability")
STATUS = {"ok", "empty", "missing_key", "skipped", "http_error", "provider_error", "schema_error", "timeout", "rate_limited"}


def present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, (list, dict)):
        return bool(value)
    return False


def coverage(rows: list[dict], fields: tuple[str, ...]) -> dict:
    return {field: {"n_requested": len(rows), "n_present": sum(present(r.get(field)) for r in rows),
                    "n_unknown": len(rows) - sum(present(r.get(field)) for r in rows), "n_not_applicable": 0,
                    "percent": round(100 * sum(present(r.get(field)) for r in rows) / len(rows), 1) if rows else None}
            for field in fields}


def number(value: object) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def text_value(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    # Never persist query strings (possible credentials/tracking tokens).
    return value.split("?", 1)[0].split("#", 1)[0]


def norm_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if c.isalnum() and not unicodedata.combining(c))


def distance_m(a: dict, b: dict) -> float | None:
    lat1, lon1, lat2, lon2 = (number(a.get("latitude")), number(a.get("longitude")),
                              number(b.get("latitude")), number(b.get("longitude")))
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(min(1, math.sqrt(h)))


def normalize_geo(raw: dict) -> dict:
    tz = raw.get("timezone") if isinstance(raw.get("timezone"), dict) else {}
    return {"name": text_value(raw.get("name")), "country": text_value(raw.get("country")),
            "country_code": text_value(raw.get("country_code")), "latitude": number(raw.get("lat")),
            "longitude": number(raw.get("lon")), "city": text_value(raw.get("city")),
            "state": text_value(raw.get("state")), "timezone": text_value(tz.get("name")),
            "result_type": text_value(raw.get("result_type")), "place_id": text_value(raw.get("place_id")),
            "currency": text_value(raw.get("currency")),
            "confidence": number((raw.get("rank") or {}).get("confidence")) if isinstance(raw.get("rank"), dict) else None}


def normalize_otm(raw: dict) -> dict:
    point = raw.get("point") if isinstance(raw.get("point"), dict) else {}
    address = raw.get("address") if isinstance(raw.get("address"), dict) else {}
    extracts = raw.get("wikipedia_extracts") if isinstance(raw.get("wikipedia_extracts"), dict) else {}
    preview = raw.get("preview") if isinstance(raw.get("preview"), dict) else {}
    description = text_value(extracts.get("text")) or text_value(raw.get("description"))
    osm = text_value(raw.get("osm"))
    if osm and re.fullmatch(r"[NWR]\d+", osm, re.I):
        osm = {"N": "node", "W": "way", "R": "relation"}[osm[0].upper()] + "/" + osm[1:]
    return {"xid": text_value(raw.get("xid")), "name": text_value(raw.get("name")),
            "kinds": text_value(raw.get("kinds")), "latitude": number(point.get("lat")),
            "longitude": number(point.get("lon")), "address": ", ".join(str(x) for x in address.values() if present(x)) or None,
            "description": description, "image_url": safe_url(preview.get("source") or raw.get("image")),
            "wikipedia": safe_url(raw.get("wikipedia")), "wikidata": text_value(raw.get("wikidata")),
            "website": safe_url(raw.get("url") or raw.get("website")), "language": text_value(extracts.get("language")),
            "rate": text_value(raw.get("rate")) or number(raw.get("rate")),
            "price_amount": number(raw.get("price_amount")), "availability": raw.get("availability") if isinstance(raw.get("availability"), bool) else None,
            "osm": osm, "commons": text_value(raw.get("commons"))}


def geo_sample(feature: dict) -> dict:
    p = feature.get("properties") or {}
    raw = (p.get("datasource") or {}).get("raw") or {}
    osm_type = {"n": "node", "w": "way", "r": "relation"}.get(str(raw.get("osm_type", "")).lower())
    osm_id = raw.get("osm_id")
    return {"name": p.get("name"), "latitude": number(p.get("lat")), "longitude": number(p.get("lon")),
            "osm": f"{osm_type}/{osm_id}" if osm_type and osm_id else None,
            "wikidata": (p.get("wiki_and_media") or {}).get("wikidata") or raw.get("wikidata"),
            "description": text_value(p.get("description")), "image_url": safe_url((p.get("wiki_and_media") or {}).get("image")),
            "website": safe_url(p.get("website")), "place_id": p.get("place_id")}


def load_prior() -> tuple[dict, dict]:
    coords, pois = {}, {}
    for city in CITY_KEYS:
        path = SAMPLES / f"open_meteo_{city}_city.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        row = data["normalized"][0]
        geonames = json.loads((SAMPLES / f"geonames_{city}_city.json").read_text(encoding="utf-8"))["normalized"][0]
        coords[city] = {"name": row["name"], "latitude": row["latitude"], "longitude": row["longitude"],
                        "country_code": row["country_code"], "timezone": row["timezone"],
                        "geonames": {"name": geonames["name"], "latitude": geonames["latitude"],
                                     "longitude": geonames["longitude"], "country_code": geonames["country_code"],
                                     "timezone": geonames["timezone"]}}
        for category in CATEGORIES:
            data = json.loads((SAMPLES / f"geoapify_{city}_{category}.json").read_text(encoding="utf-8"))
            pois[f"{city}/{category}"] = [geo_sample(f) for f in data.get("raw", [])[:2]]
    return coords, pois


def match_poi(item: dict, samples: list[dict]) -> dict:
    exact = [s for s in samples if (item.get("wikidata") and item["wikidata"] == s.get("wikidata")) or
             (item.get("xid") and re.fullmatch(r"Q\d+", item["xid"]) and item["xid"] == s.get("wikidata")) or
             (item.get("osm") and item["osm"] == s.get("osm"))]
    if len(exact) == 1:
        return {"kind": "exact_id", "sample": exact[0], "distance_m": distance_m(item, exact[0])}
    if len(exact) > 1:
        return {"kind": "uncertain", "sample": None, "distance_m": None}
    near = [(s, distance_m(item, s)) for s in samples if norm_name(item.get("name")) and
            norm_name(item.get("name")) == norm_name(s.get("name"))]
    near = [(s, d) for s, d in near if d is not None and d <= 100]
    if len(near) == 1:
        return {"kind": "probable_name_distance", "sample": near[0][0], "distance_m": round(near[0][1], 1)}
    if len(near) > 1 or any((distance_m(item, s) or 999999) <= 100 for s in samples):
        return {"kind": "uncertain", "sample": None, "distance_m": None}
    return {"kind": "new", "sample": None, "distance_m": None}


def catalog_kinds(data: object) -> set[str]:
    found = set()
    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key in ("id", "name", "kind", "key"):
                v = value.get(key)
                if isinstance(v, str) and re.fullmatch(r"[a-z_]+", v):
                    found.add(v)
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(data)
    return found


class Client:
    def __init__(self, max_requests: int, delay: float, timeout: float):
        self.max_requests, self.delay, self.timeout = max_requests, max(1.0, delay), timeout
        self.count, self.last = 0, 0.0
        self.stopped: set[str] = set()

    def get(self, provider: str, url: str, params: dict | None = None, ua: str | None = None) -> tuple[dict, object | None]:
        if provider in self.stopped or self.count >= self.max_requests:
            return {"status": "skipped", "reason": "provider_stopped_or_global_cap", "http_status": None, "duration_ms": None}, None
        wait = self.delay - (time.monotonic() - self.last)
        if wait > 0 and self.count:
            time.sleep(wait)
        self.last = time.monotonic()
        self.count += 1
        target = url + (("?" + urlencode(params)) if params else "")
        req = Request(target, headers={"User-Agent": ua or "TripFlow-FreeApiGapTest/1.0 (research)", "Accept": "application/json"})
        started = time.monotonic()
        try:
            with urlopen(req, timeout=self.timeout) as response:
                status = response.status
                body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    return {"status": "schema_error", "reason": "response_too_large", "http_status": status, "duration_ms": round((time.monotonic()-started)*1000)}, None
                data = json.loads(body)
        except HTTPError as exc:
            status = exc.code
            if status in (401, 403, 429):
                self.stopped.add(provider)
            return {"status": "rate_limited" if status == 429 else "http_error", "reason": "http_status_only", "http_status": status,
                    "duration_ms": round((time.monotonic()-started)*1000), "retry_after_seconds": exc.headers.get("Retry-After") if status == 429 else None}, None
        except (TimeoutError, URLError):
            return {"status": "timeout", "reason": "network_or_timeout", "http_status": None, "duration_ms": round((time.monotonic()-started)*1000)}, None
        except (ValueError, UnicodeError):
            return {"status": "schema_error", "reason": "invalid_json", "http_status": 200, "duration_ms": round((time.monotonic()-started)*1000)}, None
        info = {"status": "ok", "http_status": status, "duration_ms": round((time.monotonic()-started)*1000)}
        if isinstance(data, dict) and (data.get("error") or data.get("errors")):
            info["status"] = "provider_error"
            info["reason"] = "provider_reported_error"
            error = data.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            if isinstance(code, str) and any(word in code.casefold() for word in ("quota", "limit", "rate")):
                info["status"] = "rate_limited"
                self.stopped.add(provider)
            data = None
        return info, data


def record(provider: str, name: str, info: dict, rows: list[dict] | None = None, fields: tuple[str, ...] = ()) -> dict:
    entry = {"provider": provider, "name": name, **info}
    if rows is not None:
        entry["count"] = len(rows)
        entry["coverage"] = coverage(rows, fields)
        if entry["status"] == "ok" and not rows:
            entry["status"] = "empty"
    return entry


def sample_write(folder: Path, endpoint: str, rows: list[dict]) -> None:
    if rows:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{endpoint}.json").write_text(json.dumps(rows[:2], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def geocode(client: Client, key: str, prior: dict, entries: list, sample_dir: Path) -> list[dict]:
    cases = [("paris", "Paris", None), ("moscow", "Moscow", None), ("moscow_cyrillic", "Москва", None),
             ("istanbul", "Istanbul", None), ("suzdal", "Suzdal", None),
             ("springfield", "Springfield", None), ("springfield_us", "Springfield", "us"),
             ("unknown", "TripFlowNonexistentCityQzxv98765", None)]
    all_rows = []
    for name, query, country in cases:
        params = {"text": query, "type": "city", "limit": 10, "lang": "en", "format": "json", "bias": "countrycode:none", "apiKey": key}
        if country:
            params["filter"] = "countrycode:" + country
        info, data = client.get("geoapify", GEO_URL, params)
        if info["status"] == "ok":
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                info["status"], info["reason"] = "schema_error", "missing_results_list"
                rows = []
            else:
                rows = [normalize_geo(r) for r in data["results"] if isinstance(r, dict)]
        else:
            rows = []
        item = record("geoapify", name, info, rows if info["status"] in ("ok", "empty") else None, FIELDS_GEO)
        if name in prior and rows:
            for source, reference in (("open_meteo", prior[name]), ("geonames", prior[name]["geonames"])):
                item[f"prior_{source}_comparison"] = [
                    {"country_matches": (r.get("country_code") or "").upper() == reference["country_code"].upper(),
                     "distance_m": round(d, 1) if (d := distance_m(r, reference)) is not None else None,
                     "same_name": norm_name(r.get("name")) == norm_name(reference["name"])} for r in rows]
        if name.startswith("springfield"):
            item["requires_user_selection"] = len(rows) != 1
        item["input_text"] = query
        item["candidate_count"] = len(rows)
        entries.append(item)
        all_rows.extend(rows)
        sample_write(sample_dir, "geoapify_geocoding_" + name, rows)
    return all_rows


def otm(client: Client, key: str, prior_coords: dict, prior_pois: dict, entries: list, sample_dir: Path) -> tuple[list[dict], list[dict]]:
    info, data = client.get("opentripmap", OTM_CATALOG)
    if info["status"] != "ok" or not isinstance(data, (dict, list)):
        entries.append(record("opentripmap", "official_catalog", {"status": "skipped", "reason": "official_catalog_unavailable_or_invalid", "http_status": info.get("http_status"), "duration_ms": info.get("duration_ms")}))
        return [], []
    kinds = catalog_kinds(data)
    entries.append(record("opentripmap", "official_catalog", {"status": "ok", "http_status": info["http_status"], "duration_ms": info["duration_ms"], "validated_kinds": {k: v in kinds for k, v in CATEGORIES.items()}}))
    all_rows, matches = [], []
    for city in CITY_KEYS:
        for category, kind in CATEGORIES.items():
            label = f"{city}/{category}"
            if kind not in kinds:
                entries.append(record("opentripmap", label, {"status": "skipped", "reason": "kind_not_in_official_catalog", "http_status": None, "duration_ms": None}))
                continue
            coord = prior_coords[city]
            params = {"lat": coord["latitude"], "lon": coord["longitude"], "radius": 3000,
                      "kinds": kind, "limit": 5, "format": "json", "apikey": key}
            info, data = client.get("opentripmap", OTM_URL + "/radius", params)
            if info["status"] != "ok":
                entries.append(record("opentripmap", label, info))
                continue
            if not isinstance(data, list):
                entries.append(record("opentripmap", label, {**info, "status": "schema_error", "reason": "expected_list"}))
                continue
            list_rows = [normalize_otm(x) for x in data if isinstance(x, dict)]
            entries.append(record("opentripmap", label + "/list", info, list_rows, FIELDS_POI))
            sample_write(sample_dir, f"opentripmap_{city}_{category}_list", list_rows)
            details = []
            for row in list_rows[:2]:
                xid = row.get("xid")
                if not xid or not re.fullmatch(r"[A-Za-z0-9_-]+", xid):
                    entries.append(record("opentripmap", label + "/details", {"status": "skipped", "reason": "invalid_xid", "http_status": None, "duration_ms": None}))
                    continue
                detail_info, detail = client.get("opentripmap", OTM_URL + "/xid/" + xid, {"apikey": key})
                if detail_info["status"] == "ok" and isinstance(detail, dict):
                    full = normalize_otm(detail)
                    # List fields may be absent from Details; retain observed values.
                    full = {field: full.get(field) if present(full.get(field)) else row.get(field) for field in set(full) | set(row)}
                    details.append(full)
                    m = match_poi(full, prior_pois[label])
                    sample = m.pop("sample")
                    m.update({"city": city, "category": category, "xid": xid,
                              "geoapify_place_id": sample.get("place_id") if sample else None,
                              "added_fields": [f for f in ("description", "image_url", "website") if sample and not present(sample.get(f)) and present(full.get(f))],
                              "remaining_gaps": [f for f in ("description", "image_url") if sample and not present(sample.get(f)) and not present(full.get(f))],
                              "wikidata": full.get("wikidata")})
                    matches.append(m)
                    all_rows.append(full)
                    entries.append(record("opentripmap", label + "/details", detail_info, [full], FIELDS_POI))
                else:
                    if detail_info["status"] == "ok":
                        detail_info = {**detail_info, "status": "schema_error", "reason": "expected_object"}
                    entries.append(record("opentripmap", label + "/details", detail_info))
            sample_write(sample_dir, f"opentripmap_{city}_{category}_details", details)
    return all_rows, matches


def targeted_qids(client: Client, key: str, prior_pois: dict, entries: list, sample_dir: Path) -> list[dict]:
    """Small follow-up for Geoapify samples that expose a common Wikidata QID."""
    matches = []
    seen = set()
    for label, samples in prior_pois.items():
        city, category = label.split("/")
        for sample in samples:
            qid = sample.get("wikidata")
            if not isinstance(qid, str) or not re.fullmatch(r"Q\d+", qid) or qid in seen:
                continue
            seen.add(qid)
            info, data = client.get("opentripmap", OTM_URL + "/xid/" + qid, {"apikey": key})
            if info["status"] != "ok":
                entries.append(record("opentripmap", label + "/targeted_details", info))
                continue
            if not isinstance(data, dict):
                entries.append(record("opentripmap", label + "/targeted_details", {**info, "status": "schema_error", "reason": "expected_object"}))
                continue
            full = normalize_otm(data)
            if full.get("xid") != qid and full.get("wikidata") != qid:
                entries.append(record("opentripmap", label + "/targeted_details", {**info, "status": "schema_error", "reason": "qid_not_confirmed_in_response"}))
                continue
            match = match_poi(full, samples)
            linked = match.pop("sample")
            match.update({"city": city, "category": category, "xid": full.get("xid"),
                          "geoapify_place_id": linked.get("place_id") if linked else None,
                          "added_fields": [f for f in ("description", "image_url", "website") if linked and not present(linked.get(f)) and present(full.get(f))],
                          "remaining_gaps": [f for f in ("description", "image_url") if linked and not present(linked.get(f)) and not present(full.get(f))],
                          "wikidata": full.get("wikidata") or (qid if full.get("xid") == qid else None),
                          "targeted_qid": qid})
            matches.append(match)
            entries.append(record("opentripmap", label + "/targeted_details", info, [full], FIELDS_POI))
            sample_write(sample_dir, "opentripmap_targeted_" + qid, [full])
    return matches


def frankfurter(client: Client, entries: list, sample_dir: Path) -> None:
    info, data = client.get("frankfurter", FRANK_URL)
    if info["status"] == "ok":
        if not isinstance(data, dict) or data.get("base", "").upper() != "TRY" or data.get("quote", "").upper() != "RUB" or not number(data.get("rate")) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("date"))):
            info = {**info, "status": "schema_error", "reason": "unexpected_pair_date_or_rate"}
        else:
            info = {**info, "pair": "TRY/RUB", "date": data["date"], "rate": number(data["rate"])}
            sample_write(sample_dir, "frankfurter_try_rub", [{"date": data["date"], "base": "TRY", "quote": "RUB", "rate": number(data["rate"])}])
    entries.append(record("frankfurter", "TRY/RUB", info))


def plain_html(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return text_value(unescape(re.sub(r"<[^>]*>", "", value)))


def wikimedia(client: Client, ua: str, matches: list[dict], entries: list, sample_dir: Path) -> None:
    candidates = [m for m in matches if m["kind"] == "exact_id" and m.get("wikidata") and m.get("remaining_gaps")]
    qids = list(dict.fromkeys(m["wikidata"] for m in candidates if re.fullmatch(r"Q\d+", m["wikidata"])))[:5]
    if not qids:
        entries.append(record("wikimedia", "conditional", {"status": "skipped", "reason": "no_exact_matched_qid_with_gap", "http_status": None, "duration_ms": None}))
        return
    if not ua or "TripFlow" not in ua or not ("@" in ua or "https://" in ua):
        entries.append(record("wikimedia", "conditional", {"status": "skipped", "reason": "missing_meaningful_WIKIMEDIA_USER_AGENT", "http_status": None, "duration_ms": None}))
        return
    used = 0
    for qid in qids:
        if used >= 10:
            break
        info, data = client.get("wikimedia", WD_URL, {"action": "wbgetentities", "ids": qid, "props": "descriptions|claims", "languages": "en|ru", "format": "json"}, ua)
        used += 1
        if info["status"] != "ok":
            entries.append(record("wikimedia", "wikidata/" + qid, info))
            continue
        entity = (data.get("entities") or {}).get(qid) if isinstance(data, dict) else None
        if not isinstance(entity, dict):
            entries.append(record("wikimedia", "wikidata/" + qid, {**info, "status": "schema_error", "reason": "missing_entity"}))
            continue
        descriptions = entity.get("descriptions") or {}
        claims = entity.get("claims") or {}
        image_claims = claims.get("P18") or []
        image_title = None
        if image_claims:
            image_title = (((image_claims[0].get("mainsnak") or {}).get("datavalue") or {}).get("value"))
        row = {"qid": qid, "description_en": (descriptions.get("en") or {}).get("value"),
               "description_ru": (descriptions.get("ru") or {}).get("value"),
               "image_title": image_title if isinstance(image_title, str) else None}
        entries.append(record("wikimedia", "wikidata/" + qid, info, [row], ("description_en", "description_ru", "image_title")))
        sample_write(sample_dir, "wikidata_entity", [row])
        if not row["image_title"] or used >= 10:
            continue
        info, data = client.get("wikimedia", COMMONS_URL, {"action": "query", "prop": "imageinfo", "iiprop": "url|extmetadata", "titles": "File:" + row["image_title"], "format": "json"}, ua)
        used += 1
        if info["status"] != "ok":
            entries.append(record("wikimedia", "commons/" + qid, info))
            continue
        pages = ((data.get("query") or {}).get("pages") or {}) if isinstance(data, dict) else {}
        page = next(iter(pages.values()), {})
        imageinfo = (page.get("imageinfo") or [{}])[0]
        metadata = imageinfo.get("extmetadata") or {}
        meta = lambda k: plain_html((metadata.get(k) or {}).get("value"))
        image = {"qid": qid, "title": page.get("title"), "url": safe_url(imageinfo.get("url")),
                 "author": meta("Artist"), "license_name": meta("LicenseShortName"),
                 "license_url": safe_url(meta("LicenseUrl")), "attribution": meta("Attribution"), "language": "en"}
        entries.append(record("wikimedia", "commons/" + qid, info, [image], ("url", "author", "license_name", "license_url", "attribution")))
        sample_write(sample_dir, "commons_imageinfo", [image])


def ratio(c: dict) -> str:
    n, d = c["n_present"], c["n_requested"]
    return f"{n}/{d} ({c['percent']}%)" if d else "0/0 (не измерено)"


def markdown(result: dict) -> str:
    lines = ["# Результат Free API Gap Test", "", f"Run `{result['run_id']}`; режим: {'live' if result['live'] else 'offline'}; сетевых запросов: {result['attempted_requests']}.",
             "", "HTTP-успех и заполненность полей учитываются отдельно. Выборка мала; доли не являются прогнозом будущей выдачи.", "",
             "## Запросы", "", "| Провайдер | Проверка | Статус | HTTP | мс | Объектов |", "|---|---|---|---:|---:|---:|"]
    if result.get("supplements_run"):
        lines.insert(3, f"Дополнение к run `{result['supplements_run']}`; базовый запуск сделал {result['base_attempted_requests']} запросов, этот запуск — {result['attempted_requests']}. Ни один базовый запрос не повторён.")
    for e in result["entries"]:
        lines.append(f"| {e['provider']} | {e['name']} | {e['status']} | {e.get('http_status') or '—'} | {e.get('duration_ms') or '—'} | {e.get('count', '—')} |")
    lines += ["", "## Заполненность", ""]
    for e in result["entries"]:
        if e.get("coverage"):
            lines.append(f"### {e['provider']} / {e['name']}")
            lines.append("")
            lines.append(", ".join(f"{field}: {ratio(c)}" for field, c in e["coverage"].items()))
            lines.append("")
    lines += ["## Сопоставление с очищенными Geoapify samples", "",
              f"Знаменатель: {result['prior_sample_count']} сохранённых POI (не полный каталог).", ""]
    counts = {k: sum(m["kind"] == k for m in result["matches"]) for k in ("exact_id", "probable_name_distance", "new", "uncertain")}
    if result["matches"]:
        lines.append("; ".join(f"{k}: {v}" for k, v in counts.items()) + ".")
        lines.append("Добавленные поля у совпавших объектов: " + ", ".join(f"{f}: {sum(f in m['added_fields'] for m in result['matches'] if m['kind'] in ('exact_id', 'probable_name_distance'))}" for f in ("description", "image_url", "website")) + ".")
    else:
        lines.append("Не измерено: успешных сопоставленных Details пока нет.")
    lines += ["", "Совпадения по имени и расстоянию ≤100 м являются вероятными, не автоматическим слиянием. Неуверенные пары требуют ручной проверки.",
              "", "## Ограничения", "", "Неизвестная цена и доступность остаются null. Курс Frankfurter справочный дневной, не цена оплаты. URL фотографии не даёт права показывать её без проверки лицензии и атрибуции."]
    return "\n".join(lines) + "\n"


def assessment(result: dict) -> str:
    es = result["entries"]
    geo = [e for e in es if e["provider"] == "geoapify" and e["name"] in CITY_KEYS]
    geo_ok = len(geo) == 4 and all(e["status"] == "ok" and e.get("count", 0) and
                                  e["coverage"]["timezone"]["n_present"] > 0 and
                                  any(c["country_matches"] and c["distance_m"] is not None and c["distance_m"] <= 20000
                                      for c in e.get("prior_geonames_comparison", [])) for e in geo)
    otm_details = [e for e in es if e["provider"] == "opentripmap" and e["name"].endswith("/details") and e["status"] == "ok"]
    targeted_404 = sum(e["provider"] == "opentripmap" and e["name"].endswith("/targeted_details") and e.get("http_status") == 404 for e in es)
    matches = result["matches"]
    added = {f: sum(f in m["added_fields"] for m in matches if m["kind"] in ("exact_id", "probable_name_distance")) for f in ("description", "image_url", "website")}
    detail_counts = {f: sum(e["coverage"][f]["n_present"] for e in otm_details) for f in ("description", "image_url", "website", "price_amount", "availability")}
    frank = next((e for e in es if e["provider"] == "frankfurter"), None)
    return "\n".join(["# Оценка бесплатных источников для TripFlow", "",
        f"Статус: {'живой ограниченный запуск' if result['live'] else 'подготовка без сетевых запросов'}. Run `{result['run_id']}`" + (f" дополняет `{result['supplements_run']}` ({result['base_attempted_requests']} исходных и {result['attempted_requests']} точечных запросов)." if result.get("supplements_run") else "."), "",
        (f"Первый запуск `{result['incomplete_run']}` выполнил сетевые запросы, но завершился ошибкой сохранения. Его очищенные образцы помечены `INCOMPLETE.md`; полные счётчики недоступны и ниже не учтены." if result.get("incomplete_run") else ""), "",
        "## Подтверждено предыдущим исследованием 15.10.2026", "",
        "Geoapify Places: 100 POI, название 91/100, сайт 27/100, фото 3/100, описание 3/100, числовая цена и наличие 0/100. GeoNames/Open-Meteo проверили четыре города; CLDR/GeoNames — валюты FR/EUR, RU/RUB, TR/TRY; Frankfurter — EUR/RUB. Эти вызовы здесь не повторялись.", "",
        "## Решения", "",
        f"- **Geoapify Geocoding:** {'может заменить отдельный геокодер для четырёх проверенных городов; неоднозначные результаты требуют выбора пользователем (Paris — 3 кандидата, Moscow — 6)' if geo_ok else 'оставить решение открытым до успешного живого прогона и проверки неоднозначности'}; GeoNames оставить резервом для валюты/метаданных, если они нужны. Не вызывать оба автоматически. Поля валюты в ответах Geoapify не было.",
        (f"- **OpenTripMap:** {len(otm_details)} успешных Details; описание {detail_counts['description']}/{len(otm_details)}, изображение {detail_counts['image_url']}/{len(otm_details)}, сайт {detail_counts['website']}/{len(otm_details)}, числовая цена и доступность {detail_counts['price_amount']}/{len(otm_details)} и {detail_counts['availability']}/{len(otm_details)}. Совпадений с сохранёнными Geoapify samples: ID {sum(m['kind']=='exact_id' for m in matches)}, вероятных {sum(m['kind']=='probable_name_distance' for m in matches)}; прирост описаний/фото/сайтов для тех же объектов: {added['description']}/{added['image_url']}/{added['website']}. Точечные QID-запросы вернули 404: {targeted_404}. Для обогащения Geoapify сейчас **не подключать**; можно оставить отдельным резервным каталогом. Этот вывод относится только к малой выборке." if otm_details else
         "- **OpenTripMap:** живых Details пока нет; прирост и надёжность сопоставления не измерены. Оставить резервом."),
        f"- **Frankfurter TRY/RUB:** {('подтверждён курс ' + str(frank['rate']) + ' на ' + frank['date']) if frank and frank['status']=='ok' else 'не подтверждён; нужен живой ответ'}; это дневной справочный курс.",
        "- **Wikidata/Commons:** этап не вызывался: точных сопоставленных объектов с пробелами нет. Без устойчивой связи с Geoapify не подключать. Для каждой будущей картинки понадобятся автор, лицензия и атрибуция.", "",
        "## Минимальный кандидатный поток", "",
        "Geoapify Geocoding → локальный CLDR/проверенная валюта страны → Geoapify Places из предыдущего опыта → Frankfurter только при пересчёте известной денежной суммы в RUB. OpenTripMap пока вне основного потока. AI ранжирует реальные кандидаты и не выдумывает цены.", "",
        "## Незакрытые данные", "",
        "Цены и наличие отелей на даты, числовая стоимость входных билетов, гарантированные фото/описания, актуальность графика работы и стоимость питания/транспорта. Парсинг и платные API этим экспериментом не проверяются.", "",
        "## Доступ для повторного запуска", "",
        "Geoapify: `GEOAPIFY_API_KEY` и `GEOAPIFY_FREE_PLAN=1`, личная регистрация [MyProjects](https://myprojects.geoapify.com/), Free 3 000 кредитов/день и 5 запросов/с. OpenTripMap: `OPENTRIPMAP_API_KEY` и `OPENTRIPMAP_FREE_NONCOMMERCIAL=1`, [регистрация](https://dev.opentripmap.org/register), Free 5 000 запросов/день и 10 запросов/с только некоммерчески. Для условного Wikimedia: `WIKIMEDIA_USER_AGENT` с контактом. Ключи задаются в environment процесса PowerShell, как описано в [README](../README.md); не присылайте их в чат. Перед запуском сверьте актуальный план в кабинете.", "",
        "Выборка сохранённых Geoapify samples ограничена двумя объектами на endpoint; вывод о cross-match не относится к полному каталогу. Условия Free проверить перед будущим коммерческим использованием.", ""])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="analyze old local samples; no network")
    mode.add_argument("--live", action="store_true", help="explicitly allow bounded external requests")
    p.add_argument("--providers", nargs="+", choices=("geoapify", "opentripmap", "frankfurter", "wikimedia"), default=["geoapify", "opentripmap", "frankfurter", "wikimedia"])
    p.add_argument("--max-requests", type=int, default=50)
    p.add_argument("--delay-seconds", type=float, default=1.1)
    p.add_argument("--timeout-seconds", type=float, default=15)
    p.add_argument("--targeted-from", help="UTC run ID to supplement with QID Details; no prior requests are repeated")
    args = p.parse_args(argv)
    if not 1 <= args.max_requests <= 50 or not 1 <= args.delay_seconds <= 60 or not 1 <= args.timeout_seconds <= 60:
        p.error("limits: 1..50 requests, 1..60 seconds delay/timeout")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = RUNS / run_id
    sample_dir = folder / "samples"
    prior_coords, prior_pois = load_prior()
    entries, matches = [], []
    client = Client(args.max_requests, args.delay_seconds, args.timeout_seconds)
    base = None
    if args.targeted_from:
        if not args.live or not re.fullmatch(r"\d{8}T\d{12}Z", args.targeted_from):
            p.error("--targeted-from requires --live and a valid UTC run ID")
        base_path = RUNS / args.targeted_from / "results.json"
        if not base_path.is_file():
            p.error("base run results.json not found")
        base = json.loads(base_path.read_text(encoding="utf-8"))
        entries = [e for e in base["entries"] if not (e["provider"] == "wikimedia" and e["name"] == "conditional")]
        matches = list(base["matches"])
        key = os.environ.get("OPENTRIPMAP_API_KEY", "")
        if not key or os.environ.get("OPENTRIPMAP_FREE_NONCOMMERCIAL") != "1":
            p.error("OpenTripMap Free key and confirmation are required for targeted run")
        matches.extend(targeted_qids(client, key, prior_pois, entries, sample_dir))
        if "wikimedia" in args.providers:
            wikimedia(client, os.environ.get("WIKIMEDIA_USER_AGENT", ""), matches, entries, sample_dir)
    elif args.live:
        if "geoapify" in args.providers:
            key = os.environ.get("GEOAPIFY_API_KEY", "")
            if not key:
                entries.append(record("geoapify", "geocoding", {"status": "missing_key", "reason": "GEOAPIFY_API_KEY", "http_status": None, "duration_ms": None}))
            elif os.environ.get("GEOAPIFY_FREE_PLAN") != "1":
                entries.append(record("geoapify", "geocoding", {"status": "skipped", "reason": "GEOAPIFY_FREE_PLAN_not_confirmed", "http_status": None, "duration_ms": None}))
            else:
                geocode(client, key, prior_coords, entries, sample_dir)
        if "opentripmap" in args.providers:
            key = os.environ.get("OPENTRIPMAP_API_KEY", "")
            if not key:
                entries.append(record("opentripmap", "poi", {"status": "missing_key", "reason": "OPENTRIPMAP_API_KEY", "http_status": None, "duration_ms": None}))
            elif os.environ.get("OPENTRIPMAP_FREE_NONCOMMERCIAL") != "1":
                entries.append(record("opentripmap", "poi", {"status": "skipped", "reason": "OPENTRIPMAP_FREE_NONCOMMERCIAL_not_confirmed", "http_status": None, "duration_ms": None}))
            else:
                _, matches = otm(client, key, prior_coords, prior_pois, entries, sample_dir)
        if "frankfurter" in args.providers:
            frankfurter(client, entries, sample_dir)
        if "wikimedia" in args.providers:
            wikimedia(client, os.environ.get("WIKIMEDIA_USER_AGENT", ""), matches, entries, sample_dir)
    else:
        for provider in args.providers:
            entries.append(record(provider, "offline", {"status": "skipped", "reason": "offline_mode", "http_status": None, "duration_ms": None}))
    result = {"run_id": run_id, "live": args.live, "attempted_requests": client.count,
              "max_requests": args.max_requests, "prior_sample_count": sum(map(len, prior_pois.values())),
              "prior_coordinates": prior_coords, "entries": entries, "matches": matches}
    if base:
        result["supplements_run"] = args.targeted_from
        result["base_attempted_requests"] = base["attempted_requests"]
    # sample_write may have created this run directory before the final report.
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "live-results.md").write_text(markdown(result), encoding="utf-8")
    (HERE / "reports" / "assessment.md").write_text(assessment(result), encoding="utf-8")
    print(f"Run saved: {folder}; attempted requests: {client.count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

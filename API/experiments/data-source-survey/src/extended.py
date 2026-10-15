"""Bounded sequential functional checks; shares transport/secrets handling with survey."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import available_timezones

from .survey import (ROOT, Survey, FIELDS, coverage, load_env, normalize_geoapify,
                     normalize_geonames, geoapify_osm_reference, present, scrub)

CITIES = {
    "paris": {"query": "Paris", "country": "FR", "aliases": ["Paris", "Париж"], "capital": True},
    "moscow": {"query": "Moscow", "country": "RU", "aliases": ["Moscow", "Moskva", "Москва"], "capital": True},
    "istanbul": {"query": "Istanbul", "country": "TR", "aliases": ["Istanbul", "İstanbul", "Стамбул"]},
    "suzdal": {"query": "Suzdal", "country": "RU", "aliases": ["Suzdal", "Suzdal'", "Suzdal’", "Суздаль"]},
}
CATEGORIES = {"museums": "entertainment.museum", "historic": "tourism.sights",
              "nature": "leisure.park,natural,tourism.attraction.viewpoint",
              "restaurants": "catering.restaurant,catering.cafe",
              "hotels": "accommodation.hotel,accommodation.hostel,accommodation.guest_house"}
SUCCESS = {"ok", "empty"}


def canonical(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value or "").casefold() if c.isalnum())


def select_city(rows, fixture, provider):
    """Explicit test fixture selection. Never pick the first ambiguous result."""
    names = {canonical(s) for s in fixture["aliases"]}
    matches = {}
    for row in rows:
        code = row.get("country_code") if provider == "open_meteo" else row.get("countryCode")
        feature = row.get("feature_code") if provider == "open_meteo" else row.get("fcode", "")
        if code != fixture["country"] or not feature.startswith("PPL") or feature == "PPLX":
            continue
        if fixture.get("capital") and feature != "PPLC":
            continue
        if not names.intersection(canonical(row.get(k)) for k in ("name", "asciiName", "toponymName")):
            continue
        key = row.get("id") if provider == "open_meteo" else row.get("geonameId")
        if key is not None:
            matches[key] = row
    return next(iter(matches.values())) if len(matches) == 1 else None


def valid_coordinates(lat, lon):
    return (isinstance(lat, (int, float)) and not isinstance(lat, bool) and math.isfinite(lat)
            and isinstance(lon, (int, float)) and not isinstance(lon, bool) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180)


def candidate_key(row):
    return row.get("provider"), ("osm:" + row["source_external_id"]
                                  if row.get("source_provider") == "openstreetmap" and row.get("source_external_id")
                                  else row.get("external_id"))


def compare_place_identity(before, after):
    expected, actual = geoapify_osm_reference(before), geoapify_osm_reference(after)
    if expected and actual:
        return ("pass", f"Same source object {expected}") if expected == actual else ("fail", "Different OSM source objects")
    first, second = before.get("properties", {}).get("place_id"), after.get("properties", {}).get("place_id")
    if first and first == second:
        return "pass", "Same lookup ID; stable source reference not exposed in both responses"
    return "warn", "Lookup IDs differ and source identity is missing; names/coordinates alone do not prove identity"


def filter_candidates(rows, rejected):
    """Local card-scoped filtering by provider + ID. No external API exclusion claim."""
    output, seen = [], set()
    for row in rows:
        key = candidate_key(row)
        if not all(key) or key in seen or key in rejected:
            continue
        if not valid_coordinates(row.get("latitude"), row.get("longitude")):
            continue
        seen.add(key)
        output.append(row)
    return output


def category_matches(feature, requested):
    actual = (feature.get("properties") or {}).get("categories") or []
    return any(a == prefix or a.startswith(prefix + ".") for a in actual for prefix in requested.split(","))


def request_plan(city_keys, core_only=False):
    # Per city: 1 Open-Meteo + 1 GeoNames + 5 POI. CountryInfo once per country.
    core = 7 * len(city_keys) + len({CITIES[k]["country"] for k in city_keys})
    # RU search twice; ambiguity/unambiguous/unknown; empty name + vegetarian; 2 details.
    return core + (0 if core_only else 9)


class ExtendedSurvey(Survey):
    def __init__(self, args):
        super().__init__(args)
        self.context = {"scenario": "extended_v2", "cities": args.cities, "radius_metres": args.radius,
                        "limit": args.limit, "core_only": args.core_only,
                        "request_cap": args.max_requests, "planned_max_requests": 5 if getattr(args, "details_only", False) else request_plan(args.cities, args.core_only),
                        "details_only": getattr(args, "details_only", False),
                        "coordinates": {}, "no_hotel_offer_queries": True}
        self.checks, self.pois, self.selected = [], {}, {}
        self.network_attempts = 0
        self.geo_key = "" if args.no_keys else os.getenv("GEOAPIFY_API_KEY", "")
        self.username = "" if args.no_keys else os.getenv("GEONAMES_USERNAME", "")
        self.geo_gate = ("Missing GEOAPIFY_API_KEY" if not self.geo_key else
                         "Free plan not confirmed (GEOAPIFY_FREE_PLAN=1)" if os.getenv("GEOAPIFY_FREE_PLAN") != "1" else None)
        self.names_gate = "Missing GEONAMES_USERNAME" if not self.username else "demo forbidden" if self.username == "demo" else None

    def check(self, name, status, detail, evidence):
        self.checks.append({"name": name, "status": status, "detail": detail, "evidence": evidence})

    def checked_call(self, provider, name, endpoint, params, selector, normalizer=None, kind=None, gate=None):
        selected = not self.args.providers or provider in self.args.providers
        will_send = not self.args.offline and selected and not gate and provider not in self.client.blocked
        if will_send and self.network_attempts >= self.args.max_requests:
            gate = "Request cap reached"
        if will_send and not gate:
            self.network_attempts += 1
        rows = self.call(provider, name, endpoint, params, selector, normalizer, kind, gate)
        result = self.results[-1]
        evidence = f"{provider}/{name}"
        if result["status"] == "skipped":
            self.check(evidence + "/response", "skipped", result["reason"], "not_called")
        elif result["status"] in SUCCESS:
            self.check(evidence + "/response", "pass", f"HTTP {result['http_status']}; objects={result['count']}", evidence)
        else:
            self.check(evidence + "/response", "fail", f"{result['status']}; HTTP={result['http_status']}; {result.get('reason', '')}", evidence)
        return rows, result

    def city_search(self, name, query, country=None, language="en", provider="open_meteo", gate=None):
        if provider == "open_meteo":
            params = {"name": query, "count": 10, "language": language}
            if country:
                params["countryCode"] = country
            return self.checked_call(provider, name, "https://geocoding-api.open-meteo.com/v1/search", params,
                                     lambda d: d.get("results", []), self.normalize_city)
        params = {"name_equals": query, "maxRows": 10, "featureClass": "P", "style": "FULL", "lang": language,
                  "username": self.username}
        if country:
            params["country"] = country
        return self.checked_call(provider, name, "https://secure.geonames.org/searchJSON", params,
                                 lambda d: d["geonames"], lambda r: normalize_geonames(r, "city", self.received_at),
                                 "geonames", gate=self.names_gate or gate)

    def normalize_city(self, r):
        return {**dict.fromkeys(FIELDS), **{k: r.get(k) for k in ("name", "latitude", "longitude", "country_code", "timezone")},
                "provider": "open_meteo", "external_id": r.get("id"), "category": "city",
                "source_url": "https://open-meteo.com/en/docs/geocoding-api", "retrieved_at": self.received_at}

    def places(self, name, category, coords, extra=None):
        lon, lat = (coords[1], coords[0]) if coords else (None, None)
        params = {"categories": CATEGORIES[category], "filter": f"circle:{lon},{lat},{self.args.radius}",
                  "limit": self.args.limit, "lang": "en", "apiKey": self.geo_key}
        params.update(extra or {})
        rows, result = self.checked_call("geoapify", name, "https://api.geoapify.com/v2/places", params,
                                       lambda d: d["features"], lambda r: normalize_geoapify(r, category, self.received_at),
                                       "geoapify", gate=self.geo_gate or (None if coords else "No unambiguous verified city coordinates"))
        if result["status"] in SUCCESS:
            self.check(name + "/limit", "pass" if len(rows) <= self.args.limit else "fail", f"N={len(rows)}, limit={self.args.limit}", "live_http")
            self.check(name + "/categories", "pass" if all(category_matches(r, params["categories"]) for r in rows) else "fail",
                       "All returned categories match a requested prefix; empty set is checked separately", "live_http")
            if not rows and "name" not in params:
                self.check(name + "/coverage", "warn", "No objects in this radius; not proof that city has no such places", "live_http")
        normalized = [normalize_geoapify(r, category, self.received_at) for r in rows]
        if rows:
            keys = [(r.get("provider"), r.get("external_id")) for r in normalized]
            self.check(name + "/identity_coordinates", "pass" if len(set(keys)) == len(keys) and all(
                r["external_id"] and valid_coordinates(r["latitude"], r["longitude"]) for r in normalized) else "fail",
                "Provider IDs are present/unique and WGS84 coordinates valid", "live_http")
            self.check(name + "/country", "pass" if all((r.get("country_code") or "").upper() == self.current_country for r in normalized) else "warn",
                       f"Expected country {self.current_country}; missing metadata requires review", "live_http")
        return rows, normalized, result

    def rejection_checks(self, name, normalized):
        if not normalized:
            self.check(name + "/rejections", "skipped", "No live candidates for local rejection check", "not_measured")
            return
        base = filter_candidates(normalized, set())
        rejected = {candidate_key(base[0])} if base else set()
        remaining = filter_candidates(normalized, rejected)
        other_card = filter_candidates(normalized, set())
        self.check(name + "/card_scope", "pass" if len(remaining) == len(base) - 1 and other_card == base else "fail",
                   "Reject first live ID in card A; card B retains it; no extra provider call", "local_on_live_candidates")
        all_rejected = {candidate_key(r) for r in base}
        self.check(name + "/all_rejected", "pass" if filter_candidates(normalized, all_rejected) == [] else "fail",
                   "Empty list when all sampled candidates rejected; no infinite refill/retry", "local_on_live_candidates")

    def run(self):
        if getattr(self.args, "details_only", False):
            return self.run_details_only()
        countries = {}
        for key in self.args.cities:
            fixture = CITIES[key]
            om, om_result = self.city_search(key + "_city", fixture["query"], fixture["country"])
            gn, gn_result = self.city_search(key + "_city", fixture["query"], fixture["country"], provider="geonames")
            chosen_om, chosen_gn = select_city(om, fixture, "open_meteo"), select_city(gn, fixture, "geonames")
            for provider, chosen, result in (("open_meteo", chosen_om, om_result), ("geonames", chosen_gn, gn_result)):
                if result["status"] in SUCCESS:
                    self.check(key + "/" + provider + "/unambiguous", "pass" if chosen else "fail",
                               "Exactly one named populated-place candidate expected; no first-result fallback", "live_http")
            if chosen_om:
                coords = chosen_om["latitude"], chosen_om["longitude"]
                self.selected[key] = chosen_om
                self.context["coordinates"][key] = {"latitude": coords[0], "longitude": coords[1], "source": "open_meteo", "id": chosen_om["id"]}
                tz = chosen_om.get("timezone")
                # tzdata may be absent on Windows. Never pretend ZoneInfo validation ran.
                available = available_timezones()
                self.check(key + "/iana", "pass" if tz in available else "warn",
                           f"timezone={tz}; local IANA database {'available' if available else 'not installed'}", "live_http+local_zoneinfo")
            else:
                coords = None
            if chosen_om and chosen_gn:
                self.check(key + "/provider_agreement", "pass" if chosen_om["id"] == chosen_gn["geonameId"] else "warn",
                           "Compare shared GeoNames ID; these geocoders are not independent datasets", "live_http")
            country = fixture["country"]
            if country not in countries:
                values, result = self.checked_call("geonames", country + "_country", "https://secure.geonames.org/countryInfoJSON",
                                                   {"country": country, "username": self.username}, lambda d: d["geonames"],
                                                   lambda r: normalize_geonames(r, "country", self.received_at), "geonames", gate=self.names_gate)
                countries[country] = values
                if result["status"] in SUCCESS:
                    expected = {"FR": "EUR", "RU": "RUB", "TR": "TRY"}[country]
                    self.check(country + "/currency", "pass" if len(values) == 1 and values[0].get("countryCode") == country
                               and values[0].get("currencyCode") == expected else "fail",
                               f"Fixture expectation {country}/{expected}; reference currency, not hotel offer currency", "live_http")
            self.current_country = country
            for category in CATEGORIES:
                raw, normalized, result = self.places(key + "_" + category, category, coords)
                self.pois[(key, category)] = (raw, normalized)
                self.rejection_checks(key + "_" + category, normalized)
        if not self.args.core_only:
            self.edge_cases()
        self.context["attempted_requests"] = self.network_attempts
        self.save()
        self.save_assessment()

    def edge_cases(self):
        fixture = CITIES["moscow"]
        for provider in ("open_meteo", "geonames"):
            rows, result = self.city_search("russian_name", "Москва", "RU", language="ru", provider=provider)
            if result["status"] in SUCCESS:
                self.check(provider + "/cyrillic", "pass" if select_city(rows, fixture, provider) else "fail",
                           "Cyrillic query resolves the expected populated place", "live_http")
        rows, result = self.city_search("ambiguous_name", "Springfield")
        if result["status"] in SUCCESS:
            self.check("city/ambiguity", "pass" if len({r.get('id') for r in rows}) > 1 else "warn",
                       f"{len(rows)} candidates: product should request a selection, not assume first result", "live_http")
        rows, result = self.city_search("country_filter", "Springfield", "US")
        if result["status"] in SUCCESS:
            self.check("city/country_filter", "pass" if rows and all(r.get("country_code") == "US" for r in rows) else "fail",
                       "Explicit US filter; returned IDs remain candidates", "live_http")
        rows, result = self.city_search("unknown_city", "TripFlowNoSuchCity9f71b2")
        if result["status"] in SUCCESS:
            self.check("city/empty", "pass" if rows == [] else "warn", "Deliberately unknown query; inspect any unexpected real matches", "live_http")
        # Prefer Paris when selected, otherwise first successfully verified selected city.
        key = "paris" if "paris" in self.selected else next(iter(self.selected), None)
        coords = None
        if key:
            city = self.selected[key]
            coords = city["latitude"], city["longitude"]
        self.current_country = CITIES[key]["country"] if key else "FR"
        _, _, result = self.places("empty_place_name", "museums", coords, {"name": "TripFlowNoSuchMuseum9f71b2"})
        if result["status"] in SUCCESS:
            self.check("poi/empty", "pass" if result["count"] == 0 else "warn", "Unknown name with valid category and coordinates", "live_http")
        rows, _, result = self.places("vegetarian_restaurants", "restaurants", coords, {"conditions": "vegetarian"})
        if result["status"] in SUCCESS:
            if rows:
                self.check("poi/condition", "pass" if all("vegetarian" in (r.get("properties", {}).get("categories") or [])
                           or (r.get("properties", {}).get("datasource", {}).get("raw", {}).get("diet:vegetarian") in ("yes", "only")) for r in rows) else "warn",
                           "Validate vegetarian metadata when exposed; acceptance of filter alone proves less", "live_http")
            else:
                self.check("poi/condition", "warn", "No matching objects in radius; filter accepted, quality not measured", "live_http")
        self.detail_checks(key)

    def detail_checks(self, key):
        for category in ("hotels", "restaurants"):
            raw = self.pois.get((key, category), ([], []))[0]
            identifier = (raw[0].get("properties") or {}).get("place_id") if raw else None
            rows, result = self.checked_call("geoapify", category + "_details", "https://api.geoapify.com/v2/place-details",
                                             {"id": identifier, "features": "details", "apiKey": self.geo_key},
                                             lambda d: [r for r in d["features"] if r.get("properties", {}).get("feature_type") == "details"],
                                             lambda r, c=category: normalize_geoapify(r, c, self.received_at), "geoapify",
                                             gate=self.geo_gate or (None if identifier else "No verified place ID"))
            if result["status"] in SUCCESS:
                status, detail = compare_place_identity(raw[0], rows[0]) if len(rows) == 1 else ("fail", "Expected exactly one details feature")
                self.check(category + "/detail_identity", status, detail, "live_http")
                if len(rows) == 1 and rows[0]["properties"].get("place_id") != identifier:
                    self.check(category + "/lookup_id_changed", "warn", "Opaque place_id changed; retain source OSM type/id and lookup ID aliases", "live_http")

    def run_details_only(self):
        key = self.args.cities[0]
        fixture = CITIES[key]
        rows, _ = self.city_search(key + "_city", fixture["query"], fixture["country"])
        chosen = select_city(rows, fixture, "open_meteo")
        coords = (chosen["latitude"], chosen["longitude"]) if chosen else None
        if chosen:
            self.context["coordinates"][key] = {"latitude": coords[0], "longitude": coords[1], "source": "open_meteo", "id": chosen["id"]}
        self.current_country = fixture["country"]
        for category in ("hotels", "restaurants"):
            raw, normalized, _ = self.places(key + "_" + category, category, coords)
            self.pois[(key, category)] = raw, normalized
            self.rejection_checks(key + "_" + category, normalized)
        self.detail_checks(key)
        self.context["attempted_requests"] = self.network_attempts
        self.save()
        self.save_assessment()

    def save_assessment(self):
        out = ROOT / "reports" / "runs" / self.run_id
        document = scrub({"run_id": self.run_id, "checks": self.checks, "context": self.context}, self.secrets)
        (out / "checks.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        counts = Counter(c["status"] for c in self.checks)
        lines = ["# Расширенная проверка источников", "", f"Run `{self.run_id}`. UTC {self.now}.",
                 f"Проверки: pass={counts['pass']}, warn={counts['warn']}, fail={counts['fail']}, skipped={counts['skipped']}.",
                 f"Сетевых попыток: {self.network_attempts}; предел {self.args.max_requests}. Все последовательно.", "",
                 "[Полные запросы и поля](live-results.md) · [JSON результатов](results.json) · [Проверки JSON](checks.json)", "",
                 "HTTP 200 проверяется отдельно от полноты данных. warn = ограничение/нужна проверка, fail = ожидание не выполнено.",
                 "Пустая корректная выдача не ошибка транспорта. Повторных запросов для замены отклонённых объектов нет.", "",
                 "## Заполненность POI", "", "Доли по всем объектам запроса. Сохранены только 2 примера на endpoint.", "",
                 "| Запрос | N | Название | Адрес | Сайт | Фото | Описание | Кухня | Часы | Цена | Наличие |",
                 "|---|---:|---|---|---|---|---|---|---|---|---|"]
        for r in self.results:
            if r["provider"] != "geoapify" or r["status"] not in SUCCESS:
                continue
            values = []
            for field in ("name", "address", "website_url", "image_url", "description", "cuisine", "opening_hours", "price_amount", "availability"):
                stats = r["coverage"].get(field, {"filled": 0, "total": 0})
                values.append(f"{stats['filled']}/{stats['total']}" if stats["total"] else "не измерено")
            lines.append(f"| {r['name']} | {r['count']} | " + " | ".join(values) + " |")
        lines.extend(["", "## Проверки", "", "| Проверка | Результат | Подробности | Тип доказательства |", "|---|---|---|---|"])
        for c in document["checks"]:
            lines.append("| " + " | ".join(str(c[k]).replace("|", "\\|").replace("\n", " ") for k in ("name", "status", "detail", "evidence")) + " |")
        lines.extend(["", "## Пределы", "", "Это небольшие выборки в радиусе, не полный список городских объектов. Категории — фильтры поставщика; качество описаний/фото не гарантируется.",
                      "Отсутствие prices/availability не исправляется успешным HTTP. CountryInfo currency — валюта страны, не цена отеля.",
                      "Геокодеры Open-Meteo и GeoNames используют общую основу; совпадение не независимая проверка географии.",
                      "Отклонения/dedup проверены локально на живой выборке. Кэш/TTL/публикация карточки/повторный подбор production-приложения здесь не реализованы.",
                      "Время ответа — наблюдение этого запуска; повторов для статистики задержек не было. Overpass, партнёрские и визовые API не вызываются."])
        (out / "assessment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\nREADABLE SUMMARY:", out / "assessment.md")


def main(argv=None):
    p = argparse.ArgumentParser(description="Bounded four-city survey, existing local free credentials only")
    p.add_argument("--cities", nargs="+", choices=list(CITIES), default=list(CITIES))
    p.add_argument("--core-only", action="store_true", help="City/catalog checks without edge-case requests")
    p.add_argument("--details-only", action="store_true", help="Targeted identity check: one selected city, two searches + two details")
    p.add_argument("--providers", nargs="+", choices=["open_meteo", "geonames", "geoapify"])
    p.add_argument("--no-keys", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--plan", action="store_true", help="Show maximum request counts; no network or saved run")
    p.add_argument("--limit", type=int, default=5, choices=range(1, 11))
    p.add_argument("--radius", type=int, default=3000, choices=range(500, 3001), metavar="500..3000")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--delay", type=float, default=2)
    p.add_argument("--max-requests", type=int, default=40, choices=range(1, 41))
    p.add_argument("--show-samples", action="store_true")
    args = p.parse_args(argv)
    if len(set(args.cities)) != len(args.cities):
        p.error("Do not repeat cities")
    if args.details_only and (len(args.cities) != 1 or args.core_only):
        p.error("--details-only needs exactly one city (e.g. --cities paris), without --core-only")
    if not 1 <= args.timeout <= 30 or not 1 <= args.delay <= 30:
        p.error("timeout/delay must be 1..30 seconds")
    if args.plan:
        print(json.dumps({"cities": args.cities, "planned_max_requests": 5 if args.details_only else request_plan(args.cities, args.core_only),
                          "hard_cap": args.max_requests, "poi_limit": args.limit, "network": False}, indent=2))
        return 0
    if not args.no_keys:
        load_env(ROOT / ".env")
    survey = ExtendedSurvey(args)
    survey.run()
    # Exit 0 = reports saved. Read checks.json for per-scenario pass/warn/fail.
    return 0

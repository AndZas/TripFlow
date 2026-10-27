"""Bounded, read-only enrichment experiment. No third-party dependencies."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import re
import time
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "reports" / "runs"
DATATOURISME_ORIGIN = "https://api.datatourisme.fr"
WIKIDATA_ORIGIN = "https://www.wikidata.org"
COMMONS_ORIGIN = "https://commons.wikimedia.org"
FIELDS = ("name", "description", "category", "coordinates", "address", "opening_hours", "website",
          "image_url", "image_usable", "admission_price_amount", "activity_price_amount",
          "hotel_price_amount", "price_currency", "price_basis", "price_period_or_validity",
          "is_free", "price_source_url", "price_updated_at")
CITIES = {"Paris": (48.8566, 2.3522), "Lyon": (45.7640, 4.8357), "Bordeaux": (44.8378, -0.5792)}
REFERENCE = Path(__file__).resolve().parents[1] / "data-source-survey" / "data" / "samples" / "20261015T150210175612Z"


def useful(value):
    return value is not None and value != "" and value != [] and value != {}


def first(value):
    if isinstance(value, list):
        return first(value[0]) if value else None
    if isinstance(value, dict):
        for key in ("fr", "en", "@fr", "@en", "value", "label", "text", "name", "description", "shortDescription", "longDescription"):
            if key in value:
                found = first(value[key])
                if useful(found):
                    return found
        return None
    return value


def obj(value):
    return value if isinstance(value, dict) else {}


def nested(value, keys, depth=0):
    if depth > 5:
        return None
    if isinstance(value, dict):
        for key in keys:
            if useful(value.get(key)):
                return value[key]
        for child in value.values():
            found = nested(child, keys, depth + 1)
            if useful(found):
                return found
    elif isinstance(value, list):
        for child in value:
            found = nested(child, keys, depth + 1)
            if useful(found):
                return found
    return None


def seq(value):
    return value if isinstance(value, list) else ([value] if useful(value) else [])


def clean_url(value):
    if not isinstance(value, str):
        return None
    parts = parse.urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    return parse.urlunsplit(("https", parts.netloc, parts.path, "", ""))


def number(value):
    try:
        n = Decimal(str(value))
        return str(n) if n.is_finite() and n >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def coords(value):
    value = obj(value)
    if value.get("type") == "Point" and len(seq(value.get("coordinates"))) >= 2:
        lon, lat = value["coordinates"][:2]
    else:
        lat = value.get("latitude", value.get("lat"))
        lon = value.get("longitude", value.get("lon"))
    try:
        lat, lon = float(lat), float(lon)
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return [lat, lon]
    except (TypeError, ValueError):
        pass
    return None


def distance_m(a, b):
    p1, p2 = map(math.radians, (a[0], b[0]))
    dp, dl = p2-p1, math.radians(b[1]-a[1])
    return 12742000 * math.asin(min(1, math.sqrt(math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2)))


def norm_name(value):
    return re.sub(r"[^\w]+", " ", str(value or "").casefold()).strip()


def references():
    found = []
    if not REFERENCE.is_dir():
        return found
    for name in ("geoapify_paris_museums.json", "geoapify_paris_historic.json", "geoapify_paris_nature.json"):
        path = REFERENCE / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for feature in seq(data.get("raw")):
            p = obj(obj(feature).get("properties"))
            point = coords({"latitude": p.get("lat"), "longitude": p.get("lon")}) or coords(feature.get("geometry"))
            if p.get("name") and point:
                found.append({"name": p["name"], "coordinates": point,
                              "type": "museum" if "museum" in name else "poi",
                              "wikidata": obj(p.get("wiki_and_media")).get("wikidata"),
                              "baseline_photo": bool(obj(p.get("wiki_and_media")).get("image")),
                              "baseline_description": bool(p.get("description")),
                              "reference_file": name})
    return found


def match(item, refs):
    name, point = norm_name(item.get("name")), item.get("coordinates")
    qid = item.get("wikidata")
    scored = []
    for ref in refs:
        if qid and qid == ref.get("wikidata"):
            d = round(distance_m(point, ref["coordinates"])) if point else None
            # A copied but wrong Wikidata tag is possible; verify the place itself.
            same_name = name == norm_name(ref["name"]) or name in norm_name(ref["name"]) or norm_name(ref["name"]) in name
            scored.append(("confident" if same_name and d is not None and d <= 150 else "possible", ref, d))
        elif name and point and name == norm_name(ref["name"]):
            d = distance_m(point, ref["coordinates"])
            if d <= 150:
                scored.append(("confident", ref, round(d)))
            elif d <= 500:
                scored.append(("possible", ref, round(d)))
        elif name and point and name.startswith(norm_name(ref["name"])):
            d = distance_m(point, ref["coordinates"])
            if d <= 150:
                scored.append(("possible", ref, round(d)))
    confident = [x for x in scored if x[0] == "confident"]
    if len(confident) == 1:
        quality, ref, d = confident[0]
        return {"confidence": quality, "reference": ref["name"], "distance_m": d}
    if scored:
        return {"confidence": "ambiguous" if len(scored) > 1 else "possible", "reference": None}
    return {"confidence": "none", "reference": None}


def match_items(items, refs):
    for item in items:
        item["match"] = match(item, refs)
    # More than one provider record for one baseline object cannot be attached automatically.
    names = Counter(obj(item.get("match")).get("reference") for item in items
                    if obj(item.get("match")).get("confidence") == "confident")
    for item in items:
        m = obj(item.get("match"))
        if m.get("confidence") == "confident" and names[m.get("reference")] > 1:
            m["confidence"] = "ambiguous"
    return items


class Client:
    def __init__(self, args):
        self.args = args
        self.used = 0
        self.last = 0.0
        self.blocked = set()

    def call(self, provider, origin, path, params=None, headers=None):
        if provider == "amadeus":
            raise ValueError("Amadeus Self-Service closed; live calls disabled")
        allowed = {"datatourisme": DATATOURISME_ORIGIN,
                   "wikimedia": (WIKIDATA_ORIGIN, COMMONS_ORIGIN)}
        if origin not in ((allowed[provider],) if isinstance(allowed[provider], str) else allowed[provider]):
            raise ValueError("Unapproved host")
        prefixes = {"datatourisme": ("/v1/catalog", "/v1/placeOfInterest", "/v1/entertainmentAndEvent"),
                    "wikimedia": ("/w/api.php",)}
        if not any(path == p or path.startswith(p + "?") for p in prefixes[provider]):
            raise ValueError("Unapproved endpoint")
        if provider in self.blocked:
            return {"status": "skipped_provider_stopped", "http_status": None, "latency_ms": None, "data": None}
        if self.used >= self.args.max_requests:
            return {"status": "skipped_request_cap", "http_status": None, "latency_ms": None, "data": None}
        wait = self.args.delay_seconds - (time.monotonic() - self.last)
        if self.last and wait > 0:
            time.sleep(wait)
        url = origin + path + ("?" + parse.urlencode(params) if params else "")
        req = request.Request(url, headers=headers or {}, method="GET")
        t0 = time.monotonic()
        self.used += 1
        try:
            # Do not follow redirects: credentials must remain on the approved host.
            class NoRedirect(request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            with request.build_opener(NoRedirect).open(req, timeout=self.args.timeout_seconds) as response:
                status = response.status
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Response size cap exceeded")
                data = json.loads(raw)
            result = {"status": "ok", "http_status": status, "data": data}
        except error.HTTPError as exc:
            status = exc.code
            if status in (401, 403, 429):
                self.blocked.add(provider)
            result = {"status": "error", "http_status": status, "data": None, "error_kind": "http"}
        except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            result = {"status": "error", "http_status": None, "data": None, "error_kind": type(exc).__name__}
        self.last = time.monotonic()
        result["latency_ms"] = round((self.last-t0)*1000)
        return result


def base_record(provider, city, category, endpoint, response, items):
    return {"provider": provider, "city": city, "category": category, "endpoint": endpoint,
            "status": response["status"], "http_status": response["http_status"],
            "latency_ms": response["latency_ms"], "result_count": len(items),
            "error_kind": response.get("error_kind"), "items": items}


def datatourisme_item(raw):
    raw = obj(raw)
    location = obj(seq(raw.get("isLocatedAt"))[0] if seq(raw.get("isLocatedAt")) else {})
    media = obj(seq(raw.get("hasMainRepresentation"))[0] if seq(raw.get("hasMainRepresentation")) else {})
    # Several levels of representation exist; preserve only clearly attributed direct URLs.
    image = clean_url(first(nested(media, ("url", "contentUrl"))))
    photo_credit = first(nested(media, ("credit", "copyright", "hasBeenCreatedBy")))
    offer = obj(seq(raw.get("offers"))[0] if seq(raw.get("offers")) else {})
    specs = [obj(s) for s in seq(offer.get("priceSpecification"))[:10]]
    tariffs = []
    for s in specs:
        period = obj(seq(s.get("appliesOnPeriod"))[0] if seq(s.get("appliesOnPeriod")) else {})
        end = period.get("endDate")
        expired = isinstance(end, str) and end < date.today().isoformat()
        tariffs.append({"min_price": number(first(s.get("minPrice"))),
                        "price": number(first(s.get("price"))),
                        "currency": s.get("priceCurrency"), "name": first(s.get("name")),
                        "start_date": period.get("startDate"), "end_date": end,
                        "expired": expired, "basis": first(s.get("eligibleQuantity"))})
    tariff = next((t for t in tariffs if useful(t["min_price"]) or useful(t["price"])), {})
    amount = tariff.get("price") or tariff.get("min_price")
    types = [str(x) for x in seq(raw.get("type"))]
    typ = ", ".join(types)
    hotel = any("Hotel" in x or "Accommodation" in x for x in types)
    contact = obj(seq(raw.get("hasContact"))[0] if seq(raw.get("hasContact")) else {})
    address = obj(seq(location.get("address"))[0] if seq(location.get("address")) else {})
    return {"source_fields": {"uuid": raw.get("uuid"), "label": raw.get("label"),
                              "type": raw.get("type"), "tariff_observations": tariffs,
                              "isAccessibleForFree": raw.get("isAccessibleForFree"),
                              "lastUpdate": raw.get("lastUpdate"),
                              "lastUpdateDatatourisme": raw.get("lastUpdateDatatourisme")},
            "source_id": raw.get("uuid"), "source_url": clean_url(raw.get("uri")),
            "name": first(raw.get("label")), "description": first(raw.get("hasDescription")),
            "category": typ, "coordinates": coords(location.get("geo")),
            "address": first(address.get("streetAddress")),
            "opening_hours": first(nested(location.get("openingHoursSpecification"), ("additionalInformation",))),
            "website": clean_url(first(contact.get("homepage"))),
            "image_url": image, "image_author": photo_credit, "image_license": first(media.get("license")),
            "image_source_page": clean_url(media.get("url")), "image_usable": False,
            "admission_price_amount": None,
            "activity_price_amount": None,
            "hotel_price_amount": amount if amount and hotel else None,
            "unclassified_price_amount": amount if amount and not hotel else None,
            "tariff_observations": tariffs, "price_currency": tariff.get("currency"), "price_basis": tariff.get("basis"),
            "price_period_or_validity": [tariff.get("start_date"), tariff.get("end_date")] if amount else None,
            "price_kind": ("expired_catalog_tariff" if tariff.get("expired") else "catalog_minimum_unknown_basis") if amount else None,
            "is_free": raw.get("isAccessibleForFree") if isinstance(raw.get("isAccessibleForFree"), bool) else None,
            "price_source_url": clean_url(first(offer.get("url"))), "price_updated_at": None,
            "attribution": first(nested(raw.get("hasBeenCreatedBy"), ("legalName", "label", "name"))),
            "last_update": first(raw.get("lastUpdate")),
            "catalog_updated_at": first(raw.get("lastUpdateDatatourisme"))}


def wikimedia_item(entity, image=None):
    claims = obj(entity.get("claims"))
    labels = obj(entity.get("labels"))
    descriptions = obj(entity.get("descriptions"))
    pic = obj(image)
    meta = obj(pic.get("extmetadata"))
    def mv(key): return obj(meta.get(key)).get("value")
    license_name = mv("LicenseShortName") or mv("License")
    author = mv("Artist")
    credit = mv("Credit")
    # extmetadata often contains HTML. Keep it for audit only after stripping tags.
    def plain(v): return re.sub(r"<[^>]*>", "", str(v))[:500] if useful(v) else None
    coordinates = None
    if seq(claims.get("P625")):
        value = obj(obj(seq(claims["P625"])[0]).get("mainsnak")).get("datavalue")
        coordinates = coords(obj(obj(value).get("value")))
    return {"source_fields": {"id": entity.get("id"), "label_fr": obj(labels.get("fr")).get("value"),
                              "label_en": obj(labels.get("en")).get("value"),
                              "description_fr": obj(descriptions.get("fr")).get("value"),
                              "description_en": obj(descriptions.get("en")).get("value"),
                              "license": plain(license_name), "artist": plain(author), "credit": plain(credit)},
            "source_id": entity.get("id"), "wikidata": entity.get("id"),
            "name": obj(labels.get("fr") or labels.get("en")).get("value"),
            "description": obj(descriptions.get("fr") or descriptions.get("en")).get("value"),
            "category": "poi", "coordinates": coordinates,
            "image_url": clean_url(pic.get("url")), "image_author": plain(author),
            "image_credit": plain(credit), "image_license": plain(license_name),
            "image_source_page": clean_url(pic.get("descriptionurl")),
            "image_width": pic.get("width"), "image_height": pic.get("height"),
            "image_usable": bool(pic.get("url") and license_name and author and pic.get("descriptionurl") and
                                 ("CC" in str(license_name) or "Public domain" in str(license_name))),
            "price_kind": None}


def run_datatourisme(client, args, records, refs):
    key = os.getenv("DATATOURISME_API_KEY", "")
    if not key:
        records.append(base_record("datatourisme", "France", "all", "/v1/catalog",
                                   {"status": "skipped_missing_config", "http_status": None, "latency_ms": None}, []))
        return
    fields = "uuid,uri,label,type,isLocatedAt,hasDescription,hasMainRepresentation,hasContact,offers,isAccessibleForFree,hasBeenCreatedBy,lastUpdate,lastUpdateDatatourisme"
    for city, (lat, lon) in CITIES.items():
        for category, endpoint in (("museum", "/v1/catalog"), ("tourist_site", "/v1/catalog"), ("hotel", "/v1/catalog")):
            # /catalog hotel sample is deliberately type-filtered to avoid arbitrary catalog pages.
            params = {"geo_distance": f"{lat},{lon},5km", "page_size": args.max_results, "lang": "fr,en", "fields": fields}
            params["filters"] = {"museum": "type[eq]=Museum", "tourist_site": "type[eq]=CulturalSite", "hotel": "type[eq]=Hotel"}[category]
            response = client.call("datatourisme", DATATOURISME_ORIGIN, endpoint, params,
                                   {"X-API-Key": key, "User-Agent": "TripFlow-EnrichmentTest/1.0"})
            items = [datatourisme_item(x) for x in seq(obj(response.get("data")).get("objects"))[:args.max_results]]
            match_items(items, refs)
            records.append(base_record("datatourisme", city, category, endpoint, response, items))
            if response["status"] in ("skipped_provider_stopped", "skipped_request_cap") or "datatourisme" in client.blocked:
                return
    # These are targeted probes, not part of the unbiased city/category coverage denominator.
    probes = [
        ("Paris", "targeted_museum", {"search": "Musée Curie", "geo_distance": "48.8442383,2.3447906,500m"}),
        ("Paris", "targeted_museum", {"search": "Bourse de Commerce", "geo_distance": "48.8628174,2.3428364,500m"}),
        ("Paris", "price_probe_museum", {"geo_distance": "48.8566,2.3522,5km", "filters": "type[eq]=Museum AND offers.priceSpecification.minPrice[exists]=true"}),
        ("Paris", "price_probe_hotel", {"geo_distance": "48.8566,2.3522,5km", "filters": "type[eq]=Hotel AND offers.priceSpecification.minPrice[exists]=true"}),
        ("Paris", "photo_probe_museum", {"geo_distance": "48.8566,2.3522,5km", "filters": "type[eq]=Museum AND hasMainRepresentation[exists]=true"}),
    ]
    for city, category, extra in probes:
        params = {"page_size": args.max_results, "lang": "fr,en", "fields": fields, **extra}
        response = client.call("datatourisme", DATATOURISME_ORIGIN, "/v1/catalog", params,
                               {"X-API-Key": key, "User-Agent": "TripFlow-EnrichmentTest/1.0"})
        items = [datatourisme_item(x) for x in seq(obj(response.get("data")).get("objects"))[:args.max_results]]
        match_items(items, refs)
        records.append(base_record("datatourisme", city, category, "/v1/catalog", response, items))
        if response["status"] in ("skipped_provider_stopped", "skipped_request_cap") or "datatourisme" in client.blocked:
            return


def run_amadeus(client, args, records, refs):
    # The Self-Service program closed in July 2026; retained as a documented CLI status.
    records.append(base_record("amadeus", "—", "all", "—",
                               {"status": "skipped_provider_unavailable", "http_status": None, "latency_ms": None}, []))


def run_wikimedia(client, args, records, refs):
    agent = os.getenv("WIKIMEDIA_USER_AGENT", "")
    if not agent or not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https://[^\s)]+|User:[^\s)]+", agent):
        records.append(base_record("wikimedia", "Paris", "poi", "/w/api.php",
                                   {"status": "skipped_missing_config", "http_status": None, "latency_ms": None}, []))
        return
    target = [r for r in refs if r.get("wikidata") and (not r["baseline_photo"] or not r["baseline_description"])][:3]
    if not target:
        records.append(base_record("wikimedia", "Paris", "poi", "/w/api.php",
                                   {"status": "skipped_no_reference", "http_status": None, "latency_ms": None}, []))
        return
    for ref in target:
        qid = ref["wikidata"]
        response = client.call("wikimedia", WIKIDATA_ORIGIN, "/w/api.php",
                               {"action": "wbgetentities", "ids": qid, "props": "labels|descriptions|claims", "languages": "fr|en", "format": "json"},
                               {"User-Agent": agent})
        entity = obj(obj(response.get("data")).get("entities")).get(qid)
        image = None
        if entity and response["status"] == "ok":
            claims = obj(entity.get("claims"))
            p18 = seq(claims.get("P18"))
            filename = obj(obj(obj(p18[0]).get("mainsnak")).get("datavalue")).get("value") if p18 else None
            if isinstance(filename, str) and filename:
                im_response = client.call("wikimedia", COMMONS_ORIGIN, "/w/api.php",
                                          {"action": "query", "titles": "File:" + filename, "prop": "imageinfo",
                                           "iiprop": "url|size|extmetadata", "format": "json"}, {"User-Agent": agent})
                pages = obj(obj(obj(im_response.get("data")).get("query")).get("pages"))
                image = seq(obj(next(iter(pages.values()), {})).get("imageinfo"))[0] if pages else None
        items = [wikimedia_item(entity, image)] if entity else []
        for item in items: item["match"] = match(item, refs)
        records.append(base_record("wikimedia", "Paris", "poi", "/w/api.php", response, items))
        if items and items[0]["match"]["confidence"] != "confident": return
        if "wikimedia" in client.blocked or response["status"] == "skipped_request_cap": return


def metrics(items):
    count = len(items)
    return {field: {"filled": sum((x.get(field) is True) if field == "image_usable" else
                                  (x.get(field) is not None if field == "is_free" else useful(x.get(field)))
                                  for x in items), "denominator": count} for field in FIELDS}


def render(records, run_id, ref_count, request_count):
    lines = [f"# Результаты {run_id}", "", f"Запросов: {request_count}. Сохранённый набор для match: {ref_count} Geoapify POI; только точный Wikidata ID либо нормализованное имя и расстояние ≤150 м дают уверенный match.",
             "", "| Провайдер | Город | Тип | Статус | HTTP | мс | Объектов | Уверенных/возможных/неоднозначных |",
             "|---|---|---|---|---:|---:|---:|---:|"]
    for r in records:
        counts = Counter(obj(x.get("match")).get("confidence", "none") for x in r["items"])
        lines.append(f"| {r['provider']} | {r['city']} | {r['category']} | {r['status']} | {r['http_status'] or '—'} | {r['latency_ms'] if r['latency_ms'] is not None else '—'} | {r['result_count']} | {counts['confident']}/{counts['possible']}/{counts['ambiguous']} |")
    lines += ["", "## Заполненность по фактическим объектам", "", "Значения `filled/denominator`; отсутствие объектов означает `0/0`, не нулевое покрытие каталога.", ""]
    for r in records:
        m = metrics(r["items"])
        lines.append(f"### {r['provider']} / {r['city']} / {r['category']}")
        lines.append("; ".join(f"{k}: {v['filled']}/{v['denominator']}" for k, v in m.items()))
        items = r["items"]
        admiss = [x for x in items if obj(x.get("match")).get("confidence") == "confident"]
        priced = [x for x in items if any(useful(x.get(k)) for k in ("admission_price_amount", "activity_price_amount", "hotel_price_amount", "unclassified_price_amount"))]
        lines.append(f"Цена: вход {sum(useful(x.get('admission_price_amount')) for x in items)}/{len(items)}, "
                     f"активность {sum(useful(x.get('activity_price_amount')) for x in items)}/{len(items)}, "
                     f"жильё {sum(useful(x.get('hotel_price_amount')) for x in items)}/{len(items)}, "
                     f"неопределённый тариф {sum(useful(x.get('unclassified_price_amount')) for x in items)}/{len(items)}; "
                     f"валюта {sum(useful(x.get('price_currency')) for x in priced)}/{len(priced)}, "
                     f"известная база {sum(useful(x.get('price_basis')) for x in priced)}/{len(priced)}, "
                     f"истёкший срок {sum(x.get('price_kind') == 'expired_catalog_tariff' for x in priced)}/{len(priced)}. "
                     "Надёжная RUB/чел/ночь нормализация: 0 (курс и налоговая база в этом тесте не подтверждались).")
        lines.append(f"На уверенно сопоставленных {len(admiss)} объектах: описание "
                     f"{sum(useful(x.get('description')) for x in admiss)}/{len(admiss)}, "
                     f"фото с метаданными {sum(x.get('image_usable') is True for x in admiss)}/{len(admiss)}. "
                     f"Не засчитаны как уверенное обогащение: {len(items)-len(admiss)} из {len(items)} (включая записи без совпадения).")
        lines.append("")
    lines += ["Цены Amadeus — sandbox fixtures. Цена активности не равна входному билету. `image_usable` требует явных лицензии, автора и страницы файла; для DATAtourisme права фото требуют отдельной проверки. Пересчёт в RUB не выполняется без подтверждённой исходной цены и её единицы.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--live", action="store_true")
    p.add_argument("--providers", nargs="+", choices=("datatourisme", "amadeus", "wikimedia"), default=["datatourisme", "amadeus", "wikimedia"])
    p.add_argument("--max-requests", type=int, default=18)
    p.add_argument("--max-results", type=int, default=5)
    p.add_argument("--delay-seconds", type=float, default=1.0)
    p.add_argument("--timeout-seconds", type=float, default=15.0)
    args = p.parse_args()
    if not (1 <= args.max_requests <= 24 and 1 <= args.max_results <= 10 and 1 <= args.delay_seconds <= 20 and 2 <= args.timeout_seconds <= 30):
        p.error("Limits: requests 1..24, results 1..10, delay 1..20 s, timeout 2..30 s")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "samples").mkdir()
    refs = references()
    client = Client(args)
    records = []
    for provider in dict.fromkeys(args.providers):
        if args.offline:
            records.append(base_record(provider, "—", "—", "—", {"status": "skipped_offline", "http_status": None, "latency_ms": None}, []))
        else:
            {"datatourisme": run_datatourisme, "amadeus": run_amadeus, "wikimedia": run_wikimedia}[provider](client, args, records, refs)
    # Only allowlisted normalized data is persisted; no response body, OAuth token, header or secret.
    for idx, record in enumerate(records):
        for j, item in enumerate(record["items"][:2]):
            (run_dir / "samples" / f"{idx:02d}_{j:02d}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    data = {"run_id": run_id, "mode": "offline" if args.offline else "live", "version": "1.0",
            "reference_path": str(REFERENCE), "reference_count": len(refs), "requests": client.used,
            "limits": {"max_requests": args.max_requests, "max_results": args.max_results,
                       "delay_seconds": args.delay_seconds, "timeout_seconds": args.timeout_seconds},
            "records": [{**r, "coverage": metrics(r["items"])} for r in records]}
    (run_dir / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "live-results.md").write_text(render(records, run_id, len(refs), client.used), encoding="utf-8")
    print(f"Run: {run_id}; requests: {client.used}; records: {len(records)}; report: {run_dir / 'live-results.md'}")


if __name__ == "__main__":
    main()

"""Live candidate selection and official-site evidence evaluation."""

import argparse
import json
import math
import os
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from analyze import analyze, search_query
from evidence import judge, parse_html, retrieve
from source_reader import Reader


ROOT = Path(__file__).resolve().parent
GEO = {"museums": "entertainment.museum", "parks": "leisure.park", "historic": "tourism.sights"}
AMENITIES = {
    "restaurant": "В самом отеле есть собственный ресторан",
    "parking": "У отеля есть парковка для гостей",
    "wifi": "В отеле доступен Wi-Fi для гостей",
}


def read_json(request):
    with urlopen(request, timeout=16) as response:
        return json.load(response)


def hotel_candidates(destination, nights, travelers, maximum, *, pages=1, breakfast=None):
    city = destination["city"]
    center = destination["coordinates"]
    seen = set()
    limit = 20 if pages > 1 else 12
    for page in range(pages):
        request = Request("https://russhotels.ru/api/hotel/index",
                          urlencode({"city_name": city, "limit": limit, "offset": page * limit}).encode())
        rows = read_json(request)
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            candidate = hotel_from_row(row, destination, center, nights, travelers, maximum, breakfast)
            if candidate:
                yield candidate
        if len(rows) < limit:
            break


def hotel_from_row(row, destination, center, nights, travelers, maximum, breakfast):
    city = destination["city"]
    if (row.get("city") or {}).get("name", "").casefold() != city.casefold():
        return None
    address = row.get("address") or ""
    if not address or (city == "Москва" and "московская область" in address.casefold()):
        return None
    try:
        lat, lon = float(row["geo_lat"]), float(row["geo_lon"])
    except (ValueError, KeyError, TypeError):
        return None
    km = math.hypot(lat - center["latitude"],
                    (lon - center["longitude"]) * math.cos(math.radians(lat))) * 111
    if not math.isfinite(km) or km > 23:
        return None
    rooms = []
    for room in row.get("rooms") or []:
        price = room.get("price_client")
        if (str((room.get("placement_type") or {}).get("id")) != "1"
                or type(price) is not int or price <= 0):
            continue
        amount = price * nights * travelers
        if maximum is not None and amount > maximum:
            continue
        meal = (room.get("food_type") or {}).get("name") or ""
        meal_text = meal.casefold()
        excluded = re.search(r"нет питания|без завтрака|без питания|за доплату|не включ[её]н", meal_text)
        includes = "завтрак" in meal_text or "полный пансион" in meal_text
        meal_status = "contradicted" if excluded else "confirmed" if includes else "unknown"
        actual = meal_status == "confirmed" if meal_status != "unknown" else None
        if breakfast and breakfast["required"] and actual is not breakfast["included"]:
            continue
        rooms.append((bool(breakfast and actual is not breakfast["included"]), amount, room, meal, meal_status))
    if not rooms:
        return None
    _, amount, room, meal, meal_status = min(rooms, key=lambda item: item[:2])
    return {"id": str(row["id"]), "name": row["name"], "address": address, "city": city,
            "region": destination.get("regionName"), "indicativeGroupRub": amount, "source": "Russhotels",
            "description": " ".join(parse_html(row.get("hotel_description") or "")[0])[:900],
            "checkIn": row.get("check_in"), "checkOut": row.get("check_out"), "room": room.get("name"),
            "meal": meal or None, "breakfastStatus": meal_status,
            "nightlyPersonRub": room["price_client"]}


def place_candidates(destination, filters, count, *, free=None):
    key = os.environ.get("GEOAPIFY_API_KEY")
    if not key:
        raise ValueError("GEOAPIFY_API_KEY is required")
    rules = [f for f in filters if f["kind"] == "attraction_category"]
    required = [f["value"] for f in rules if not f["excluded"] and f["strength"] == "required"]
    preferred = {f["value"] for f in rules if not f["excluded"]}
    excluded = {f["value"] for f in rules if f["excluded"] and f["strength"] == "required"}
    avoided = {f["value"] for f in rules if f["excluded"]}
    search_categories = [GEO[value] for value in (required or GEO) if value not in excluded]
    if not search_categories:
        return []
    center = destination["coordinates"]
    params = {"categories": ",".join(search_categories), "lang": "ru",
              "filter": f"circle:{center['longitude']},{center['latitude']},16000",
              "bias": f"proximity:{center['longitude']},{center['latitude']}",
              "limit": min(count * 5, 100), "apiKey": key}
    try:
        url = "https://api.geoapify.com/v2/places?"
        features = read_json(url + urlencode({**params, "conditions": "no_fee.no"}))["features"] if free else []
        if free != "required":
            features += read_json(url + urlencode(params))["features"]
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Geoapify request failed ({type(error).__name__})") from None
    result = {}
    for row in features:
        p = row["properties"]
        if not p.get("place_id") or not p.get("name") or (p.get("city") or "").casefold() != destination["city"].casefold():
            continue
        categories = p.get("categories") or []
        matches = {value for value, prefix in GEO.items() if any(
            category == prefix or category.startswith(prefix + ".") for category in categories
        )}
        if not matches or matches & excluded or required and not matches.intersection(required):
            continue
        raw = (p.get("datasource") or {}).get("raw") or {}
        status, price = admission(raw, categories)
        if free == "required" and status != "free":
            continue
        rank = (free is not None and status != "free", len(matches & avoided), -len(matches & preferred))
        result.setdefault(p["place_id"], (rank, {
            "id": p["place_id"], "name": p["name"], "address": p.get("formatted"),
            "categories": categories, "price": price, "feeStatus": status, "source": "Geoapify",
            "openingHours": raw.get("opening_hours"), "website": p.get("website") or raw.get("website") or raw.get("contact:website"),
            "description": p.get("description") or raw.get("description:ru") or raw.get("description"),
        }))
    return [row for _, row in sorted(result.values(), key=lambda item: item[0])[:count]]


def admission(raw, categories):
    fee = str(raw.get("fee") or "").strip().casefold()
    charge = re.fullmatch(r"(\d{1,6})\s*(?:rub|₽|руб\.?)", str(raw.get("charge") or "").strip(), re.I)
    if charge and int(charge[1]) > 0:
        return "paid", int(charge[1])
    if fee == "no" or "no_fee.no" in categories:
        return "free", 0
    return ("paid" if fee == "yes" or "fee" in categories else "unknown"), None


def add_museum_estimates(places, destination):
    from stage3 import read_reference

    museums = [place for place in places if place["price"] is None
               and any(category.startswith("entertainment.museum") for category in place["categories"])]
    if museums:
        reference = read_reference().get_reference(
            "museum_ticket", destination["city"], destination.get("regionName"), allow_country_fallback=True,
        )
        if reference:
            for place in museums:
                place["priceReference"] = reference


def probe(hotel, requirement, dates, args, cache, reader, *, registry=False):
    query = search_query(requirement, hotel["name"], hotel["city"], hotel.get("address"))
    started = monotonic()
    evidence, pages, search = retrieve(hotel, requirement["searchTerms"], cache, reader, registry=registry)
    retrieval_seconds = round(monotonic() - started, 3)
    trace = {}
    with getattr(args, "model_lock", nullcontext()):
        if evidence:
            if getattr(args, "cancelled", lambda: False)():
                return {"status": "unknown", "requirement": requirement}
            sleep(2)
        verdict = judge(hotel, requirement["question"], evidence, dates, args.port, args.model, trace)
    return {"query": query, "searchMode": "registry" if registry else "discovery", "discovery": search,
            "requirement": requirement, "retrievalSeconds": retrieval_seconds,
            "pages": pages, "evidence": evidence, "trace": trace,
            **verdict, "label": requirement.get("labels", {}).get(verdict["status"])}


def read_destinations():
    return json.loads((ROOT.parents[2] / "shared/data/destinations.json").read_text(encoding="utf8"))["destinations"]


def requirements_for(parsed):
    requirements = list(parsed["extra"])
    for rule in parsed["filters"]:
        if rule["kind"] != "hotel_amenity":
            continue
        condition = AMENITIES[rule["value"]]
        requirements.append({"question": f"Выполняется ли условие: {condition}?", "searchTerms": condition,
                             "strength": rule["strength"], "excluded": rule["excluded"]})
    return sorted(requirements, key=lambda req: req["strength"] != "required")


def split_breakfast(requirements, preferences):
    simple_breakfast = []
    for req in requirements:
        text = (req.get("condition", "") + " " + req.get("label", "") + " " + req["question"]).casefold()
        if "завтрак" not in text:
            continue
        if re.search(r"вегетариан|время|ранн|поздн|шведск|\d|достав", text):
            continue
        simple_breakfast.append(req)
        if re.search(r"включ|тариф|с завтраком|без завтрака", text):
            excluded = bool(re.search(r"без завтрака|не включ[её]н", text))
            return ({"required": req["strength"] == "required", "included": not excluded},
                    [rule for rule in requirements if rule is not req])
    for clause in re.split(r"[.!?;\n]", preferences):
        if re.search(r"\b(?:отел\w*|гостиниц\w*)\s+(?:ид[её]т\s+)?(?:с завтраком|без завтрака)\b"
                     r"|завтрак\s+(?:должен быть\s+)?включ[её]н", clause, re.I):
            return {"required": not bool(re.search(r"желательно|хотелось|в идеале", clause, re.I)),
                    "included": not bool(re.search(r"без завтрака", clause, re.I))}, [
                        rule for rule in requirements if rule not in simple_breakfast
                    ]
    return None, requirements


def free_places(text):
    if re.search(r"только\s+бесплатн\w*\s+(?:мест|достопримечательност|музе|парк)", text, re.I):
        return "required"
    if re.search(r"бесплатн\w*\s+(?:мест|достопримечательност|музе|парк)|бесплатн\w*\s+вход", text, re.I):
        return "preferred"
    return None


def check_hotel(hotel, requirements, dates, args, cache, reader):
    probes = []
    for req in requirements:
        if getattr(args, "cancelled", lambda: False)():
            break
        outcome = probe(hotel, req, dates, args, cache, reader)
        if req.get("excluded") and outcome["status"] != "unknown":
            outcome["sourceStatus"] = outcome["status"]
            outcome["status"] = {"confirmed": "contradicted", "contradicted": "confirmed"}[outcome["status"]]
        probes.append(outcome)
        if req["strength"] == "required" and outcome["status"] != "confirmed":
            break
    return {**hotel, "checks": probes}


def parallel_checks(hotels, requirements, dates, args):
    def check(hotel):
        with Reader() as reader:
            return check_hotel(hotel, requirements, dates, args, {}, reader)

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="hotel-search") as pool:
        def submit():
            if args.cancelled():
                return None
            hotel = next(hotels, None)
            return pool.submit(check, hotel) if hotel else None

        jobs = {job for _ in range(3) if (job := submit()) is not None}
        while jobs and not args.cancelled():
            done, jobs = wait(jobs, return_when=FIRST_COMPLETED)
            for job in done:
                yield job.result()
                if (new_job := submit()) is not None:
                    jobs.add(new_job)


def select(input_card, args, reader, progress=None, publish=None):
    destinations = args.destinations if publish else read_destinations()
    destination = next((d for d in destinations if d["id"] == input_card["destination"]), None)
    if destination is None:
        raise ValueError("Неизвестное направление")
    dates = [input_card["startDate"], input_card["endDate"]]
    nights = (date.fromisoformat(dates[1]) - date.fromisoformat(dates[0])).days
    travelers = input_card["travelers"]
    if nights <= 0 or type(travelers) is not int or travelers <= 0:
        raise ValueError("Expected positive nights and travelers")
    started = monotonic()
    if progress:
        progress("Разбираем пожелания")
    with getattr(args, "model_lock", nullcontext()):
        parsed = analyze(input_card["preferences"], args.port, args.model, {})
    parsed_at = monotonic()
    if progress:
        progress("Ищем отели и интересные места")
    requirements = requirements_for(parsed)
    breakfast = None
    if publish:
        breakfast, requirements = split_breakfast(requirements, input_card["preferences"])
        places = place_candidates(destination, parsed["filters"], 15, free=free_places(input_card["preferences"]))
        add_museum_estimates(places, destination)
        hotels = hotel_candidates(destination, nights, travelers, input_card["hotelBudgetRub"],
                                  pages=4, breakfast=breakfast)
    else:
        hotels = list(hotel_candidates(destination, nights, travelers, input_card.get("hotelBudgetRub")))
        places = place_candidates(destination, parsed["filters"], 5)
    providers_at = monotonic()
    cache = {}
    checked, selected = [], []
    max_checked = getattr(args, "max_checked_hotels", 8)
    def snapshot():
        count = len(checked) if publish else len(hotels)
        return {"card": input_card, "parsed": parsed, "providerHotelCount": count,
                "uncheckedHotelCount": count - len(checked),
                "seconds": {"preferences": round(parsed_at - started, 3),
                            "providers": round(providers_at - parsed_at, 3),
                            "hotelChecks": round(monotonic() - providers_at, 3)},
                "checkedHotels": list(checked), "hotels": list(selected), "attractions": places}

    if publish:
        publish(snapshot())
        if progress:
            progress("Подбираем отели по условиям поездки")
        entries = parallel_checks(hotels, requirements, dates, args) if requirements else (
            {**hotel, "checks": []} for hotel in hotels
        )
    else:
        candidates = hotels[:max_checked] if requirements else hotels
        entries = (check_hotel(hotel, requirements, dates, args, cache, reader) for hotel in candidates)

    try:
        for entry in entries:
            checked.append(entry)
            if all(p["status"] == "confirmed" or p["requirement"]["strength"] != "required" for p in entry["checks"]):
                selected.append(entry)
                if publish:
                    publish(snapshot())
                if len(selected) == (8 if publish else 4):
                    break
    finally:
        entries.close()
    if not publish:
        selected.sort(key=lambda hotel: -sum(p["status"] == "confirmed" for p in hotel["checks"]))
    return snapshot()


def evaluate(args, reader):
    cases = json.loads(args.cases.read_text(encoding="utf8"))
    cache = {}
    rows = []
    for case in cases:
        result = probe(case["hotel"], {"question": case["question"], "searchTerms": case["terms"],
                                      "strength": "preferred"}, case.get("dates"), args, cache, reader,
                       registry=args.registry)
        # Gold is for the full reviewed source. Excerpt coverage is independently anchored
        # by a human-selected marker, and is evaluated separately from verdict accuracy.
        marker = case.get("marker")
        delivered = bool(marker and any(row["url"] == case["goldSource"]
                         and marker.casefold() in row["text"].casefold() for row in result["evidence"]))
        row = {**case, **result, "decisiveExcerpt": delivered, "correct": case["expected"] == result["status"]}
        rows.append(row)
        print(case["id"], result["status"], "PASS" if row["correct"] else "FAIL", flush=True)
        sleep(3)
    return rows


def evaluate_snapshot(args):
    rows = json.loads(args.snapshot.read_text(encoding="utf8"))
    results = []
    for row in rows:
        trace = {}
        verdict = judge(row["hotel"], row["question"], row["evidence"], row.get("dates"),
                        args.port, args.model, trace)
        correct = row["expected"] == verdict["status"]
        results.append({"id": row["id"], "expected": row["expected"], "decisiveExcerpt": row.get("decisiveExcerpt"),
                        "evidence": row["evidence"], "verdict": verdict, "trace": trace, "correct": correct})
        print(row["id"], verdict["status"], "PASS" if correct else "FAIL", flush=True)
        sleep(3)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--card", type=Path)
    mode.add_argument("--check", type=Path, help="Check one hotel and requirement from a JSON file")
    mode.add_argument("--judge-suite", action="store_true")
    mode.add_argument("--snapshot", type=Path, help="Evaluate the judge on saved evidence from a judge suite")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--model", default="tripflow-qwen3.5-9b")
    parser.add_argument("--max-checked-hotels", type=int, choices=range(1, 13), default=8)
    parser.add_argument("--cases", type=Path, default=ROOT / "judge-cases.json")
    parser.add_argument("--registry", action="store_true", help="Use manually pinned sites in a judge suite")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.snapshot:
        result = evaluate_snapshot(args)
    else:
        with Reader() as reader:
            if args.judge_suite:
                result = evaluate(args, reader)
            elif args.check:
                item = json.loads(args.check.read_text(encoding="utf8"))
                result = probe(item["hotel"], {"question": item["question"], "searchTerms": item["terms"],
                                               "strength": "preferred"}, item.get("dates"), args, {}, reader)
            else:
                result = select(json.loads(args.card.read_text(encoding="utf8")), args, reader)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

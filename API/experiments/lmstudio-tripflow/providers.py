"""Replay real Moscow provider snapshots already collected in this repository."""

import json
import math
from decimal import Decimal
from pathlib import Path


API = Path(__file__).resolve().parents[2]
SAMPLES = API / "experiments/data-source-survey/data/samples/20261015T150210175612Z"
RESEARCH = API / "research/data-coverage-russia-2026-10-28"
CATEGORIES = ("museums", "nature", "historic")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)


def attractions(categories):
    candidates = {}
    for category in categories:
        path = SAMPLES / f"geoapify_moscow_{category}.json"
        snapshot = read(path)
        for index, item in enumerate(snapshot["normalized"], 1):
            if not item["name"] or item["country_code"] != "ru":
                continue
            candidates.setdefault(item["external_id"], {
                "id": f"{category}-{index}",
                "name": item["name"],
                "category": category,
                "price": None,
                "address": item["address"],
                "coordinates": {
                    "latitude": float(item["latitude"]),
                    "longitude": float(item["longitude"]),
                },
                "source": "Geoapify",
                "snapshot": str(path.relative_to(API)),
            })
    return list(candidates.values())


def hotels():
    path = RESEARCH / "russhotels-evidence.json"
    snapshot = read(path)
    candidates = {}
    for record in snapshot["records"]:
        if record["city"] != "Москва":
            continue
        for hotel in record["hotels"]:
            if hotel["city"] != "Москва" or hotel["active"] != "1":
                continue
            prices = [
                room["price_client"] for room in hotel["rooms"]
                if room.get("placement_type", {}).get("id") == "1"
                and (room["price_client"] or 0) > 0
            ]
            if not prices:
                continue
            candidates[hotel["id"]] = {
                "id": f"hotel-{hotel['id']}",
                "name": hotel["name"],
                "referenceRubPerPersonNight": math.ceil(min(prices)),
                "address": hotel["address"],
                "coordinates": {
                    "latitude": float(hotel["lat"]),
                    "longitude": float(hotel["lon"]),
                },
                "source": "Russhotels",
                "snapshot": str(path.relative_to(API)),
            }
    return list(candidates.values())


def museum_rate():
    path = RESEARCH / "rosstat-budget-reference-2026-09.json"
    data = read(path)
    moscow = next(row for row in data["territories"] if row["territory_code"] == "45000000000")
    return {
        "perVisitPerPersonRub": math.ceil(moscow["values"]["9525"]),
        "scope": "city",
        "period": data["period"],
        "source": "Росстат, Музеи и выставки, билет (9525)",
        "snapshot": str(path.relative_to(API)),
    }

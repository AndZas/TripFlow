"""Read the saved Rosstat reference without network access.

Research helper, not a TripFlow contract or a booking-price calculator.
Hotel statistical rates are per person/day, not guaranteed private-room rates.
"""

import argparse
import json
from decimal import Decimal
from pathlib import Path


METRICS = {
    "hotel_1_star": "9462",
    "hotel_2_star": "9463",
    "hotel_3_star": "9464",
    "hotel_4_5_star": "9465",
    "hostel": "9466",
    "cafe_lunch": "3606",
    "restaurant_lunch": "3601",
    "restaurant_dinner": "3607",
    "bus_ride": "9222",
    "taxi_km": "9219",
    "metro_ride": "9214",
    "museum_ticket": "9525",
    "cinema_ticket": "9521",
    "theatre_ticket": "9523",
}

ALIASES = {
    "москва": "Город Москва столица Российской Федерации город федерального значения",
    "санкт-петербург": "Город Санкт-Петербург город федерального значения",
    "спб": "Город Санкт-Петербург город федерального значения",
}


def normalize(value):
    return " ".join(value.casefold().replace("ё", "е").split())


def get_reference(metric, city=None, region=None, allow_country_fallback=False):
    """Return a sourced rate and its geographic scope, or None.

    The caller supplies the region explicitly. No guessed city/region mapping,
    interpolation, price inflation or room/person conversion is performed.
    """
    code = METRICS[metric]
    path = Path(__file__).with_name("rosstat-budget-reference-2026-09.json")
    dataset = json.loads(path.read_text(encoding="utf-8"))
    candidates = []
    if city:
        candidates.append(("city", ALIASES.get(normalize(city), city)))
    if region:
        candidates.append(("region", region))
    if allow_country_fallback:
        candidates.append(("country", "Российская Федерация"))

    field = next(f for f in dataset["fields"] if f["key"] == code)
    for scope, name in candidates:
        matches = [
            row for row in dataset["territories"]
            if normalize(row["territory_name"]) == normalize(name)
        ]
        if len(matches) != 1:
            continue
        row = matches[0]
        value = row["values"].get(code)
        if value is None or Decimal(str(value)) <= 0:
            continue
        return {
            "metric": metric,
            "amount_rub": str(Decimal(str(value))),
            "source_label_with_unit": field["label"],
            "scope": scope,
            "territory_name": row["territory_name"],
            "territory_code": row["territory_code"],
            "reference_period": dataset["period"],
            "source_url": dataset["source_url"],
            "source_cell": f"{dataset['sheet']}!{field['excel_column']}{row['excel_row']}",
        }
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric", choices=METRICS, required=True)
    parser.add_argument("--city")
    parser.add_argument("--region")
    parser.add_argument("--allow-country-fallback", action="store_true")
    args = parser.parse_args()
    result = get_reference(
        args.metric, args.city, args.region, args.allow_country_fallback
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

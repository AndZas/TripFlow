"""Run a selected-card experiment across preferences, search and budget."""

import argparse
import json
from pathlib import Path
from time import monotonic

from source_reader import Reader
from stage2 import select
from stage3 import estimate


def run(card, args):
    started = monotonic()
    with Reader() as reader:
        recommendations = select(card, args, reader)
    searched = monotonic()
    # For a repeatable smoke test choose one of the returned options by position.
    hotel = next(iter(recommendations["hotels"]), None)
    attraction = next(iter(recommendations["attractions"]), None)
    result = {"recommendations": recommendations, "seconds": {"recommendations": round(searched - started, 2)}}
    if not hotel:
        return {**result, "budget": None, "reason": "No eligible hotel to select"}

    budget_card = {key: card[key] for key in ("startDate", "endDate", "travelers", "budgetRub")}
    budget_card.update(hotel=hotel, expenseNotes=recommendations["parsed"]["expenses"],
                       selectedPlaces=[{"name": attraction["name"], "alreadyPriced": attraction["price"] is not None}]
                       if attraction else [])
    budget_trace = {}
    selected = {"selectedHotelId": hotel["id"], "selectedPlaceId": attraction["id"] if attraction else None}
    try:
        budget = estimate(budget_card, args, budget_trace)
    except (ValueError, RuntimeError) as error:
        return {**result, **selected, "budget": None, "budgetTrace": budget_trace, "reason": str(error)}
    result["seconds"]["budget"] = round(monotonic() - searched, 2)
    return {**result, **selected, "budget": budget, "budgetTrace": budget_trace}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--model", default="tripflow-qwen3.5-9b")
    parser.add_argument("--max-checked-hotels", type=int, choices=range(1, 13), default=8)
    args = parser.parse_args()
    args.verify_tariff = False  # Supplier listing has no verified selected tariff.
    card = json.loads(args.card.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        result = run(card, args)
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(result.get("selectedHotelId"), result.get("selectedPlaceId"), result["seconds"])
    return int(result["budget"] is None or result["selectedPlaceId"] is None)


if __name__ == "__main__":
    raise SystemExit(main())

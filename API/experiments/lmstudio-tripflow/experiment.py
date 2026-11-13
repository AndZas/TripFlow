"""Run fixed Russian-language cases against a loaded model and record its replies."""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic

from harness import Harness, LMStudio, Trip, encode


@dataclass(frozen=True)
class Case:
    trip: Trip
    categories: tuple[str, ...] = ()
    visits: int | None = None
    hotel_order: tuple[str, ...] | None = None
    attraction_ids: tuple[str, ...] | None = None

    def evaluate(self, harness, result):
        categories = next(
            (call["arguments"]["categories"] for call in harness.calls if call["name"] == "search_attractions"),
            [],
        )
        estimate = result["museumEstimate"]
        visits = estimate["suggestedVisitsPerPerson"] if estimate is not None else None
        checks = {
            "expectedSearchCategories": set(categories) == set(self.categories),
            "expectedMuseumVisits": visits == self.visits,
        }
        if self.hotel_order is not None:
            checks["expectedHotelOrder"] = tuple(row["id"] for row in result["hotels"]) == self.hotel_order
        if self.attraction_ids is not None:
            checks["expectedAttractionIds"] = {row["id"] for row in result["attractions"]} == set(self.attraction_ids)
        return checks


CASES = {
    "two-museums": Case(
        Trip("За всю поездку хотим два платных музея и погулять по паркам. Отель нужен подешевле."),
        ("museums", "nature"), visits=2, hotel_order=("hotel-19", "hotel-18", "hotel-16"),
    ),
    "four-museums": Case(
        Trip("За всю поездку хотим четыре платных музея и погулять по паркам. Отель нужен подешевле."),
        ("museums", "nature"), visits=4, hotel_order=("hotel-19", "hotel-18", "hotel-16"),
    ),
    "unclear-visit-count": Case(
        Trip("Интересуют только музеи. Решим на месте, сколько посетить."),
        ("museums",),
    ),
    "parks-refinement": Case(
        Trip("Хотим только музеи.", target="attractions", refinement="Передумали: теперь только парки, без музеев.",
             excluded_ids=("nature-2",)),
        ("nature",), attraction_ids=(),
    ),
    "budget-hotel": Case(
        Trip("Отель подешевле.", target="hotels", option_budget_rub=65_000, excluded_ids=("hotel-19",)),
        hotel_order=("hotel-18",),
    ),
    "rank-hotels": Case(
        Trip("Для нас важна минимальная цена, поставь отели от самого дешёвого к самому дорогому.",
             target="hotels", option_budget_rub=1_000_000),
        hotel_order=("hotel-19", "hotel-18", "hotel-16"),
    ),
    "empty-hotel": Case(
        Trip("Нужен самый дешёвый отель.", target="hotels", option_budget_rub=10_000),
        hotel_order=(),
    ),
}


def run_case(name, case, port, model):
    harness = Harness(case.trip)
    client = LMStudio(port, model)
    started = monotonic()
    result, checks, error = None, {}, None
    try:
        result = harness.run(client)
        checks = case.evaluate(harness, result)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, IndexError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {
        "case": name, "trip": asdict(case.trip),
        "passed": error is None and all(checks.values()),
        "checks": checks, "error": error,
        "durationSeconds": round(monotonic() - started, 3),
        "calls": harness.calls, "toolResults": harness.results,
        "result": result, "lmStudioReplies": client.trace,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--model", default="tripflow-qwen3-4b")
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeat < 1 or not 1 <= args.port <= 65535:
        parser.error("Expected positive repeat count and a valid TCP port")
    now = datetime.now().astimezone()
    output = args.output or Path(__file__).with_name("runs") / f"{now:%Y%m%dT%H%M%S%f%z}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Trace: {output}", flush=True)
    success = True
    with output.open("x", encoding="utf-8") as log:
        for repeat in range(1, args.repeat + 1):
            for name in args.case or CASES:
                record = run_case(name, CASES[name], args.port, args.model)
                record.update(repeat=repeat, model=args.model, port=args.port)
                print(encode(record), file=log, flush=True)
                status = "PASS" if record["passed"] else "FAIL"
                print(f"{status} {name} #{repeat} ({record['durationSeconds']:.3f} s)", flush=True)
                success &= record["passed"]
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

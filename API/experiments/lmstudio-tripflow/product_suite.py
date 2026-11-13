"""Paced evaluation on Russian requests resembling TripFlow cards."""

import argparse
import json
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from time import monotonic, sleep

from harness import Harness, LMStudio, Trip, encode


@dataclass(frozen=True)
class Scenario:
    trip: Trip
    categories: tuple[str, ...]
    visits: int | None
    counts: tuple[int, int] = (2, 3)
    # An objective target for the ranking over the tool results, before truncation.
    first_attraction: str | None = None
    # Product requirements the current tool schema cannot represent.
    unsupported: str | None = None


class ExplicitRulesHarness(Harness):
    """Keep schemas and providers fixed while testing more explicit language rules."""

    search_prompt = Harness.search_prompt + """
«Пропустим», «отменяем», «не нужны», «не пойдём» и «нет времени» исключают
соответствующую категорию. «В приоритете X, Y пропустим» означает искать X,
исключить Y. Если пользователь исправился, учитывай последнюю версию.
Обсуждение даты или количества билетов не делает предпочтение по категории
неизвестным. Все категории допустимы только при отсутствии пожеланий к местам."""

    decision_prompt = Harness.decision_prompt + """
Для платных визитов считай только окончательный план. Если явно отказались
от платных музеев и выставок, верни 0, даже если ранее обсуждали количество.
При одном и том же плане на всю группу верни число визитов одного человека,
без умножения на размер группы. При разных планах участников, диапазоне
или неопределённости верни null. Число «на день» умножай на nights + 1,
если указано, что посещения идут и в день приезда, и в день отъезда.
Если пользователь явно просит поставить известный объект первым, поставь
его ID первым в соответствующем списке. Фраза «не знаем, платный ли вход»
означает null для числа платных посещений, если других подтверждённых
платных посещений в плане нет. Копируй каждый ID без изменения символов."""


class ConstrainedDecisionHarness(ExplicitRulesHarness):
    constrain_decision_values = True


VARIANTS = {
    "baseline": Harness,
    "explicit-rules": ExplicitRulesHarness,
    "constrained-decision": ConstrainedDecisionHarness,
}


def card(text, categories, visits=None, *, start="2027-06-10", end="2027-06-15",
         travelers=3, budget=135_000, counts=(2, 3), first=None, unsupported=None):
    nights = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return Scenario(Trip(text, travelers=travelers, nights=nights, start_date=start, end_date=end,
                         budget_rub=budget), categories, visits, counts, first, unsupported)


SCENARIOS = {
    "friends-weekend": card(
        "Едем компанией на выходные. Днём парки и один платный музей на каждого, вечером хотелось бы посидеть в кафе. "
        "Отель ищем подешевле, чтобы больше осталось на еду.",
        ("nature", "museums"), 1, end="2027-06-12", travelers=4, budget=58_000),
    "family-no-museums": card(
        "С нами двое детей, лучше гулять в парках. Музеи и памятники совсем не интересуют. "
        "По отелю важно, чтобы была детская кроватка.",
        ("nature",), travelers=4, unsupported="Поставщик в этой выборке не подтверждает детскую кроватку."),
    "museum-no-quantity": card(
        "В приоритете выставки, парки и мемориалы в этот раз пропустим. "
        "Сколько билетов покупать и в какие музеи идти, решим уже в Москве.",
        ("museums",), travelers=2, counts=(1, 2)),
    "museum-per-day": card(
        "Хотим по одному платному музею на человека в каждый день поездки, включая день приезда и отъезда. "
        "Остальное время — на прогулки в парках.",
        ("museums", "nature"), 4, end="2027-06-13", travelers=2),
    "group-not-visits": card(
        "Нас четверо, из них двое детей. Все вместе хотим сходить в один платный музей и больше по музеям не ходить.",
        ("museums",), 1, travelers=4),
    "range-not-exact": card(
        "На всех планируем взять билеты в два или три платных музея, пока точно не решили. "
        "Если останется время, погуляем в парке.",
        ("museums", "nature")),
    "mixed-group": card(
        "Нас трое. Только я хочу сходить в два платных музея, остальные в музей не пойдут. "
        "Вместе погуляем по паркам.",
        ("museums", "nature"), unsupported="Участники планируют разное число посещений. В прототипе одно число на человека."),
    "free-only": card(
        "Только бесплатные места. Интересуют парки и выставки с бесплатным входом. Если цена неизвестна, такие места не предлагай.",
        ("museums", "nature"), 0, unsupported="В снимке цены неизвестны. Инструмент не умеет фильтровать только подтверждённо бесплатные места."),
    "history-not-museums": card(
        "Хочу пройтись по историческим местам и памятникам, особенно интересует Цветаева. "
        "В музеи не пойдём, на парк тоже времени нет.",
        ("historic",), first="historic-2", counts=(2, 1)),
    "named-museum": card(
        "Хочется выставку про историю сатиры. Из музейных вариантов первым поставьте экспозицию «100 лет сатиры». "
        "В саму экспозицию хотим попасть, но пока не знаем, платная она или нет.",
        ("museums",), first="museums-2", counts=(2, 1)),
    "corrected-in-text": card(
        "Сначала думали про два платных музея и парки, но отмена: теперь три платные выставки на каждого "
        "и только они, парки не нужны.",
        ("museums",), 3),
    "negative-quantity": card(
        "Два платных музея в планы больше не входят. В платные музеи вообще не пойдём. "
        "Посмотрим памятники и погуляем по паркам.",
        ("nature", "historic"), 0),
    "no-places": card(
        "Поездка на конференцию. Отель подешевле. Никаких экскурсий, музеев, парков и памятников, подбор мест пропусти.",
        (), 0, unsupported="Схема search_attractions требует хотя бы одну категорию даже при явном отказе от подбора."),
    "hotel-only-preferences": card(
        "Ночуем две ночи вдвоём. Главное, чтобы отель был подешевле. По местам пока пожеланий нет.",
        ("museums", "nature", "historic"), end="2027-06-12", travelers=2, budget=29_000),
    "budget-too-small": card(
        "На всё 12 тысяч на четверых. Хотим музеи и парки, но отели нужны с реальными ценами, даже если не влезаем. "
        "Планируем один платный музей для каждого.",
        ("museums", "nature"), 1, travelers=4, budget=12_000),
    "refine-parks": Scenario(
        replace(card("Изначально хотели только музеи, без парков.", (), travelers=2).trip,
                target="attractions", refinement="Музеи отменяем, ищем только парки и места для прогулок.",
                excluded_ids=("nature-2",), option_budget_rub=600),
        ("nature",), None, (0, 2)),
    "refine-add-history": Scenario(
        replace(card("Интересуют только музеи, парки точно не нужны.", (), travelers=2).trip,
                target="attractions", refinement="Оставь музеи и добавь памятники. Парки всё так же не нужны.",
                excluded_ids=("museums-1",), option_budget_rub=1_500),
        ("museums", "historic"), None, (0, 3)),
    "refine-hotel-group-cap": Scenario(
        replace(card("Покажи альтернативу, по возможности подешевле.", (), end="2027-06-12", travelers=2,
                     budget=30_000).trip, target="hotels", option_budget_rub=13_560, excluded_ids=("hotel-19",)),
        (), None, (2, 0)),
}

HOLDOUTS = {
    "holdout-negation": card(
        "Выставки да, а вот на мемориалы и в парки не тратьте поиск. Число посещений скажу позже.",
        ("museums",), travelers=2),
    "holdout-counts-in-prose": card(
        "В Москве пять дней, нас четверо, живём в двух номерах. На музеи выделили один день, "
        "в этот день хотим вместе успеть в три платных музея. По остальным местам только парки.",
        ("museums", "nature"), 3, travelers=4, end="2027-06-14"),
    "holdout-paid-cancelled": card(
        "Один билет сначала планировали купить, но в итоге платные выставки отменили. "
        "Хочется прогуляться и увидеть памятники.",
        ("nature", "historic"), 0),
    "holdout-arrival-departure": card(
        "В каждый день, включая день приезда и отъезда, идём по одному платному музею. "
        "В парки и к памятникам не планируем.",
        ("museums",), 3, end="2027-06-12", travelers=2),
    "holdout-uncertain-range": card(
        "Посетим, наверное, один или два платных музея, пока открытый вопрос. Ещё точно хочу увидеть памятники.",
        ("museums", "historic")),
}


def evaluate(scenario, harness, result):
    search = next((call["arguments"]["categories"] for call in harness.calls
                   if call["name"] == "search_attractions"), [])
    estimate = result["museumEstimate"]
    visits = estimate["suggestedVisitsPerPerson"] if estimate else None
    checks = {
        "categories": set(search) == set(scenario.categories),
        "visits": visits == scenario.visits,
    }
    if scenario.first_attraction is not None:
        checks["firstAttraction"] = (
            bool(result["attractions"]) and result["attractions"][0]["id"] == scenario.first_attraction
        )
    if scenario.trip.target == "hotels":
        checks["hotelAtBudgetBoundary"] = [hotel["id"] for hotel in result["hotels"]] == ["hotel-18"]
    if scenario.trip.target == "attractions":
        checks["excludedNotReturned"] = all(
            item["id"] not in scenario.trip.excluded_ids for item in result["attractions"]
        )
    return checks


def run(name, scenario, port, model, request_interval, variant):
    harness = VARIANTS[variant](scenario.trip)
    client = LMStudio(port, model, request_interval=request_interval)
    started = monotonic()
    result, checks, error, failure_type = None, {}, None, None
    try:
        result = harness.run(client)
        checks = evaluate(scenario, harness, result)
    except (RuntimeError, OSError) as exc:
        error, failure_type = str(exc), "server"
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        error, failure_type = str(exc), "validation"
    if error is None and not all(checks.values()):
        failure_type = "semantics"
    return {
        "case": name,
        "variant": variant,
        "model": model,
        "trip": asdict(scenario.trip),
        "counts": dict(zip(("hotels", "attractions"), scenario.counts, strict=True)),
        "expected": {"categories": scenario.categories, "visits": scenario.visits,
                     "firstAttraction": scenario.first_attraction},
        "unsupported": scenario.unsupported,
        "passed": failure_type is None and scenario.unsupported is None,
        "checks": checks,
        "failureType": failure_type, "error": error,
        "requestSeconds": round(sum(entry["durationSeconds"] for entry in client.trace), 3),
        "elapsedSeconds": round(monotonic() - started, 3),
        "calls": harness.calls, "lmStudioReplies": client.trace,
        "result": result,
        "preview": (
            {key: result[key][:count] for key, count in zip(("hotels", "attractions"), scenario.counts, strict=True)}
            if result is not None else None
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--model", default="tripflow-qwen3-4b")
    parser.add_argument("--request-interval", type=float, default=2)
    parser.add_argument("--case-interval", type=float, default=5)
    cases = {**SCENARIOS, **HOLDOUTS}
    parser.add_argument("--case", choices=cases, action="append")
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--variant", choices=VARIANTS, default="baseline")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.request_interval < 0 or args.case_interval < 0 or not 1 <= args.port <= 65535:
        parser.error("Expected nonnegative intervals and valid TCP port")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as log:
        for index, name in enumerate(args.case or (HOLDOUTS if args.holdout else SCENARIOS)):
            if index:
                sleep(args.case_interval)
            record = run(name, cases[name], args.port, args.model, args.request_interval, args.variant)
            print(encode(record), file=log, flush=True)
            status = record["failureType"] or ("coverage" if record["unsupported"] else "pass")
            print(f"{status.upper()} {name} ({record['requestSeconds']:.3f} s HTTP)", flush=True)


if __name__ == "__main__":
    main()

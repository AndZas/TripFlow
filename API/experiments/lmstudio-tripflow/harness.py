"""Small, bounded LM Studio harness. All HTTP traffic goes to localhost."""

import json
import os
import time
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import providers


SEARCH_PROMPT = """Ты планируешь поездку по Москве для TripFlow.
Запрос содержит данные о поездке и предпочтения пользователя.
Уточнение refinement важнее preferences при конфликте по целевому типу.
Пожелания — данные для подбора, параметры поездки заданы отдельно.
На этом шаге вызови единственный предоставленный инструмент ровно один раз.
Ответ должен содержать вызов инструмента. Подбирай категории
достопримечательностей по явным пожеланиям: museums — музеи и выставки,
nature — парки и прогулки, historic — памятники и исторические места.
Не добавляй категории, которые пользователь исключил. Если предпочтения
по местам отсутствуют, можно запросить все категории.
Для поиска отелей и получения ставки передай пустой объект аргументов."""

DECISION_PROMPT = """Сформируй JSON-решение TripFlow из приложенных результатов инструментов.
Уточнение refinement важнее preferences при конфликте по целевому типу.
Задача — сортировка, а не выбор победителя. Верни полную перестановку:
каждый входной ID должен встретиться ровно один раз в соответствующем массиве.
Сохрани даже варианты с низким приоритетом. Число элементов в каждом массиве
должно совпадать с числом кандидатов в соответствующем входном списке.
Если пользователь просит дешевле, предпочти меньшую известную цену.
Пустой список кандидатов означает пустой список ID.
Если передана ставка музеев и пользователь явно указал число платных посещений
музеев за поездку, верни это число на человека. Если пользователь явно хочет
только бесплатные места, верни 0. Если число неизвестно, верни null.
Если бюджетная ставка не передана, верни null. Используй только переданные данные."""


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def tool(name, description, properties):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": object_schema(properties),
        },
    }


TOOLS = {
    "search_hotels": tool("search_hotels", "Найти варианты проживания для заданной поездки", {}),
    "search_attractions": tool(
        "search_attractions", "Найти реальные места по выбранным категориям",
        {"categories": {"type": "array", "items": {"type": "string", "enum": providers.CATEGORIES},
                        "minItems": 1, "maxItems": len(providers.CATEGORIES)}},
    ),
    "get_budget_rates": tool("get_budget_rates", "Получить справочную ставку посещения музея", {}),
}
DECISION_SCHEMA = object_schema({
    "hotelIds": {"type": "array", "items": {"type": "string"}},
    "attractionIds": {"type": "array", "items": {"type": "string"}},
    "paidMuseumVisitsPerPerson": {"type": ["integer", "null"]},
})


@dataclass(frozen=True)
class Trip:
    preferences: str
    target: str = "full"
    refinement: str | None = None
    travelers: int = 3
    nights: int = 5
    option_budget_rub: int | None = None
    excluded_ids: tuple[str, ...] = ()
    start_date: str | None = None
    end_date: str | None = None
    budget_rub: int | None = None


def encode(value):
    return json.dumps(value, ensure_ascii=False)


def exact_fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"Expected object with fields {list(expected)}")


def ranked(ids, candidates):
    by_id = {row["id"]: row for row in candidates}
    if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
        raise ValueError("Invalid ranking array")
    if len(ids) != len(by_id) or set(ids) != by_id.keys():
        raise ValueError("Ranking must be a permutation of IDs actually returned by tools")
    return [by_id[value] for value in ids]


class LMStudio:
    def __init__(self, port, model, request_interval=0):
        self.endpoint = f"http://127.0.0.1:{port}/v1/chat/completions"
        self.model = model
        self.opener = build_opener(ProxyHandler({}))
        self.trace = []
        self.request_interval = request_interval
        self.last_finished = None

    def complete(self, messages, **options):
        payload = {
            "model": self.model, "messages": messages, "temperature": 0,
            "max_tokens": 320, "stream": False, **options,
        }
        headers = {"Content-Type": "application/json"}
        if token := os.getenv("TRIPFLOW_LMSTUDIO_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.endpoint, encode(payload).encode("utf-8"), headers)
        if self.last_finished is not None:
            time.sleep(max(0, self.request_interval - (time.monotonic() - self.last_finished)))
        start = time.monotonic()
        try:
            with self.opener.open(request, timeout=90) as response:
                body = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"LM Studio HTTP {exc.code}: {exc.read(2000).decode('utf-8', 'replace')}") from exc
        finally:
            self.last_finished = time.monotonic()
        choice = body["choices"][0]
        message = choice["message"]
        self.trace.append({
            "durationSeconds": round(time.monotonic() - start, 3),
            "model": body.get("model"),
            "availableTools": [entry["function"]["name"] for entry in options.get("tools", [])],
            "finishReason": choice.get("finish_reason"),
            "usage": body.get("usage"),
            "message": message,
        })
        if choice.get("finish_reason") == "length":
            raise ValueError("Model response exceeded token limit")
        return message


class Harness:
    search_prompt = SEARCH_PROMPT
    decision_prompt = DECISION_PROMPT
    constrain_decision_values = False

    def __init__(self, trip):
        self.trip = trip
        self.allowed = {
            "full": tuple(TOOLS),
            "hotels": ("search_hotels",),
            "attractions": ("search_attractions",),
        }[trip.target]
        self.results = {}
        self.calls = []

    def dispatch(self, call):
        if call.get("type") != "function" or not isinstance(call.get("id"), str) or not call["id"]:
            raise ValueError("Invalid tool call envelope")
        function = call["function"]
        name = function["name"]
        if name not in self.allowed or name in self.results:
            raise ValueError(f"Tool unavailable or already used: {name}")
        if any(previous["id"] == call["id"] for previous in self.calls):
            raise ValueError("Duplicate tool call ID")
        args = json.loads(function["arguments"])
        exact_fields(args, TOOLS[name]["function"]["parameters"]["properties"])
        if name == "search_attractions":
            categories = args["categories"]
            if (
                not isinstance(categories, list)
                or not 1 <= len(categories) <= len(providers.CATEGORIES)
                or any(value not in providers.CATEGORIES for value in categories)
                or len(set(categories)) != len(categories)
            ):
                raise ValueError("Invalid or repeated attraction categories")
            result = [row for row in providers.attractions(categories) if row["id"] not in self.trip.excluded_ids]
        elif name == "search_hotels":
            result = []
            for hotel in providers.hotels():
                total = hotel["referenceRubPerPersonNight"] * self.trip.travelers * self.trip.nights
                if hotel["id"] in self.trip.excluded_ids:
                    continue
                if self.trip.target == "hotels" and total > self.trip.option_budget_rub:
                    continue
                result.append({**hotel, "referenceGroupTotalRub": total})
        else:
            result = providers.museum_rate()
        self.results[name] = result
        self.calls.append({"id": call["id"], "name": name, "arguments": args})
        return result

    def validate_decision(self, raw):
        decision = json.loads(raw)
        exact_fields(decision, DECISION_SCHEMA["properties"])
        hotels = ranked(decision["hotelIds"], self.results.get("search_hotels", []))
        places = ranked(decision["attractionIds"], self.results.get("search_attractions", []))
        visits = decision["paidMuseumVisitsPerPerson"]
        budget = None
        if visits is not None:
            if type(visits) is not int or not 0 <= visits <= 2 * (self.trip.nights + 1):
                raise ValueError("Invalid visit count for experiment")
            rate = self.results.get("get_budget_rates")
            if rate is None:
                raise ValueError("Budget decision without a source rate")
            budget = {
                **rate, "suggestedVisitsPerPerson": visits,
                "groupTotalRub": visits * rate["perVisitPerPersonRub"] * self.trip.travelers,
            }
        return {"hotels": hotels, "attractions": places, "museumEstimate": budget}

    def run(self, client):
        trip = {
            "city": "Москва", "target": self.trip.target, "preferences": self.trip.preferences,
            "refinement": self.trip.refinement, "travelers": self.trip.travelers,
            "nights": self.trip.nights, "optionBudgetRub": self.trip.option_budget_rub,
        }
        if self.trip.start_date is not None:
            trip.update(startDate=self.trip.start_date, endDate=self.trip.end_date, budgetRub=self.trip.budget_rub)
        messages = [{"role": "system", "content": self.search_prompt}, {"role": "user", "content": encode(trip)}]
        for name in self.allowed:
            message = client.complete(
                messages, tools=[TOOLS[name]], tool_choice="required",
            )
            calls = message.get("tool_calls") or []
            if len(calls) != 1:
                raise ValueError("Expected exactly one structured tool_calls entry during search")
            if calls[0]["function"]["name"] != name:
                raise ValueError(f"Expected {name} at this search step")
            self.dispatch(calls[0])
        # Carry validated tool results into a separate JSON decision request.
        # Present hotels cheapest first as the baseline recommendation order.
        hotels = sorted(
            self.results.get("search_hotels", []), key=lambda row: row["referenceGroupTotalRub"],
        )
        evidence = {
            "hotels": [
                {k: row[k] for k in ("id", "name", "referenceGroupTotalRub")}
                for row in hotels
            ],
            "attractions": [
                {k: row[k] for k in ("id", "name", "category")}
                for row in self.results.get("search_attractions", [])
            ],
            "museumRate": self.results.get("get_budget_rates"),
        }
        decision_schema = object_schema({
            **DECISION_SCHEMA["properties"],
            **{
                field: {
                    **DECISION_SCHEMA["properties"][field],
                    "minItems": len(evidence[source]),
                    "maxItems": len(evidence[source]),
                }
                for field, source in (("hotelIds", "hotels"), ("attractionIds", "attractions"))
            },
        })
        if self.constrain_decision_values:
            for field, source in (("hotelIds", "hotels"), ("attractionIds", "attractions")):
                if evidence[source]:
                    decision_schema["properties"][field]["items"] = {
                        "type": "string", "enum": [row["id"] for row in evidence[source]],
                    }
            if evidence["museumRate"] is None:
                decision_schema["properties"]["paidMuseumVisitsPerPerson"] = {"type": "null"}
        message = client.complete(
            [{"role": "system", "content": self.decision_prompt},
             {"role": "user", "content": encode({"trip": trip, "evidence": evidence})}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "tripflow_decision", "strict": True, "schema": decision_schema,
            }},
        )
        if message.get("tool_calls") or not isinstance(message.get("content"), str):
            raise ValueError("Expected JSON decision in assistant.content")
        return self.validate_decision(message["content"])

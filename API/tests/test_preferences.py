import asyncio
import inspect
import json
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from tripflow_api.main import app, budget_examples, recommendation_examples
from tripflow_api.preference_model import PROMPT_VERSION, AnalysisError, parse_conditions
from tripflow_api.preference_numbers import Quantity, quantities
from tripflow_api.preferences import WINDOW_SECONDS
from tripflow_api.schemas import RecommendationsRequest


BREAKFAST = "Обязательно завтрак до 7:00"
METRO = "Желательно у метро"
MUSEUM = "Музей космонавтики не предлагать"
TAXI = "На такси не ездим"
RARE = "Нужна швейная машинка в отеле"
TEXT = ". ".join(("Парковка у аэропорта", BREAKFAST, METRO, MUSEUM, TAXI, RARE))


def condition(scope, role, quote, meaning=None):
    return {"scope": scope, "role": role, "quote": quote, "meaning": meaning or quote, "ambiguous": False}


BASE = [condition("hotels", "required", BREAKFAST), condition("hotels", "preferred", METRO),
        condition("attractions", "excluded", MUSEUM), condition("budget", "note", TAXI),
        condition("hotels", "required", RARE)]
USAGE = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30,
         "prompt_cache_hit_tokens": 4, "prompt_cache_miss_tokens": 16}
DETAILS = "/portal/data/preferences/tasks/"
BUILDER = "/portal/data/builder"


def reply(content, usage=USAGE):
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    return httpx.Response(200, json={"model": "deepseek-flash", "usage": usage, "choices": [
        {"finish_reason": "stop", "message": {"content": content, "reasoning_content": "private provider text"}},
    ]})


def recommendation(text=TEXT, refinement=None, category="hotels", task_id=None):
    body = recommendation_examples[category]["value"]
    return {**body, "taskId": task_id or uuid4().hex, "refinement": refinement,
            "trip": {**body["trip"], "preferences": text}}


class PreferenceRulesTest(unittest.TestCase):
    def test_price_basis_stays_local_with_usually_costs(self):
        dinner = "Ужин на человека обычно стоит до 1 200 рублей"
        cases = (
            ("Ужин на человека до 1 200 рублей", dinner, 1200, ("person",), ("person",)),
            (dinner, "Ужин обычно стоит до 1200 ₽ на человека", 1200, ("person",), ("person",)),
            (dinner, "Ужин на всю группу обычно стоит до 1 200 рублей", 1200, ("person",), ("group",)),
            (dinner, "Ужин обычно стоит до 1 200 рублей", 1200, ("person",), ()),
            ("На всю группу трансфер обычно стоит до 700 ₽", "Трансфер на человека обычно стоит до 700 ₽",
             700, ("group",), ("person",)),
        )
        for quote, meaning, amount, quoted_basis, stated_basis in cases:
            with self.subTest(quote=quote, meaning=meaning):
                item = condition("budget", "preferred", quote, meaning)
                payload = json.dumps({"conditions": [item]})
                if quoted_basis == stated_basis:
                    self.assertEqual(len(parse_conditions(payload, {"preferences": quote})["conditions"]), 1)
                else:
                    with self.assertRaisesRegex(AnalysisError, "numeric_conflict") as error:
                        parse_conditions(payload, {"preferences": quote})
                    self.assertTrue(error.exception.retryable)
                self.assertEqual(quantities(quote), {Quantity("rubles", amount, "upper", quoted_basis)})
                self.assertEqual(quantities(meaning), {Quantity("rubles", amount, "upper", stated_basis)})
        for separator in (", а ", ". ", "\n"):
            with self.subTest(separator=separator):
                text = f"Ужин на человека{separator}такси обычно стоит до 700 ₽"
                self.assertEqual(quantities(text), {Quantity("rubles", 700, "upper")})
        self.assertEqual(quantities(dinner + "\nНа всю группу трансфер обычно стоит до 700 ₽"),
                         {Quantity("rubles", 1200, "upper", ("person",)), Quantity("rubles", 700, "upper", ("group",))})

    def test_price_basis_follows_its_amount_across_short_wording(self):
        quote = "Ужин на человека до 1 200 рублей"
        expected = {Quantity("rubles", 1200, "upper", ("person",))}
        for meaning in ("Ужин на человека должен стоить до 1 200 рублей", "Ужин должен стоить до 1200 ₽ на человека"):
            with self.subTest(meaning=meaning):
                item = condition("budget", "required", quote, meaning)
                self.assertEqual(quantities(quote), expected)
                self.assertEqual(quantities(meaning), expected)
                self.assertEqual(len(parse_conditions(json.dumps({"conditions": [item]}), {"preferences": quote})["conditions"]), 1)
        for meaning in ("Ужин на всю группу должен стоить до 1 200 рублей", "Ужин должен стоить до 1 200 рублей"):
            item = condition("budget", "required", quote, meaning)
            with self.subTest(meaning=meaning), self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                parse_conditions(json.dumps({"conditions": [item]}), {"preferences": quote})

        taxi = "Такси на всю группу до 700 ₽"
        other = "Такси на всю группу может обойтись не дороже 700 рублей"
        both = expected | {Quantity("rubles", 700, "upper", ("group",))}
        self.assertEqual(quantities(f"{quote}, а {other}"), both)
        self.assertEqual(quantities("Ужин на человека, такси должно стоить до 700 ₽"), {Quantity("rubles", 700, "upper")})
        text = f"{quote}. {taxi}."
        items = [condition("budget", "required", quote, "Ужин на человека должен стоить до 1 200 рублей"),
                 condition("budget", "required", taxi, other)]
        self.assertEqual(len(parse_conditions(json.dumps({"conditions": items}), {"preferences": text})["conditions"]), 2)
        for index, swap in enumerate(("Ужин на группу до 1200 ₽", "Такси на человека до 700 ₽")):
            wrong = [{**item, "meaning": swap} if i == index else item for i, item in enumerate(items)]
            with self.subTest(index=index), self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                parse_conditions(json.dumps({"conditions": wrong}), {"preferences": text})

    def test_explicit_time_preservation_requires_the_linked_bound_even_with_partial_quote(self):
        breakfast = "Обязателен завтрак до 07:00"
        transfer = "Нужен трансфер в 09:00"
        base = [{"index": i, **condition("hotels", "required", quote), "source": "preferences"}
                for i, quote in enumerate((breakfast, transfer))]
        text = breakfast + ". " + transfer
        for keep in ("Время оставляем прежним", "Время не меняем", "По времени всё остаётся как было"):
            refinement = keep + ", но теперь это пожелание"
            data = {"preferences": text, "category": "hotels", "base": base, "refinement": refinement}
            for citation in (refinement, "теперь это пожелание"):
                good = condition("hotels", "preferred", citation, "Желателен завтрак до 7:00")
                change = {"index": 0, "quote": citation, "replacement": good}
                result = parse_conditions(json.dumps({"changes": [change], "additions": []}), data)
                self.assertIn(base[1]["quote"], [item["quote"] for item in result["conditions"]])
                self.assertEqual(result["changes"][0]["replacement"]["role"], "preferred")
                for meaning in (None, "Желателен завтрак", "Желателен завтрак после 07:00", "Желателен завтрак до 09:00"):
                    wrong = {**change, "replacement": None if meaning is None else {**good, "meaning": meaning}}
                    with self.subTest(keep=keep, citation=citation, meaning=meaning), self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                        parse_conditions(json.dumps({"changes": [wrong], "additions": []}), data)

    def test_later_change_to_breakfast_time_does_not_affect_other_conditions(self):
        transfer = "Трансфер в 09:00"
        base = [{"index": i, **condition("hotels", "required", quote), "source": "preferences"}
                for i, quote in enumerate((BREAKFAST, transfer))]
        cases = (
            ("Теперь завтрак нужен до 08:00", "Завтрак обязателен до 8:00", "Завтрак обязателен до 07:00"),
            ("Время завтрака больше не важно, сам завтрак обязателен", "Завтрак обязателен", "Завтрак обязателен до 7:00"),
            ("Время пока оставим прежним. Передумали: завтрак подойдёт в любое время", "Завтрак обязателен", "Завтрак обязателен до 7:00"),
            ("Время пока оставим прежним. Теперь завтрак нужен до 08:00", "Завтрак обязателен до 8:00", "Завтрак обязателен до 07:00"),
            ("Время не меняем. Передумали: теперь завтрак нужен до 08:00", "Завтрак обязателен до 8:00", "Завтрак обязателен до 07:00"),
            ("Время завтрака прежнее. Теперь трансфер в 10:00. Завтрак пусть будет пожеланием", "Желателен завтрак до 7:00", "Желателен завтрак"),
            ("Время трансфера оставляем прежним. Время завтрака больше не важно", "Завтрак обязателен", "Завтрак обязателен до 7:00"),
            ("Время трансфера не меняем. Время завтрака не важно, сам завтрак обязателен", "Завтрак обязателен", "Завтрак обязателен до 7:00"),
            ("Время пока оставим прежним. Завтрак вообще больше не нужен как условие", None, "Завтрак обязателен до 7:00"),
        )
        for refinement, meaning, wrong in cases:
            with self.subTest(refinement=refinement):
                citation = refinement.rsplit(". ", 1)[-1]
                data = {"preferences": BREAKFAST + ". " + transfer, "category": "hotels", "base": base, "refinement": refinement}
                replacement = condition("hotels", "required", citation, meaning) if meaning else None
                change = {"index": 0, "quote": citation, "replacement": replacement}
                result = parse_conditions(json.dumps({"changes": [change], "additions": []}), data)
                self.assertIn(transfer, [item["quote"] for item in result["conditions"]])
                if meaning is None:
                    self.assertEqual(len(result["conditions"]), 1)
                else:
                    with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                        parse_conditions(json.dumps({"changes": [{**change, "replacement": None}], "additions": []}), data)
                change["replacement"] = condition("hotels", "required", citation, wrong)
                with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                    parse_conditions(json.dumps({"changes": [change], "additions": []}), data)

        keep_transfer = "Время трансфера не меняем"
        release_breakfast = "Время завтрака не важно, сам завтрак обязателен"
        data = {"preferences": BREAKFAST + ". " + transfer, "category": "hotels", "base": base,
                "refinement": keep_transfer + ". " + release_breakfast}
        changes = [
            {"index": 0, "quote": release_breakfast,
             "replacement": condition("hotels", "required", release_breakfast, "Завтрак обязателен")},
            {"index": 1, "quote": keep_transfer,
             "replacement": condition("hotels", "required", keep_transfer, transfer)},
        ]
        result = parse_conditions(json.dumps({"changes": changes, "additions": []}), data)
        self.assertEqual([item["meaning"] for item in result["conditions"]], ["Завтрак обязателен", transfer])
        changes[1]["replacement"] = condition("hotels", "required", keep_transfer, "Трансфер в 07:00")
        with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
            parse_conditions(json.dumps({"changes": changes, "additions": []}), data)

    def test_recognized_quantities_keep_value_boundary_and_price_basis(self):
        cases = (
            ("Breakfast before 07:00", "Breakfast after 09:00", False),
            ("Завтрак до 07:00", "Завтрак до 7:00", True),
            ("Завтрак до 7 утра", "Завтрак до 07:00", True),
            ("Завтрак до 07:00", "Завтрак после 07:00", False),
            ("Завтрак до 07:00", "Завтрак до 07:30", False),
            ("Обед до 900 ₽ с человека в день", "Обед на человека до 900 рублей за день", True),
            ("Обед до 900 ₽ с человека в день", "Обед до 900 ₽ на всю группу в день", False),
            ("Обед до 900 ₽ с человека в день", "Обед до 900 ₽ с человека за всю поездку", False),
            ("До метро не больше 1,5 км", "До метро не больше 1500 м", True),
            ("До метро не больше 1,5 км", "До метро не больше 150 м", False),
            ("Пускают с собакой до 12 кг", "Пускают с собакой до 15 кг", False),
        )
        for quote, meaning, accepted in cases:
            with self.subTest(quote=quote, meaning=meaning):
                item = condition("hotels", "required", quote, meaning)
                payload = json.dumps({"conditions": [item]})
                if accepted:
                    self.assertEqual(len(parse_conditions(payload, {"preferences": quote})["conditions"]), 1)
                else:
                    with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                        parse_conditions(payload, {"preferences": quote})

    def test_numeric_evidence_is_local_to_the_condition_and_linked_base(self):
        transfer = "Трансфер в 9:00"
        text = BREAKFAST + ". " + transfer
        changed = condition("hotels", "required", BREAKFAST, "Завтрак до 9:00")
        with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
            parse_conditions(json.dumps({"conditions": [changed]}), {"preferences": text})
        base = [{"index": i, **condition("hotels", "required", quote), "source": "preferences"}
                for i, quote in enumerate((BREAKFAST, transfer))]
        refinement = "Достаточно, если получится"
        data = {"preferences": text, "category": "hotels", "base": base, "refinement": refinement}
        replacement = condition("hotels", "preferred", refinement, "Желателен завтрак до 7:00")
        change = {"index": 0, "quote": refinement, "replacement": replacement}
        result = parse_conditions(json.dumps({"changes": [change], "additions": []}), data)
        self.assertEqual(result["changes"][0]["previous"]["quote"], BREAKFAST)
        for changes, additions in (([{**change, "index": 1}], []), ([], [replacement])):
            with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
                parse_conditions(json.dumps({"changes": changes, "additions": additions}), data)
        new_quote = "Вместо этого нужен завтрак до 08:00"
        data["refinement"] = new_quote + ". " + refinement
        amended = {**change, "quote": new_quote}
        with self.assertRaisesRegex(AnalysisError, "numeric_conflict"):
            parse_conditions(json.dumps({"changes": [amended], "additions": []}), data)
        amended["replacement"] = {**replacement, "meaning": "Желателен завтрак до 8:00"}
        result = parse_conditions(json.dumps({"changes": [amended], "additions": []}), data)
        self.assertEqual(result["changes"][0]["replacement"]["role"], "preferred")

    def test_exact_quotes_allow_whitespace_and_remove_duplicates(self):
        item = condition("hotels", "required", "Завтрак до 7:00")
        result = parse_conditions(json.dumps({"conditions": [item, item]}), {"preferences": "Завтрак\n  до 7:00"})
        self.assertEqual(len(result["conditions"]), 1)
        self.assertEqual(result["conditions"][0]["quote"], "Завтрак\n  до 7:00")
        for altered in ("завтрак до 7:00", "Завтрак после 7:00", "Завтрак до 7.00"):
            with self.assertRaisesRegex(AnalysisError, "invalid_quote"):
                parse_conditions(json.dumps({"conditions": [{**item, "quote": altered}]}), {"preferences": "Завтрак до 7:00"})

    def test_validation_rejects_unknown_fields_types_and_cross_category_edits(self):
        for item in ({**BASE[0], "ambiguous": "false"}, {**BASE[0], "unexpected": True},
                     {**BASE[0], "scope": "transport"}, {**BASE[0], "quote": " "}):
            with self.assertRaisesRegex(AnalysisError, "invalid_response"):
                parse_conditions(json.dumps({"conditions": [item]}), {"preferences": TEXT})
        data = {"preferences": TEXT, "refinement": MUSEUM, "category": "hotels", "base": []}
        with self.assertRaisesRegex(AnalysisError, "invalid_response"):
            parse_conditions(json.dumps({"changes": [], "additions": [BASE[2]]}), data)


class PreferenceApiTest(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(TemporaryDirectory())
        url = os.getenv("TRIPFLOW_TEST_DATABASE_URL", "")
        if url:
            import psycopg
            from psycopg.conninfo import make_conninfo

            schema = "preferences_test_" + uuid4().hex
            connection = self.resources.enter_context(psycopg.connect(url, autocommit=True))
            connection.execute(f"CREATE SCHEMA {schema}")
            self.resources.callback(connection.execute, f"DROP SCHEMA {schema} CASCADE")
            url = make_conninfo(url, options=f"-c search_path={schema}")
        self.owner = {"email": "preferences-owner@example.test", "password": "preferences-owner-password"}
        self.resources.enter_context(patch.dict(os.environ, {
            "TRIPFLOW_STATE_PATH": str(Path(directory) / "state.sqlite3"), "DATABASE_URL": url,
            "TRIPFLOW_PORTAL_ADMIN_EMAIL": self.owner["email"], "TRIPFLOW_PORTAL_ADMIN_PASSWORD": self.owner["password"],
            "DEEPSEEK_API_KEY": "test-provider-key", "RENDER": "",
        }))
        self.calls = []
        self.handle = lambda _: reply({"conditions": BASE})
        self.start()

    async def transport(self, request):
        self.assertEqual(str(request.url), "https://api.deepseek.com/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer test-provider-key")
        body = json.loads(request.content)
        self.calls.append(body)
        response = self.handle(body)
        return await response if inspect.isawaitable(response) else response

    def start(self, key="test-provider-key"):
        self.server = ExitStack()
        self.resources.callback(self.server.close)
        original = httpx.AsyncClient
        self.server.enter_context(patch.dict(os.environ, {"DEEPSEEK_API_KEY": key}))
        self.server.enter_context(patch("tripflow_api.main.httpx.AsyncClient", side_effect=lambda **kwargs:
                                       original(transport=httpx.MockTransport(self.transport), **kwargs)))
        self.client = self.server.enter_context(TestClient(app, headers={"X-Portal-Request": "1"}))
        self.account = self.login(self.owner)

    def login(self, user):
        self.client.cookies.clear()
        response = self.client.post("/portal/data/login", json=user)
        self.assertEqual(response.status_code, 200)
        return response.json()["account"]

    def api_key(self):
        return {"X-API-Key": self.client.post("/portal/data/keys/api/issue", json={}).json()["key"]}

    def details(self, task_id):
        response = self.client.get(DETAILS + task_id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private provider text", response.text)
        return response.json()

    def submit(self, body, prefix=BUILDER, headers=None, operation="recommendations"):
        accepted = self.client.post(prefix + "/" + operation, json=body, headers=headers)
        self.assertEqual(accepted.status_code, 202, accepted.text)
        result = self.client.get(accepted.headers["Location"], headers=headers).json()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(set(result), {"taskId", "status", "result"})
        return result["result"]

    def summary(self):
        return self.client.get("/portal/data/activity").json()["preferences"]

    def test_price_paraphrase_finishes_on_first_provider_attempt(self):
        dinner = "Ужин на человека до 1 200 рублей"
        walk = "Хотелось бы набережную"
        wheel = "колесо обозрения точно пропустим"
        items = [condition("budget", "required", dinner, "Ужин на человека обычно стоит до 1 200 рублей"),
                 condition("attractions", "preferred", walk), condition("attractions", "excluded", wheel)]
        self.handle = lambda _: reply({"conditions": items})
        body = recommendation(f"{dinner}. {walk}, но {wheel}", category="attractions")
        self.submit(body)
        record = self.details(body["taskId"])
        self.assertEqual(record["status"], "succeeded")
        stage = record["stages"][0]
        self.assertEqual([item["quote"] for item in stage["result"]["conditions"]], [dinner, walk, wheel])
        self.assertEqual([item["error"] for item in stage["attempts"]], [None])
        self.assertEqual(self.summary()["usage"]["totalTokens"], 30)

    def test_missing_inherited_clock_retries_without_losing_provider_usage_or_mock(self):
        base = "Обязателен завтрак до 07:00"
        refinement = "Время не меняем, но теперь это пожелание"
        refinement_calls = []

        def answer(body):
            data = json.loads(body["messages"][1]["content"])
            if "refinement" not in data:
                return reply({"conditions": [condition("hotels", "required", base)]})
            refinement_calls.append(data["refinement"])
            citation = "теперь это пожелание"
            meaning = "Желателен завтрак до 07:00" if len(refinement_calls) == 2 else "Желателен завтрак"
            replacement = None if len(refinement_calls) == 4 else condition("hotels", "preferred", citation, meaning)
            return reply({"changes": [{"index": 0, "quote": citation, "replacement": replacement}], "additions": []})

        self.handle = answer
        corrected = recommendation(base, refinement)
        mock = self.submit(corrected)["results"]
        record = self.details(corrected["taskId"])
        self.assertEqual(record["status"], "succeeded")
        stage = record["stages"][-1]
        self.assertEqual([item["error"] for item in stage["attempts"]], ["numeric_conflict", None])
        self.assertEqual(sum(item["usage"]["totalTokens"] for item in stage["attempts"]), 60)
        current = stage["result"]["conditions"][0]
        self.assertEqual((current["role"], current["meaning"]), ("preferred", "Желателен завтрак до 07:00"))

        exhausted = recommendation(base, refinement + ". Остальное без изменений")
        self.assertEqual(self.submit(exhausted)["results"], mock)
        record = self.details(exhausted["taskId"])
        self.assertEqual((record["status"], record["error"]), ("failed", "numeric_conflict"))
        self.assertEqual(record["stages"][0]["source"], "reused")
        self.assertEqual([item["error"] for item in record["stages"][-1]["attempts"]], ["numeric_conflict", "numeric_conflict"])
        self.assertEqual(self.summary()["usage"]["totalTokens"], 150)

    def test_numeric_conflict_retries_and_keeps_usage_for_both_attempts(self):
        quote = "Breakfast before 07:00"

        def answer(_):
            meaning = "Breakfast after 09:00" if len(self.calls) == 1 else "Завтрак до 7:00"
            return reply({"conditions": [condition("hotels", "required", quote, meaning)]})

        self.handle = answer
        body = recommendation(quote)
        self.submit(body)
        record = self.details(body["taskId"])
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual([item["error"] for item in record["stages"][0]["attempts"]], ["numeric_conflict", None])
        self.assertIn("числа", self.calls[1]["messages"][0]["content"])
        self.assertEqual(self.summary()["usage"]["totalTokens"], 60)

        self.handle = lambda _: reply({"conditions": [condition("hotels", "required", quote, "Breakfast after 09:00")]})
        body = recommendation("Хотим отель. " + quote)
        self.assertTrue(self.submit(body)["results"]["hotels"]["items"])
        record = self.details(body["taskId"])
        self.assertEqual((record["status"], record["error"]), ("failed", "numeric_conflict"))
        self.assertIsNone(record["stages"][0]["result"])
        self.assertEqual(self.summary()["usage"]["totalTokens"], 120)

    def test_instruction_version_refreshes_cache_without_rewriting_history(self):
        legacy = recommendation()
        with patch("tripflow_api.preferences.PROMPT_VERSION", "stage1-v6"):
            legacy_result = self.submit(legacy)
        self.assertEqual(self.submit(legacy), legacy_result)
        history = self.details(legacy["taskId"])["stages"][0]
        self.assertEqual(history["version"], "stage1-v6")

        for category, source in (("hotels", "call"), ("attractions", "reused")):
            body = recommendation(category=category)
            self.submit(body)
            stage = self.details(body["taskId"])["stages"][0]
            self.assertEqual((stage["version"], stage["source"]), (PROMPT_VERSION, source))
            self.assertNotEqual(stage["id"], history["id"])
        self.assertEqual(len(self.calls), 2)

    def test_empty_and_refinement_only_then_budget(self):
        empty = recommendation(" \n ", " \t")
        mock = self.submit(empty)
        self.assertTrue(mock["results"]["hotels"]["items"])
        self.assertEqual(self.details(empty["taskId"])["status"], "empty")
        self.assertEqual(self.summary()["attempts"], 0)
        self.assertIsNone(self.summary()["averageMs"])
        self.handle = lambda _: reply({"changes": [], "additions": [condition("hotels", "required", RARE)]})
        only = recommendation(None, RARE)
        self.assertEqual(self.submit(only)["results"], mock["results"])
        stage = self.details(only["taskId"])["stages"][-1]
        self.assertEqual(stage["result"]["conditions"][0]["source"], "refinement")
        selected = mock["results"]["hotels"]["items"][0]
        places = self.submit(recommendation(None, category="attractions"))["results"]["attractions"]["items"]
        result = self.submit({**budget_examples["budget"]["value"], "taskId": uuid4().hex,
                              "selectedHotel": {key: selected[key] for key in ("objectId", "price")},
                              "selectedAttractions": [{key: places[0][key] for key in ("objectId", "price")}]}, operation="budget")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(result["expenses"]), 4)
        self.assertEqual(self.summary()["attempts"], 1)

    def test_refinement_changes_only_affected_category_and_reuses_base(self):
        first = "Завтрак необязателен. Нужен заезд после полуночи"
        second = first + ". Вместо этого заезд после 22:00"

        def answer(body):
            data = json.loads(body["messages"][1]["content"])
            if "refinement" not in data:
                self.assertEqual(data, {"preferences": TEXT})
                return reply({"conditions": BASE})
            breakfast = "Завтрак необязателен"
            arrival = "Вместо этого заезд после 22:00" if data["refinement"] == second else "Нужен заезд после полуночи"
            return reply({"changes": [{"index": 0, "quote": breakfast,
                                       "replacement": condition("hotels", "preferred", breakfast, "Завтрак до 7:00 необязателен")}],
                          "additions": [condition("hotels", "required", arrival)]})

        self.handle = answer
        original = recommendation()
        self.submit(original)
        base = self.details(original["taskId"])["stages"][0]["result"]["conditions"]
        self.assertEqual([{key: item[key] for key in BASE[0]} for item in base], BASE)
        for refinement in (first, second, second):
            body = recommendation(refinement=refinement)
            self.submit(body)
            stages = self.details(body["taskId"])["stages"]
            self.assertEqual(stages[0]["result"]["conditions"], base)
            updated = stages[-1]["result"]["conditions"]
            self.assertEqual({item["scope"] for item in updated}, {"hotels"})
            self.assertIn(METRO, [item["quote"] for item in updated])
            self.assertIn("preferred", [item["role"] for item in updated if item["quote"] == "Завтрак необязателен"])
            if refinement == second:
                self.assertEqual(updated[-1]["quote"], "Вместо этого заезд после 22:00")
        self.assertEqual(self.summary()["attempts"], 3)
        self.assertEqual(self.summary()["reused"], 4)

    def test_invalid_response_and_quote_keep_both_attempts_and_mock(self):
        self.handle = lambda _: reply("{") if len(self.calls) == 1 else reply({"conditions": [{**BASE[0], "quote": "выдуманная цитата"}]})
        body = recommendation()
        self.assertEqual(self.submit(body)["results"], self.submit(recommendation(None))["results"])
        record = self.details(body["taskId"])
        self.assertEqual((record["status"], record["error"]), ("failed", "invalid_quote"))
        self.assertEqual([attempt["error"] for attempt in record["stages"][0]["attempts"]], ["invalid_response", "invalid_quote"])
        self.assertIn("Исправление", self.calls[1]["messages"][0]["content"])
        self.assertEqual(self.summary()["usage"]["totalTokens"], 60)
        self.handle = lambda _: reply({"conditions": BASE})
        revived = recommendation()
        self.submit(revived)
        self.assertEqual(self.details(revived["taskId"])["status"], "succeeded")

    def test_failed_refinement_keeps_successful_base(self):
        def answer(body):
            data = json.loads(body["messages"][1]["content"])
            return httpx.Response(401) if "refinement" in data else reply({"conditions": BASE})

        self.handle = answer
        body = recommendation(refinement="Завтрак необязателен")
        self.assertTrue(self.submit(body)["results"]["hotels"]["items"])
        record = self.details(body["taskId"])
        self.assertEqual(record["status"], "failed")
        self.assertEqual([stage["status"] for stage in record["stages"]], ["succeeded", "failed"])
        self.assertEqual(self.summary()["tasks"], {"failed": 1})
        self.assertEqual(self.summary()["attempts"], 2)

    def test_timeout_authorization_limits_and_unconfigured(self):
        def timeout(request):
            raise httpx.ReadTimeout("fake private error")

        self.handle = timeout
        body = recommendation()
        self.submit(body)
        self.assertEqual(self.details(body["taskId"])["error"], "timeout")
        self.assertIsNone(self.summary()["usage"]["totalTokens"])
        self.assertEqual(self.summary()["incompleteUsage"], 2)
        self.handle = lambda _: httpx.Response(401)
        body = recommendation()
        self.submit(body)
        self.assertEqual(self.details(body["taskId"])["error"], "authorization")
        self.assertEqual(len(self.calls), 3)
        self.handle = lambda _: httpx.Response(429)
        body = recommendation()
        self.submit(body)
        self.assertEqual(self.details(body["taskId"])["error"], "rate_limit")
        self.assertEqual(len(self.calls), 5)
        self.handle = lambda _: reply({"conditions": []}, usage=None)
        body = recommendation()
        self.submit(body)
        self.assertEqual(self.details(body["taskId"])["status"], "succeeded")
        self.assertEqual(self.summary()["incompleteUsage"], 6)
        self.handle = lambda _: reply({"conditions": []}, usage={key: 0 for key in USAGE})
        self.submit(recommendation("Другой текст"))
        self.assertEqual(self.summary()["usage"]["totalTokens"], 0)
        self.server.close()
        self.start(key="")
        for text, expected in (("Ещё текст", "unconfigured"), ("А" * 6001, "failed")):
            body = recommendation(text)
            self.submit(body)
            self.assertEqual(self.details(body["taskId"])["status"], expected)
        self.assertEqual(len(self.calls), 7)

    def test_parallel_public_and_builder_share_analysis_and_idempotency(self):
        started = Event()
        release = Event()

        async def delayed(_):
            started.set()
            if not await asyncio.to_thread(release.wait, 5):
                raise AssertionError("provider was not released")
            return reply({"conditions": BASE})

        self.handle = delayed
        public = recommendation()
        builder = recommendation(category="attractions")
        key = self.api_key()
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(self.submit, public, "/v1", key)
            try:
                self.assertTrue(started.wait(5))
                local = pool.submit(self.submit, builder)
                for _ in range(100):
                    if self.details(public["taskId"])["status"] == "pending" and self.client.get(DETAILS + builder["taskId"]).status_code == 200:
                        break
                    time.sleep(0.01)
                else:
                    self.fail("second task was not accepted while the provider was waiting")
                self.assertEqual(self.client.get("/v1/tasks/" + public["taskId"], headers=key).json()["status"], "pending")
            finally:
                release.set()
            pending.result()
            local.result()
        self.assertEqual(self.details(public["taskId"])["stages"][0]["id"], self.details(builder["taskId"])["stages"][0]["id"])
        self.assertEqual(self.details(builder["taskId"])["stages"][0]["source"], "reused")
        self.submit(public, "/v1", key)
        self.assertEqual(self.client.post("/v1/recommendations", json={**public, "count": 1}, headers=key).status_code, 409)
        for _ in range(2):
            self.assertEqual(self.summary()["usage"]["totalTokens"], 30)
        self.assertEqual(len(self.calls), 1)

    def test_isolation_same_id_and_seven_day_boundaries(self):
        private = recommendation()
        self.submit(private)
        user = {"email": "preferences-developer@example.test", "password": "preferences-developer-password"}
        self.assertEqual(self.client.post("/portal/data/register", json=user).json(), {"status": "pending"})
        users = self.client.get("/portal/data/admin/accounts").json()["accounts"]
        developer_id = next(row["id"] for row in users if row["email"] == user["email"])
        self.assertEqual(self.client.post(f"/portal/data/admin/accounts/{developer_id}", json={"action": "approve"}).status_code, 200)
        self.login(user)
        self.assertEqual(self.client.get(DETAILS + private["taskId"]).status_code, 404)
        self.assertEqual(self.summary()["attempts"], 0)
        self.submit(recommendation(task_id=private["taskId"]))
        other = self.details(private["taskId"])["stages"][0]
        self.assertEqual(other["source"], "call")
        self.login(self.owner)
        own = self.details(private["taskId"])["stages"][0]
        self.assertNotEqual(other["id"], own["id"])
        self.assertEqual(self.summary()["attempts"], 1)
        db = app.state.tasks.connection
        now = int(time.time())
        with patch("tripflow_api.preferences.time.time", return_value=now):
            start = now - WINDOW_SECONDS
            # Database operations must run on the application's thread (SQLite).
            portal = self.client.portal
            portal.call(db.execute, "UPDATE preference_attempts SET started_at = ? WHERE run_id = ?", (start, own["id"]))
            portal.call(db.execute, "UPDATE tasks SET created_at = ? WHERE client_id = ?", (start - 1, self.account["id"]))
            summary = self.summary()
            self.assertEqual(summary["attempts"], 1)
            self.assertEqual(summary["tasks"], {})
            portal.call(db.execute, "UPDATE preference_attempts SET started_at = ? WHERE run_id = ?", (start - 1, own["id"]))
            self.assertEqual(self.summary()["attempts"], 0)

    def test_restart_reuses_success_and_finishes_expired_attempt_without_rebilling(self):
        first = recommendation()
        result = self.submit(first)
        stalled = recommendation("Другие пожелания")
        store = app.state.tasks
        portal = self.client.portal
        portal.call(store.accept, self.account["id"], "recommendations", RecommendationsRequest.model_validate(stalled))
        run_id, execute = portal.call(store.preferences.claim, self.account["id"], stalled["taskId"], "preferences",
                                      {"preferences": stalled["trip"]["preferences"]}, None)
        self.assertTrue(execute)
        portal.call(store.connection.execute, "UPDATE preference_runs SET expires_at = 0 WHERE id = ?", (run_id,))
        portal.call(store.connection.execute, "INSERT INTO preference_attempts (client_id, run_id, number, started_at) VALUES (?, ?, 1, ?)",
                    (self.account["id"], run_id, int(time.time())))
        self.server.close()
        self.start()
        self.assertEqual(self.submit(first), result)
        self.submit(recommendation())
        for _ in range(30):
            diagnosed = self.details(stalled["taskId"])
            if diagnosed["status"] != "pending":
                break
            time.sleep(0.01)
        self.assertEqual(diagnosed["error"], "interrupted")
        self.assertIsNone(diagnosed["stages"][0]["attempts"][0]["usage"])
        self.assertEqual(len(self.calls), 1)
        self.handle = lambda _: reply({"conditions": []})
        new = recommendation(stalled["trip"]["preferences"])
        self.submit(new)
        self.assertEqual(self.details(new["taskId"])["status"], "succeeded")
        self.assertEqual(len(self.calls), 2)

import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tripflow_api.main import app, budget_examples, recommendation_examples
from tripflow_api.schemas import BudgetRequest


class PollingTest(unittest.TestCase):
    def setUp(self):
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        directory = self.resources.enter_context(tempfile.TemporaryDirectory())
        self.admin = {"email": "owner@example.test", "password": "local-admin-test"}
        self.resources.enter_context(patch.dict(os.environ, {
            "TRIPFLOW_PORTAL_ADMIN_EMAIL": self.admin["email"],
            "TRIPFLOW_PORTAL_ADMIN_PASSWORD": self.admin["password"],
            "TRIPFLOW_STATE_PATH": str(Path(directory) / "tasks.sqlite3"),
            "DATABASE_URL": os.getenv("TRIPFLOW_TEST_DATABASE_URL", ""),
        }))
        self.client = self.resources.enter_context(TestClient(app))
        self.client.headers["X-Portal-Request"] = "1"

    def post(self, route, body=None):
        return self.client.post("/portal/data/" + route, json=body or {})

    def login(self, user):
        self.client.cookies.clear()
        return self.post("login", user)

    def make_user(self):
        user = {"email": uuid4().hex + "@example.test", "password": "developer-test"}
        self.assertEqual(self.post("register", user).json(), {"status": "pending"})
        self.assertEqual(self.login(user).status_code, 403)
        self.assertEqual(self.login(self.admin).status_code, 200)
        users = self.client.get("/portal/data/admin/accounts").json()["accounts"]
        user_id = next(row["id"] for row in users if row["email"] == user["email"])
        return user, "admin/accounts/" + user_id

    def test_lifecycle_and_ownership(self):
        user, route = self.make_user()
        admin_key = self.post("keys/api/issue").json()["key"]
        self.assertEqual(self.post(route, {"action": "approve"}).status_code, 200)
        self.assertEqual(self.login(user).status_code, 200)
        self.assertEqual(self.client.get("/portal/data/admin/accounts").status_code, 403)
        key = {"X-API-Key": self.post("keys/api/issue").json()["key"]}
        paths = self.client.get("/openapi.json").json()["paths"]
        cases = [
            (endpoint, kind, example["value"])
            for endpoint in ("/v1/recommendations", "/v1/budget")
            for kind, example in paths[endpoint]["post"]["requestBody"]["content"]["application/json"]["examples"].items()
        ]
        self.assertEqual({kind for _, kind, _ in cases}, {"hotels", "attractions", "budget"})
        for endpoint, kind, example in cases:
            result = self.client.post(endpoint, json=example, headers=key)
            self.assertEqual(result.status_code, 202)
            url = result.headers["Location"]
            task = self.client.get(url, headers=key).json()
            self.assertEqual(task["status"], "completed")
            if kind == "budget":
                self.assertEqual(task["result"]["status"], "succeeded")
            else:
                self.assertEqual(set(task["result"]["results"]), {kind})
                items = task["result"]["results"][kind]["items"]
                self.assertTrue(items)
                self.assertTrue(all("tariff" not in item for item in items))
            self.assertEqual(self.client.post(endpoint, json=example, headers=key).status_code, 202)
            self.assertEqual(self.client.get(url, headers=key).json(), task)
            self.assertEqual(self.client.get(url, headers={"X-API-Key": admin_key}).status_code, 404)
            different = dict(example, trip=dict(example["trip"], travelers=3))
            self.assertEqual(self.client.post(endpoint, json=different, headers=key).status_code, 409)
        self.assertEqual(self.client.get("/portal/data/activity").json()["summary"], {"total": 3, "pending": 0})
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.post("keys/api/revoke").status_code, 200)
        self.assertEqual(self.client.get(url, headers=key).status_code, 401)

    def test_builder_uses_the_signed_in_accounts_api_tasks(self):
        builder = "/portal/data/builder"
        body = dict(recommendation_examples["hotels"]["value"], taskId=uuid4().hex)
        self.assertEqual(self.client.get(builder + "/destinations").status_code, 401)
        self.assertEqual(self.client.post(builder + "/recommendations", json=body).status_code, 401)
        user, route = self.make_user()
        self.assertEqual(self.post(route, {"action": "approve"}).status_code, 200)
        self.assertEqual(self.login(user).status_code, 200)
        self.assertTrue(any(d["id"] == "ru-moscow" for d in self.client.get(builder + "/destinations").json()))
        missing_header = self.client.post(builder + "/recommendations", json=body, headers={"X-Portal-Request": ""})
        self.assertEqual(missing_header.status_code, 403)
        created = self.client.post(builder + "/recommendations", json=body)
        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.headers["Location"], builder + "/tasks/" + body["taskId"])
        task = self.client.get(created.headers["Location"]).json()
        self.assertEqual(task["status"], "completed")
        self.assertIn("hotels", task["result"]["results"])

        budget = dict(budget_examples["budget"]["value"], taskId=uuid4().hex)
        estimate = self.client.post(builder + "/budget", json=budget)
        self.assertEqual(estimate.status_code, 202)
        self.assertEqual(self.client.get(estimate.headers["Location"]).json()["result"]["status"], "succeeded")
        self.assertEqual(self.client.get("/portal/data/activity").json()["summary"]["total"], 2)

        path = "/v1/tasks/" + body["taskId"]
        self.assertEqual(self.client.get(path).status_code, 401)
        key = self.post("keys/api/issue").json()["key"]
        self.assertEqual(self.client.get(path, headers={"X-API-Key": key}).json(), task)
        self.login(self.admin)
        self.assertEqual(self.client.get(created.headers["Location"]).status_code, 404)
        usage = self.client.get("/portal/data/" + route + "/activity").json()["usage"]
        self.assertEqual((usage["submissions"], usage["polls"]), (2, 3))

    def test_single_target_and_nullable_refinement_fields(self):
        self.login(self.admin)
        key = {"X-API-Key": self.post("keys/api/issue").json()["key"]}
        endpoint = "/v1/recommendations"
        body = dict(recommendation_examples["hotels"]["value"], taskId=uuid4().hex,
                    refinement=None, excludedObjectIds=None, maxTotalRub=None)
        created = self.client.post(endpoint, json=body, headers=key)
        self.assertEqual(created.status_code, 202)
        retry = self.client.post(endpoint, json=dict(body, excludedObjectIds=[]), headers=key)
        self.assertEqual(retry.status_code, 202)

        for field in ("refinement", "excludedObjectIds"):
            incomplete = dict(body)
            del incomplete[field]
            response = self.client.post(endpoint, json=incomplete, headers=key)
            self.assertEqual(response.status_code, 422)
            self.assertIn(field, response.json()["error"]["fields"])
        for targets in ({"hotels": {"count": 2, "maxTotalRub": None}}, ["hotels", "attractions"]):
            self.assertEqual(self.client.post(endpoint, json=dict(body, targets=targets), headers=key).status_code, 422)

        filtered = dict(body, taskId=uuid4().hex, excludedObjectIds=["hotel-boulevard"])
        created = self.client.post(endpoint, json=filtered, headers=key)
        self.assertEqual(created.status_code, 202)
        items = self.client.get(created.headers["Location"], headers=key).json()["result"]["results"]["hotels"]["items"]
        self.assertEqual([item["objectId"] for item in items], ["hotel-metro", "hotel-garden"])

        budget = budget_examples["budget"]["value"]
        with_tariff = dict(budget, selectedHotel=dict(budget["selectedHotel"], tariff={"name": "Old"}))
        self.assertEqual(self.client.post("/v1/budget", json=with_tariff, headers=key).status_code, 422)

    def test_older_stored_tasks_still_available(self):
        admin_id = self.login(self.admin).json()["account"]["id"]
        key = {"X-API-Key": self.post("keys/api/issue").json()["key"]}
        store = app.state.tasks
        trip = budget_examples["budget"]["value"]["trip"]
        task_id = uuid4().hex
        old_body = {
            "taskId": task_id, "trip": trip,
            "targets": {
                "hotels": {"count": 2, "maxTotalRub": None, "excludedObjectIds": ["hotel-boulevard"]},
                "attractions": {"count": 1, "maxTotalRub": None},
            },
        }

        def persist(operation, body, result=None):
            store.connection.execute(
                "INSERT INTO tasks (client_id, task_id, operation, payload, result, created_at) VALUES (?, ?, ?, ?, ?, 0)",
                (admin_id, body["taskId"], operation, json.dumps(body), json.dumps(result) if result else None),
            )

        self.client.portal.call(persist, "recommendations", old_body)
        self.client.portal.call(store.run, admin_id, task_id)
        result = self.client.get("/v1/tasks/" + task_id, headers=key).json()["result"]
        self.assertEqual(set(result["results"]), {"hotels", "attractions"})
        self.assertEqual(result["results"]["hotels"]["items"][0]["objectId"], "hotel-metro")

        saved_id = uuid4().hex
        saved = dict(result, taskId=saved_id)
        saved["results"]["hotels"]["items"][0]["tariff"] = {"name": "Old"}
        self.client.portal.call(persist, "recommendations", dict(old_body, taskId=saved_id), saved)
        item = self.client.get("/v1/tasks/" + saved_id, headers=key).json()["result"]["results"]["hotels"]["items"][0]
        self.assertNotIn("tariff", item)

        budget_id = uuid4().hex
        budget = budget_examples["budget"]["value"]
        old_budget = dict(budget, taskId=budget_id, selectedHotel=dict(budget["selectedHotel"], tariff={"name": "Old"}))
        self.client.portal.call(persist, "budget", old_budget)
        self.client.portal.call(store.run, admin_id, budget_id)
        result = self.client.get("/v1/tasks/" + budget_id, headers=key).json()["result"]
        self.assertEqual(result["expenses"]["foodTotalRub"], 11200)

    def test_rejection_approval_and_disable(self):
        user, route = self.make_user()
        self.assertEqual(self.post(route, {"action": "reject"}).status_code, 200)
        self.assertEqual(self.login(user).status_code, 403)
        user, route = self.make_user()
        self.assertEqual(self.post(route, {"action": "approve"}).status_code, 200)
        self.assertEqual(self.login(user).status_code, 200)
        key = self.post("keys/api/issue").json()["key"]
        session = self.client.cookies.get("tripflow_portal")
        self.login(self.admin)
        self.assertEqual(self.post(route, {"action": "disable"}).status_code, 200)
        self.client.cookies.clear()
        self.client.cookies.set("tripflow_portal", session)
        self.assertIsNone(self.client.get("/portal/data/session").json()["account"])
        self.assertEqual(self.client.get("/v1/tasks/id", headers={"X-API-Key": key}).status_code, 401)

    def test_pending_and_restart(self):
        admin_id = self.login(self.admin).json()["account"]["id"]
        key = {"X-API-Key": self.post("keys/api/issue").json()["key"]}
        body = dict(budget_examples["budget"]["value"], taskId=uuid4().hex)
        store = app.state.tasks
        self.client.portal.call(store.accept, admin_id, "budget", BudgetRequest.model_validate(body))
        path = "/v1/tasks/" + body["taskId"]
        status = self.client.get(path, headers=key)
        self.assertEqual(status.json(), {"taskId": body["taskId"], "status": "pending", "result": None})
        self.assertEqual(status.headers["Retry-After"], "2")
        with TestClient(app) as restarted:
            result = restarted.get(path, headers=key).json()
            self.assertEqual(result["result"]["event"], "budget.finished")
            self.assertEqual(result["status"], "completed")

    def test_owner_roles_and_reapplication(self):
        moderator, moderator_route = self.make_user()
        developer, developer_route = self.make_user()
        self.assertEqual(self.post(moderator_route, {"action": "approve"}).status_code, 200)
        self.assertEqual(self.post(moderator_route, {"action": "promote"}).status_code, 200)
        owner_id = self.client.get("/portal/data/session").json()["account"]["id"]

        self.assertEqual(self.login(moderator).json()["account"]["role"], "admin")
        self.assertEqual(self.post(developer_route, {"action": "approve"}).status_code, 200)
        self.assertEqual(self.post(developer_route, {"action": "promote"}).status_code, 403)
        self.assertEqual(self.post(developer_route, {"action": "disable"}).status_code, 403)
        self.assertEqual(self.client.get(f"/portal/data/admin/accounts/{owner_id}/activity").status_code, 404)

        user_key = {"X-API-Key": self.post("keys/api/issue").json()["key"]}
        example = dict(budget_examples["budget"]["value"], taskId=uuid4().hex)
        location = self.client.post("/v1/budget", json=example, headers=user_key).headers["Location"]
        self.assertEqual(self.client.get(location, headers=user_key).status_code, 200)
        self.assertEqual(self.client.post("/v1/budget", content=b"{", headers=user_key).status_code, 422)
        self.assertEqual(self.client.get(location + "-unknown", headers=user_key).status_code, 404)

        self.login(self.admin)
        info = self.client.get("/portal/data/" + moderator_route + "/activity").json()
        self.assertEqual(info["summary"]["total"], 1)
        self.assertEqual(info["usage"]["last24h"], 4)
        self.assertEqual(info["usage"]["submissions"], 2)
        self.assertEqual(info["usage"]["polls"], 2)
        self.assertEqual(info["usage"]["errors"], 2)
        self.assertEqual(self.post(moderator_route, {"action": "disable"}).status_code, 200)
        self.assertEqual(self.client.get(location, headers=user_key).status_code, 401)
        with patch.dict(os.environ, {"TRIPFLOW_PORTAL_ADMIN_EMAIL": "", "TRIPFLOW_PORTAL_ADMIN_PASSWORD": ""}):
            with TestClient(app) as restarted:
                response = restarted.post("/portal/data/login", json=self.admin, headers={"X-Portal-Request": "1"})
                self.assertEqual(response.json()["account"]["role"], "owner")
                headers = {"X-Portal-Request": "1"}
                response = restarted.post("/portal/data/register", json=dict(moderator, password="wrong-password"), headers=headers)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(restarted.post("/portal/data/register", json=moderator, headers=headers).status_code, 200)
                accounts = restarted.get("/portal/data/admin/accounts").json()["accounts"]
                row = next(row for row in accounts if row["email"] == moderator["email"])
                self.assertEqual((row["role"], row["status"], row["ownerReview"]), ("developer", "pending", True))
                response = restarted.post("/portal/data/login", json=developer, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(restarted.get("/portal/data/admin/accounts").status_code, 403)
                restarted.post("/portal/data/login", json=self.admin, headers=headers)
                restarted.post("/portal/data/" + developer_route, json={"action": "promote"}, headers=headers)
                restarted.post("/portal/data/login", json=developer, headers=headers)
                response = restarted.post("/portal/data/" + moderator_route, json={"action": "approve"}, headers=headers)
                self.assertEqual(response.status_code, 403)
                restarted.post("/portal/data/login", json=self.admin, headers=headers)
                response = restarted.post("/portal/data/" + moderator_route, json={"action": "approve"}, headers=headers)
                self.assertEqual(response.status_code, 200)
                response = restarted.post("/portal/data/login", json=moderator, headers=headers)
                self.assertEqual(response.json()["account"]["role"], "developer")
                self.assertIsNone(response.json()["account"]["keys"]["api"]["hint"])

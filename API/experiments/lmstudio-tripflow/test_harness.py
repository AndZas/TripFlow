"""Test the HTTP exchange and guardrails without performing model inference."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from experiment import CASES, run_case
from harness import Harness, Trip


def call(name, args=None, call_id="c1"):
    return {
        "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(args if args is not None else {})},
    }


class LocalStub(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, payload))
        message = self.server.replies.pop(0)
        body = json.dumps({
            "model": "stub", "choices": [{"message": message, "finish_reason": "stop"}],
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class HarnessTests(unittest.TestCase):
    def run_stub(self, case_name, *messages):
        with HTTPServer(("127.0.0.1", 0), LocalStub) as server:
            server.requests = []
            server.replies = list(messages)
            worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            worker.start()
            try:
                result = run_case(case_name, CASES[case_name], server.server_port, "stub")
            finally:
                server.shutdown()
                worker.join()
        self.assertEqual(server.replies, [])
        self.assertTrue(all(path == "/v1/chat/completions" for path, _ in server.requests))
        return result, [request for _, request in server.requests]

    def test_tool_exchange_and_budget(self):
        for name, visits, expected_total in (("two-museums", 2, 3006), ("four-museums", 4, 6012)):
            with self.subTest(name=name):
                result, requests = self.run_stub(
                    name,
                    {"tool_calls": [call("search_hotels")]},
                    {"tool_calls": [call("search_attractions", {"categories": ["museums", "nature"]}, "c2")]},
                    {"tool_calls": [call("get_budget_rates", call_id="c3")]},
                    {"content": json.dumps({
                        "hotelIds": ["hotel-19", "hotel-18", "hotel-16"],
                        "attractionIds": ["museums-1", "museums-2", "nature-2"],
                        "paidMuseumVisitsPerPerson": visits,
                    })},
                )
                self.assertTrue(result["passed"], result["error"])
                self.assertEqual(result["result"]["museumEstimate"]["groupTotalRub"], expected_total)
                self.assertIsNone(result["result"]["attractions"][0]["price"])
                self.assertEqual(
                    [[tool["function"]["name"] for tool in request["tools"]] for request in requests[:3]],
                    [["search_hotels"], ["search_attractions"], ["get_budget_rates"]],
                )
                self.assertTrue(all(request["tool_choice"] == "required" for request in requests[:3]))
                self.assertNotIn("tools", requests[3])
                decision = requests[3]["response_format"]
                self.assertEqual(decision["type"], "json_schema")
                self.assertEqual(decision["json_schema"]["schema"]["properties"]["hotelIds"]["minItems"], 3)
                evidence = json.loads(requests[3]["messages"][-1]["content"])["evidence"]
                self.assertEqual(evidence["attractions"][0]["id"], "museums-1")
                self.assertEqual(evidence["hotels"][0]["id"], "hotel-19")

    def test_hotel_budget_and_exclusions_are_applied_before_model_ranking(self):
        result, requests = self.run_stub(
            "budget-hotel",
            {"tool_calls": [call("search_hotels")]},
            {"content": '{"hotelIds":["hotel-18"],"attractionIds":[],"paidMuseumVisitsPerPerson":null}'},
        )
        self.assertTrue(result["passed"], result["error"])
        self.assertEqual([tool["function"]["name"] for tool in requests[0]["tools"]], ["search_hotels"])
        hotels = result["toolResults"]["search_hotels"]
        self.assertEqual([row["id"] for row in hotels], ["hotel-18"])
        self.assertEqual(hotels[0]["referenceGroupTotalRub"], 50_850)

    def test_plain_text_tool_call_is_rejected(self):
        result, _ = self.run_stub("budget-hotel", {"content": '<tool_call>{"name":"search_hotels"}</tool_call>'})
        self.assertFalse(result["passed"])
        self.assertIn("structured tool_calls", result["error"])
        self.assertEqual(result["toolResults"], {})

    def test_forbidden_tool_is_not_executed(self):
        harness = Harness(Trip("", target="hotels", option_budget_rub=65_000))
        with self.assertRaisesRegex(ValueError, "Tool unavailable"):
            harness.dispatch(call("get_budget_rates"))
        self.assertEqual(harness.results, {})

    def test_invalid_tool_parameters_are_rejected(self):
        harness = Harness(Trip(""))
        for args in ({"categories": ["unknown"]}, {"categories": ["nature", "nature"]},
                     {"categories": ["museums"], "city": "Казань"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                harness.dispatch(call("search_attractions", args))
        self.assertEqual(harness.results, {})

    def test_repeated_tool_is_rejected(self):
        harness = Harness(Trip(""))
        harness.dispatch(call("get_budget_rates"))
        with self.assertRaisesRegex(ValueError, "already used"):
            harness.dispatch(call("get_budget_rates", call_id="c2"))

    def test_invalid_rankings_are_rejected(self):
        harness = Harness(Trip(""))
        harness.dispatch(call("search_attractions", {"categories": ["museums"]}))
        for ids in (["museums-1", "fake"], ["museums-1", "museums-1"], ["museums-1"]):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, "permutation"):
                harness.validate_decision(json.dumps({
                    "hotelIds": [], "attractionIds": ids, "paidMuseumVisitsPerPerson": None,
                }))

    def test_invalid_budget_is_rejected(self):
        harness = Harness(Trip(""))
        harness.dispatch(call("get_budget_rates"))
        for visits in (-1, 13, True, "2"):
            with self.subTest(visits=visits), self.assertRaisesRegex(ValueError, "Invalid visit count"):
                harness.validate_decision(json.dumps({
                    "hotelIds": [], "attractionIds": [], "paidMuseumVisitsPerPerson": visits,
                }))

    def test_valid_json_can_still_fail_semantic_check(self):
        result, _ = self.run_stub(
            "parks-refinement",
            {"tool_calls": [call("search_attractions", {"categories": ["museums"]})]},
            {"content": '{"hotelIds":[],"attractionIds":["museums-1","museums-2"],"paidMuseumVisitsPerPerson":null}'},
        )
        self.assertIsNone(result["error"])
        self.assertFalse(result["checks"]["expectedSearchCategories"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()

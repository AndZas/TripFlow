"""Offline checks. Fixtures below are SYNTHETIC and are never survey evidence."""
import argparse
from datetime import date
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from src.survey import (Client, NoRedirect, Survey, coverage, normalize_osm,
                        normalize_geoapify, normalize_otm, public_url, safe_sample, scrub, stay_dates)


class SurveyTests(unittest.TestCase):
    def test_stay_crosses_year_and_leap_day(self):
        self.assertEqual(stay_dates(date(2026, 12, 15))["check_in"], "2027-01-14")
        self.assertEqual(stay_dates(date(2028, 1, 30))["check_out"], "2028-03-02")

    def test_entrance_flag_is_not_ticket_price_or_hotel_availability(self):
        row = normalize_osm({"id": 1, "type": "way", "center": {"lat": 48.8, "lon": 2.3},
                             "tags": {"name": "Fixture", "fee": "yes", "charge": "20 EUR"}}, "museums", "test")
        self.assertIsNone(row["price_amount"])
        self.assertIsNone(row["price_currency"])
        self.assertIsNone(row["availability"])
        self.assertEqual(row["entrance_fee"], "yes")
        self.assertEqual(row["latitude"], 48.8)

    def test_zero_and_false_are_present_values(self):
        stats = coverage([{"price_amount": 0, "availability": False}, {}])
        self.assertEqual(stats["price_amount"], {"filled": 1, "total": 2})
        self.assertEqual(stats["availability"]["filled"], 1)

    def test_recursive_redaction(self):
        value = {"apiKey": "abc123", "data": [{"url": "https://example.test/?key=abc123&x=1", "echo": "abc123"}]}
        result = json.dumps(scrub(value, ["abc123"]))
        self.assertNotIn("abc123", result)
        self.assertIn("REDACTED", result)

    def test_geoapify_details_preserve_documented_content(self):
        item = {"properties": {"place_id": "fixture", "description": "Fixture", "opening_hours": "24/7",
                               "timezone": {"name": "Europe/Paris"}, "wiki_and_media": {"image": "https://example.test/image.jpg"},
                               "contact": {"email": "private@example.test"}}}
        row = normalize_geoapify(item, "details", "test")
        self.assertEqual(row["description"], "Fixture")
        self.assertEqual(row["timezone"], "Europe/Paris")
        self.assertEqual(row["image_url"], "https://example.test/image.jpg")
        self.assertNotIn("private@example.test", json.dumps(safe_sample(item, "geoapify")))

    def test_opentripmap_significance_does_not_become_review_rating(self):
        row = normalize_otm({"xid": "fixture", "rate": "3h", "point": {"lat": 48.8, "lon": 2.3}}, "historic", "test")
        self.assertIsNone(row["rating"])
        self.assertIsNone(row["price_amount"])

    def test_optional_nested_nulls_are_missing_data_not_schema_failure(self):
        geo = {"properties": {"datasource": None, "timezone": None, "contact": None, "wiki_and_media": None}}
        self.assertIsNone(normalize_geoapify(geo, "details", "test")["image_url"])
        self.assertIsNone(normalize_otm({"preview": None, "wikipedia_extracts": None}, "details", "test")["description"])
        safe_sample(geo, "geoapify")

    def test_free_plan_gates_with_existing_keys(self):
        survey = self.make_survey()
        survey.args.no_keys = False
        survey.args.providers = ["geoapify", "opentripmap"]
        with patch.dict("os.environ", {"GEOAPIFY_API_KEY": "fixture-secret", "OPENTRIPMAP_API_KEY": "fixture-secret",
                                        "GEOAPIFY_FREE_PLAN": "0", "OPENTRIPMAP_FREE_PLAN": "0"}), \
                patch.object(survey.client, "get") as get, patch.object(survey, "save"), patch("builtins.print"):
            survey.run()
        get.assert_not_called()
        self.assertTrue(any("Free plan" in r.get("reason", "") or "Free" in r.get("reason", "") for r in survey.results))

    def test_public_urls_drop_credentials_and_tracking(self):
        self.assertIsNone(public_url("https://user:secret@example.test/"))
        self.assertIsNone(public_url("javascript:alert(1)"))
        self.assertEqual(public_url("https://example.test/a?token=secret#fragment"), "https://example.test/a")

    def test_osm_sample_excludes_contacts_and_user_metadata(self):
        item = {"id": 1, "user": "private", "tags": {"name": "Fixture", "contact:email": "private@example.test", "phone": "private"}}
        self.assertNotIn("private", json.dumps(safe_sample(item, "osm")))

    def test_redirects_never_forward_keys(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test/"))

    def client_with_response(self, body):
        client = Client(delay=1)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status, response.headers = 200, {"Content-Type": "application/json"}
        response.read.return_value = body
        client.opener = Mock()
        client.opener.open.return_value = response
        return client

    def test_http_errors_are_recorded_without_response_body(self):
        for status in (401, 403, 404, 429, 500, 503):
            with self.subTest(status=status), patch("src.survey.time.sleep"):
                client = Client()
                client.opener = Mock()
                client.opener.open.side_effect = HTTPError("https://api.frankfurter.dev/?key=secret", status, "error", {}, io.BytesIO(b"secret"))
                meta, data = client.get("test", "https://api.frankfurter.dev/v2/rates", {})
                self.assertEqual(meta["http_status"], status)
                self.assertEqual(meta["status"], "http_error")
                self.assertIsNone(data)
                self.assertNotIn("secret", json.dumps(meta))
                self.assertIsNotNone(meta["duration_ms"])
                if status in (401, 403, 429):
                    client.get("test", "https://api.frankfurter.dev/v2/rates", {})
                    self.assertEqual(client.opener.open.call_count, 1)

    def test_timeout_does_not_abort(self):
        with patch("src.survey.time.sleep"):
            client = Client()
            client.opener = Mock()
            client.opener.open.side_effect = URLError(TimeoutError("secret"))
            meta, data = client.get("test", "https://api.frankfurter.dev/v2/rates", {})
            self.assertEqual(meta["status"], "network_error")
            self.assertNotIn("secret", json.dumps(meta))

    def test_empty_malformed_and_oversized_responses(self):
        for body, expected in ((b"", "empty"), (b"<html>blocked</html>", "invalid_response"), (b"x" * 2_000_001, "response_too_large")):
            with self.subTest(expected=expected), patch("src.survey.time.sleep"):
                meta, data = self.client_with_response(body).get("test", "https://api.frankfurter.dev/v2/rates", {})
                self.assertEqual(meta["status"], expected)
                self.assertIsNone(data)

    def test_http_host_allowlist(self):
        with self.assertRaises(ValueError):
            Client().get("test", "https://other.test/", {})

    def make_survey(self, offline=False):
        return Survey(argparse.Namespace(timeout=1, delay=1, limit=10, providers=None,
                                         no_keys=True, offline=offline, show_samples=False))

    def test_offline_never_opens_network_and_missing_city_skips_poi(self):
        survey = self.make_survey(offline=True)
        with patch.object(survey.client, "get") as get, patch.object(survey, "save"), patch("builtins.print"):
            survey.run()
        get.assert_not_called()
        self.assertTrue(all(r["status"] == "skipped" for r in survey.results))

    def test_provider_error_and_partial_overpass_not_success(self):
        survey = self.make_survey()
        survey.client.get = Mock(return_value=({"status": "ok", "http_status": 200, "duration_ms": 1},
                                              {"elements": [{"id": 1}], "remark": "runtime error"}))
        with patch("builtins.print"):
            rows = survey.call("overpass", "test", "https://overpass-api.de/api/interpreter", {}, lambda d: d["elements"])
        self.assertEqual(rows, [])
        self.assertEqual(survey.results[0]["status"], "provider_error")
        self.assertNotIn("sample", survey.results[0])


if __name__ == "__main__":
    unittest.main()

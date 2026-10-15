"""Synthetic fixtures, offline only. No supplier observations or market hotel rates."""
import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.extended import (CITIES, ExtendedSurvey, canonical, candidate_key, category_matches, compare_place_identity,
                          filter_candidates, request_plan, select_city, valid_coordinates)
from src.hotel_estimate import estimate, main as estimate_main
from src.survey import ROOT, normalize_geonames, safe_sample


def candidate(identifier="a", provider="geoapify", **extra):
    return {"provider": provider, "external_id": identifier, "latitude": 48.8, "longitude": 2.3, **extra}


class ExtendedTests(unittest.TestCase):
    def test_default_plan_has_hard_bound(self):
        self.assertEqual(request_plan(list(CITIES)), 40)
        self.assertEqual(request_plan(["paris"], True), 8)
        self.assertEqual(request_plan(["moscow", "suzdal"], True), 15)

    def test_select_city_never_picks_first_ambiguous_candidate(self):
        rows = [{"id": 1, "country_code": "FR", "feature_code": "PPLC", "name": "Paris"},
                {"id": 2, "country_code": "FR", "feature_code": "PPLC", "name": "Paris"}]
        self.assertIsNone(select_city(rows, CITIES["paris"], "open_meteo"))
        self.assertIsNone(select_city([{**rows[0], "country_code": "US"}], CITIES["paris"], "open_meteo"))

    def test_city_aliases_handle_cyrillic_apostrophes_and_diacritics(self):
        row = {"id": 1, "country_code": "TR", "feature_code": "PPLA", "name": "İstanbul"}
        self.assertEqual(select_city([row], CITIES["istanbul"], "open_meteo"), row)
        self.assertEqual(canonical("Suzdal’"), canonical("Suzdal"))
        row = {"geonameId": 2, "countryCode": "RU", "fcode": "PPLC", "name": "Москва"}
        self.assertEqual(select_city([row], CITIES["moscow"], "geonames"), row)

    def test_rejections_are_provider_scoped_not_name_scoped(self):
        rows = [candidate("a", name="Same"), candidate("b", name="Same"), candidate("a", provider="other")]
        result = filter_candidates(rows, {("geoapify", "a")})
        self.assertEqual([(r["provider"], r["external_id"]) for r in result], [("geoapify", "b"), ("other", "a")])

    def test_rejections_do_not_change_other_card_or_input(self):
        rows = [candidate("a"), candidate("b")]
        before = json.dumps(rows)
        self.assertEqual(len(filter_candidates(rows, {("geoapify", "a")})), 1)
        self.assertEqual(len(filter_candidates(rows, set())), 2)
        self.assertEqual(before, json.dumps(rows))

    def test_changed_lookup_id_keeps_rejection_by_source_identity(self):
        first = candidate("old", source_provider="openstreetmap", source_external_id="node/123")
        updated = candidate("new", source_provider="openstreetmap", source_external_id="node/123")
        self.assertEqual(filter_candidates([updated], {candidate_key(first)}), [])
        way = candidate("new", source_provider="openstreetmap", source_external_id="way/123")
        self.assertEqual(filter_candidates([way], {candidate_key(first)}), [way])

    def test_detail_identity_uses_osm_not_opaque_lookup_id(self):
        def feature(identifier, osm_id):
            return {"properties": {"place_id": identifier, "datasource": {"raw": {"osm_type": "n", "osm_id": osm_id}}}}
        self.assertEqual(compare_place_identity(feature("old", 123), feature("new", 123))[0], "pass")
        self.assertEqual(compare_place_identity(feature("same", 123), feature("same", 456))[0], "fail")
        self.assertEqual(compare_place_identity({"properties": {"place_id": "a"}}, {"properties": {"place_id": "b"}})[0], "warn")

    def test_all_rejected_and_empty_inputs_return_empty(self):
        self.assertEqual(filter_candidates([], set()), [])
        self.assertEqual(filter_candidates([candidate()], {("geoapify", "a")}), [])

    def test_duplicate_and_invalid_candidates_removed(self):
        rows = [candidate(), candidate(), candidate(None), candidate("bad", latitude=float("nan")), candidate("wrong", longitude=200)]
        self.assertEqual(filter_candidates(rows, set()), [rows[0]])
        self.assertFalse(valid_coordinates(True, 2))

    def test_hierarchical_categories_use_prefix_boundaries(self):
        self.assertTrue(category_matches({"properties": {"categories": ["catering.restaurant.french"]}}, "catering.restaurant"))
        self.assertFalse(category_matches({"properties": {"categories": ["catering.restaurant_fake"]}}, "catering.restaurant"))

    def test_geonames_normalized_without_fake_hotel_currency(self):
        row = normalize_geonames({"name": "Fixture", "lat": "48.8", "lng": "2.3", "countryCode": "FR",
                                  "currencyCode": "EUR", "timezone": {"timeZoneId": "Europe/Paris"}}, "city", "test")
        self.assertEqual(row["latitude"], 48.8)
        self.assertEqual(row["currency_code"], "EUR")
        self.assertIsNone(row["price_currency"])
        self.assertEqual(row["timezone"], "Europe/Paris")

    def test_geonames_sample_excludes_account_fields_and_long_aliases(self):
        sample = safe_sample({"name": "Fixture", "username": "private", "alternateNames": ["long"] * 100}, "geonames")
        self.assertEqual(sample, {"name": "Fixture"})

    def make_survey(self, offline=False, cap=40):
        args = argparse.Namespace(timeout=1, delay=1, limit=5, providers=None, no_keys=True, offline=offline,
                                  show_samples=False, cities=["paris"], radius=3000, core_only=False, max_requests=cap)
        return ExtendedSurvey(args)

    def test_extended_offline_has_no_network_and_no_fake_passes(self):
        survey = self.make_survey(offline=True)
        with patch.object(survey.client, "get") as get, patch.object(survey, "save"), patch.object(survey, "save_assessment"), patch("builtins.print"):
            survey.run()
        get.assert_not_called()
        self.assertEqual(survey.network_attempts, 0)
        self.assertTrue(all(c["status"] == "skipped" for c in survey.checks))

    def test_request_cap_stops_actual_calls(self):
        survey = self.make_survey(cap=1)
        survey.client.get = Mock(return_value=({"status": "ok", "http_status": 200, "duration_ms": 1}, {"results": []}))
        with patch("builtins.print"):
            survey.city_search("one", "Fixture")
            survey.city_search("two", "Fixture")
        self.assertEqual(survey.client.get.call_count, 1)
        self.assertEqual(survey.results[-1]["reason"], "Request cap reached")

    def test_failed_http_is_not_a_pass_even_if_count_missing(self):
        survey = self.make_survey()
        survey.client.get = Mock(return_value=({"status": "http_error", "http_status": 429, "duration_ms": 1}, None))
        with patch("builtins.print"):
            survey.city_search("test", "Fixture")
        self.assertEqual(survey.checks[-1]["status"], "fail")


class HotelEstimateTests(unittest.TestCase):
    def fixture(self, **changes):
        return {"guests": 5, "guests_per_room": 2, "nights": 3, "price_per_room_night": "100.00",
                "price_basis": "room_per_night", "currency": "EUR", "source_type": "manual_estimate",
                "source_url": None, "observed_on": "2026-01-01", "basis": "SYNTHETIC test fixture, not a market rate",
                "taxes_included": None, **changes}

    def test_room_count_rounds_up_and_total_is_estimate(self):
        result = estimate(self.fixture())
        self.assertEqual(result["rooms"], 3)
        self.assertEqual(result["estimated_total"], "900.00")
        self.assertFalse(result["is_live_offer"])
        self.assertIsNone(result["availability"])
        self.assertIsNone(result["taxes_included"])

    def test_exact_capacity_and_decimal_rounding(self):
        result = estimate(self.fixture(guests=4, nights=1, price_per_room_night=Decimal("125.555")))
        self.assertEqual(result["rooms"], 2)
        self.assertEqual(result["estimated_total"], "251.11")

    def test_missing_price_never_defaults_to_zero_or_average(self):
        with self.assertRaises(ValueError):
            estimate(self.fixture(price_per_room_night=None))

    def test_invalid_guests_capacity_nights_and_price_rejected(self):
        for change in ({"guests": 0}, {"guests": True}, {"guests_per_room": 0}, {"guests_per_room": 2.5},
                       {"nights": -1}, {"price_per_room_night": "NaN"}, {"price_per_room_night": "Infinity"},
                       {"price_per_room_night": "-1"}, {"price_per_room_night": "0"}, {"price_per_room_night": 125.5}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                estimate(self.fixture(**change))

    def test_wrong_price_units_or_unknown_currency_rejected(self):
        with self.assertRaises(ValueError):
            estimate(self.fixture(price_basis="person_per_night"))
        with self.assertRaises(ValueError):
            estimate(self.fixture(currency="JPY"))

    def test_source_and_observation_date_required(self):
        for change in ({"source_type": "official_published_rate", "source_url": None}, {"basis": None},
                       {"observed_on": None}, {"observed_on": "2099-01-01"}, {"source_url": "https://user:secret@example.test/"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                estimate(self.fixture(**change))

    def test_published_rate_source_query_cleaned(self):
        result = estimate(self.fixture(source_type="official_published_rate", source_url="https://example.test/rate?token=secret"))
        self.assertEqual(result["source_url"], "https://example.test/rate")

    def test_calculator_cli_writes_only_explicit_estimate_artifacts(self):
        # Synthetic input/output live only under this experiment, then stdlib cleans them up.
        with tempfile.TemporaryDirectory(prefix="estimate-test-", dir=ROOT / "tests") as directory:
            temporary_root = Path(directory).resolve()
            self.assertTrue(temporary_root.is_relative_to(ROOT))
            (temporary_root / "input.json").write_text(json.dumps(self.fixture()), encoding="utf-8")
            with patch("src.hotel_estimate.ROOT", temporary_root), patch("builtins.print"):
                self.assertEqual(estimate_main(["--input", "input.json"]), 0)
            outputs = list((temporary_root / "reports" / "estimates").glob("*/estimate.json"))
            self.assertEqual(len(outputs), 1)
            result = json.loads(outputs[0].read_text(encoding="utf-8"))
            self.assertEqual(result["estimated_total"], "900.00")
            self.assertFalse(result["is_live_offer"])
            self.assertIn("SYNTHETIC", result["basis"])
            self.assertTrue(outputs[0].with_suffix(".md").is_file())


if __name__ == "__main__":
    unittest.main()

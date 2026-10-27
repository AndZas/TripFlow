import unittest
from unittest.mock import patch

import enrichment_test as e


class MappingTests(unittest.TestCase):
    def test_match_requires_name_and_location_even_with_qid(self):
        refs = [{"name": "Musée Curie", "coordinates": [48.8442, 2.3448], "wikidata": "Q1"}]
        self.assertEqual(e.match({"name": "Musée Curie", "coordinates": [48.8442, 2.3448], "wikidata": "Q1"}, refs)["confidence"], "confident")
        self.assertEqual(e.match({"name": "Unrelated street", "coordinates": [48.8442, 2.3448], "wikidata": "Q1"}, refs)["confidence"], "possible")

    def test_duplicate_candidates_are_ambiguous(self):
        refs = [{"name": "Musée Curie", "coordinates": [48.8442, 2.3448], "wikidata": None}]
        items = [{"source_id": "a", "name": "Musée Curie", "coordinates": [48.8442, 2.3448]},
                 {"source_id": "b", "name": "Musée Curie", "coordinates": [48.8443, 2.3448]}]
        e.match_items(items, refs)
        self.assertEqual([x["match"]["confidence"] for x in items], ["ambiguous", "ambiguous"])

    def test_empty_and_false_coverage(self):
        m = e.metrics([{"image_usable": False, "is_free": False}, {"image_usable": True, "is_free": None}])
        self.assertEqual(m["image_usable"], {"filled": 1, "denominator": 2})
        self.assertEqual(m["is_free"], {"filled": 1, "denominator": 2})

    def test_datatourisme_nested_lists_and_expired_minimum(self):
        item = e.datatourisme_item({"label": {"@fr": "Musée"}, "type": ["Museum", "PlaceOfInterest"],
            "hasBeenCreatedBy": {"legalName": "Regional Tourism Board"}, "lastUpdate": "2026-10-01",
            "isLocatedAt": [{"geo": {"latitude": 48.8, "longitude": 2.3},
                             "address": [{"streetAddress": ["Rue Exemple"]}]}],
            "offers": [{"priceSpecification": [{"priceCurrency": "EUR", "minPrice": [18.8],
                "appliesOnPeriod": [{"startDate": "2023-01-01", "endDate": "2024-12-31"}]}]}]})
        self.assertEqual(item["coordinates"], [48.8, 2.3])
        self.assertEqual(item["address"], "Rue Exemple")
        self.assertEqual(item["unclassified_price_amount"], "18.8")
        self.assertEqual(item["price_kind"], "expired_catalog_tariff")
        self.assertIsNone(item["admission_price_amount"])
        self.assertIsNone(item["price_updated_at"])
        self.assertEqual(item["attribution"], "Regional Tourism Board")

    def test_client_rejects_production_and_booking_before_network(self):
        args = type("Args", (), {"max_requests": 2, "delay_seconds": 1, "timeout_seconds": 2})()
        client = e.Client(args)
        with patch("urllib.request.build_opener") as opener:
            with self.assertRaises(ValueError):
                client.call("amadeus", "https://api.amadeus.com", "/v3/shopping/hotel-offers")
            with self.assertRaises(ValueError):
                client.call("amadeus", "https://test.api.amadeus.com", "/v1/booking/hotel-bookings")
            opener.assert_not_called()
        self.assertEqual(client.used, 0)

    def test_amadeus_closed_without_network(self):
        args = type("Args", (), {"max_requests": 2, "delay_seconds": 1, "timeout_seconds": 2})()
        client = e.Client(args)
        records = []
        with patch("urllib.request.build_opener") as opener:
            e.run_amadeus(client, args, records, [])
            self.assertEqual(records[0]["status"], "skipped_provider_unavailable")
            with self.assertRaises(ValueError):
                client.call("amadeus", "https://test.api.amadeus.com", "/v1/shopping/activities")
            opener.assert_not_called()
        self.assertEqual(client.used, 0)


if __name__ == "__main__":
    unittest.main()

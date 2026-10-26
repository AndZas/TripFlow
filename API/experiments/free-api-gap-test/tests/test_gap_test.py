import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("gap_test", Path(__file__).resolve().parents[1] / "gap_test.py")
gap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gap)


class NormalizationTests(unittest.TestCase):
    def test_missing_fields_are_not_zero_or_present(self):
        row = gap.normalize_otm({"xid": "Q1", "name": "Museum", "rate": "3h", "point": {"lat": 48, "lon": 2}})
        self.assertIsNone(row["price_amount"])
        self.assertIsNone(row["availability"])
        self.assertEqual(row["rate"], "3h")
        self.assertEqual(gap.coverage([row], gap.FIELDS_POI)["price_amount"]["n_present"], 0)

    def test_geo_timezone_and_no_assumed_currency(self):
        row = gap.normalize_geo({"name": "Paris", "lat": 48.85, "lon": 2.35, "timezone": {"name": "Europe/Paris"}})
        self.assertEqual(row["timezone"], "Europe/Paris")
        self.assertIsNone(row["currency"])

    def test_exact_and_probable_matching(self):
        sample = {"name": "Musée Curie", "latitude": 48.84, "longitude": 2.34, "osm": "node/123", "wikidata": "Q4"}
        exact = gap.match_poi({"name": "Other", "wikidata": "Q4"}, [sample])
        self.assertEqual(exact["kind"], "exact_id")
        probable = gap.match_poi({"name": "Musee Curie", "latitude": 48.8401, "longitude": 2.3401}, [sample])
        self.assertEqual(probable["kind"], "probable_name_distance")
        uncertain = gap.match_poi({"name": "Different", "latitude": 48.8401, "longitude": 2.3401}, [sample])
        self.assertEqual(uncertain["kind"], "uncertain")

    def test_catalog_validation(self):
        self.assertEqual(gap.catalog_kinds({"children": [{"name": "museums"}, {"name": "historic"}]}), {"museums", "historic"})

    def test_no_query_strings_in_samples(self):
        self.assertEqual(gap.safe_url("https://example.org/photo?token=secret"), "https://example.org/photo")


if __name__ == "__main__":
    unittest.main()

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import unittest
from unittest.mock import patch

from deepseek import DeepSeekError, Usage
from lodging import estimate_hotels
from selection import pages_for
from trip import calculate, cards, checked_price


class ExperimentTest(unittest.TestCase):
    def test_search_attempts_cannot_cross_limit_concurrently(self):
        usage = Usage()

        def reserve(_):
            try:
                usage.reserve("search", b"{}")
                return True
            except DeepSeekError:
                return False

        with ThreadPoolExecutor(max_workers=12) as pool:
            self.assertEqual(sum(pool.map(reserve, range(16))), 7)
        self.assertEqual(usage.snapshot()["billed"]["search"], 0)

    def test_usage_counts_cached_tokens_and_successful_web_requests(self):
        usage = Usage()
        usage.record("model", {"usage": {"prompt_cache_hit_tokens": 1000, "prompt_cache_miss_tokens": 300,
                                         "completion_tokens": 100}})
        usage.record("search", {"results": [{}]})
        usage.record("fetch", {"content": ""})
        self.assertAlmostEqual(usage.snapshot()["peakCny"], 0.00644)

    def test_canonical_url_retains_tariff_parameters(self):
        rows = [{"url": f"https://example.com/hotel?{query}", "title": "Отель", "text": "Проверка"}
                for query in ("guests=1&utm_source=one", "utm_source=two&guests=1", "guests=2")]
        self.assertEqual(len(pages_for(rows)), 2)

    def test_additional_fact_requires_an_existing_quote(self):
        data = [{"id": 1, "url": "https://example.com/hotel", "title": "Отель", "images": [],
                 "text": "Красный отель. Стойка работает круглосуточно."}]
        raw = {"name": "Красный отель", "identity": {"source": 1, "quote": "Красный отель"}, "facts": [
            {"label": "Стойка", "value": "24 часа", "source": 1, "quote": "Стойка работает круглосуточно"},
            {"label": "Бассейн", "value": "есть", "source": 1, "quote": "Бесплатный бассейн"},
        ]}
        hotel, = cards([raw], data, "hotels", {"destination": "Киото"})
        self.assertEqual([fact["label"] for fact in hotel["facts"]], ["Стойка"])

    def test_rate_for_two_guests_is_a_per_room_proxy(self):
        source = {1: {"url": "https://example.com/rooms?adults=2", "title": "Отель", "text": "от ¥20,000 за ночь"}}
        rate = checked_price({"source": 1, "quote": "от ¥20,000 за ночь", "amount": 20_000,
                              "currency": "JPY", "basis": "room_night", "from": True}, source, "hotels")
        self.assertEqual(rate["occupancy"], 2)
        hotels = [{"name": "Отель", "id": "hotels-1", "description": "", "facts": [], "price": rate}]
        with patch("lodging.exchange_rates", return_value=({"JPY": Decimal("0.5")}, None)), \
             patch("lodging.complete", return_value={"estimates": [{"id": "hotels-1", "nightlyRub": 9_000}]}):
            estimate_hotels({"travelers": 4, "nights": 7, "budgetRub": 500_000}, hotels, [], Usage())
        estimate = hotels[0]["estimate"]
        self.assertEqual(estimate["basis"], "hotel_proxy")
        self.assertEqual(estimate["totalRub"], 252_000)

    def test_tariffs_comparables_and_model_only_all_use_single_rooms(self):
        trip = {"travelers": 4, "nights": 7, "budgetRub": 500_000}
        price = {"amount": 20_000, "currency": "JPY", "basis": "room_night", "from": True,
                 "url": "https://example.com/nearby", "title": "Тариф", "quote": "от ¥20,000 за ночь"}
        hotels = [{"id": f"hotels-{i}", "name": name, "description": "", "note": "", "facts": [],
                   "price": price if i == 1 else None} for i, name in enumerate(("Первый", "Второй", "Третий"), 1)]
        reply = {"estimates": [{"id": "hotels-1", "nightlyRub": 8_000},
                               {"id": "hotels-2", "nightlyRub": 11_000, "comparables": [1, 999]},
                               {"id": "hotels-3", "nightlyRub": 12_000, "comparables": [999]}]}
        with patch("lodging.exchange_rates", return_value=({"JPY": Decimal("0.5")}, None)), \
             patch("lodging.complete", return_value=reply):
            estimate_hotels(trip, hotels, [], Usage())
        self.assertEqual([c["estimate"]["basis"] for c in hotels], ["hotel_rate", "comparable_rates", "model_only"])
        self.assertEqual([c["estimate"]["totalRub"] for c in hotels], [280_000, 308_000, 336_000])
        self.assertEqual(len(hotels[1]["estimate"]["sources"]), 1)
        with patch("trip.complete", return_value=dict(foodRub=4_000, transportRub=2000, otherRub=0, reserveRub=0)):
            result = calculate(trip, hotels[1], [])
        self.assertEqual(result["totalRub"], 314_000)


if __name__ == "__main__":
    unittest.main()

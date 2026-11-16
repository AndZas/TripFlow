import unittest
from unittest.mock import patch

from stand import budget_input, calculate, card_input


class StandTests(unittest.TestCase):
    def setUp(self):
        self.card = {"destination": "ru-moscow", "startDate": "2027-05-19", "endDate": "2027-05-21",
                     "travelers": 3, "budgetRub": 50000, "hotelBudgetRub": None, "preferences": "Музеи"}
        self.recommendations = {"card": self.card, "parsed": {"expenses": {"food": None, "other": None}},
                                "hotels": [{"id": "one", "indicativeGroupRub": 20000,
                                            "source": "Russhotels", "breakfastStatus": "confirmed"}],
                                "attractions": [{"id": "museum", "name": "Музей", "price": None}]}

    def test_card_limit_is_calculated_from_budget_and_preferences(self):
        destinations = [{"id": "ru-moscow"}]
        self.assertEqual(card_input(self.card, destinations)["hotelBudgetRub"], 25000)
        custom = {**self.card, "preferences": "На отель до 35 тыс. руб."}
        self.assertEqual(card_input(custom, destinations)["hotelBudgetRub"], 35000)

    def test_selection_only_uses_provider_values_from_current_recommendations(self):
        pick = {"hotelId": "one", "placeIds": ["museum"], "indicativeGroupRub": 1, "travelers": 1}
        result = budget_input(pick, self.recommendations)
        self.assertEqual((result["hotel"]["indicativeGroupRub"], result["travelers"]), (20000, 3))
        self.assertEqual(result["benefits"][0]["dayIndices"], [2, 3])
        with self.assertRaises(ValueError):
            budget_input({**pick, "placeIds": ["stale"]}, self.recommendations)

    def test_total_exposes_unknown_prices(self):
        card = budget_input({"hotelId": "one", "placeIds": ["museum"]}, self.recommendations)
        with patch("stand.estimate", return_value={"extraTotalRub": 6000, "expenses": {}}):
            result = calculate(card, None, None)
        self.assertEqual((result["knownTotalRub"], result["remainingRub"]), (26000, 24000))
        self.assertEqual(result["unpricedPlaces"], ["Музей"])

    def test_discretionary_spending_can_drop_to_zero_without_cutting_food(self):
        card = budget_input({"hotelId": "one"}, self.recommendations)
        base = {"extraTotalRub": 36300, "expenses": {"food": {"groupRub": 35100}, "other": {"groupRub": 1200}}}
        with patch("stand.estimate", return_value=base):
            result = calculate(card, None, None)
        self.assertEqual(result["knownTotalRub"], 55100)
        self.assertEqual(result["expenses"]["other"]["groupRub"], 0)
        self.assertEqual(result["expenses"]["food"]["groupRub"], 35100)

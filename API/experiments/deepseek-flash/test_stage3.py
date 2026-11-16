import unittest
from argparse import Namespace
from unittest.mock import patch

from stage3 import MEALS, benefits_for, build_dates, estimate_category, group_total, note_amount, uncovered_days


class BudgetTests(unittest.TestCase):
    args = Namespace(verify_tariff=False)

    def test_explicit_rubles_keep_scope_and_caps_are_not_estimates(self):
        self.assertEqual(note_amount("Резерв ровно 7 500 ₽ на группу за поездку."),
                         ({"amountRub": "7500", "unit": "group_trip"}, False))
        self.assertEqual(note_amount("На питание не больше 900 ₽ на человека в день."),
                         ({"amountRub": "900", "unit": "person_day"}, True))
        self.assertIsNone(note_amount("В ресторане обед стоит от 900 ₽ на человека в день."))
        self.assertIsNone(note_amount("Потратим примерно 900 ₽ на человека за поездку."))

    def test_calendar_deducts_only_overlapping_included_days(self):
        planned = {"dayIndices": [1, 3]}
        self.assertEqual(uncovered_days(planned, {"coveredDays": 2, "dayIndices": [2, 3]}, 3), (1, 1))
        self.assertEqual(uncovered_days(planned, {"coveredDays": 1}, 3), (2, 0))
        self.assertEqual(uncovered_days({"dayIndices": [1, 2, 3]}, {"coveredDays": 2}, 3), (1, 2))

    def test_trip_transport_quantity_is_not_multiplied_by_days(self):
        with patch("stage3.suggest", return_value={"amountRub": 159, "references": ["metro_ride"],
                                                  "assumption": "Две поездки."}) as model:
            result = estimate_category("transport", "Всего за поездку два проезда на метро.",
                                       {"travelers": 3}, 3, [], {}, self.args, {})
        self.assertEqual(model.call_args.args[4], "person_trip")
        self.assertEqual(result["groupRub"], 477)

    def test_cap_keeps_estimate_and_reports_overage(self):
        with patch("stage3.suggest", return_value={"amountRub": 160, "references": ["metro_ride"],
                                                  "assumption": "Две поездки в день."}):
            result = estimate_category("transport", "Не больше 100 ₽ на человека в день.",
                                       {"travelers": 2}, 3, [], {}, self.args, {})
        self.assertEqual((result["groupRub"], result["overCapRub"]), (960, 360))

    def test_inclusive_days_and_ruble_rounding(self):
        card = {"startDate": "2027-05-19", "endDate": "2027-05-21", "travelers": 2}
        self.assertEqual(build_dates(card), (3, 2))
        self.assertEqual(group_total("79.42", "person_day", 2, 3), 477)
        self.assertEqual(group_total(500, "person_trip", 2, 3), 1000)
        self.assertEqual(group_total(500, "group_trip", 2, 3), 500)

    def test_unknown_benefit_does_not_cover_days(self):
        benefit = {"kind": "breakfast", "status": "unknown", "coveredDays": 2}
        self.assertEqual(benefits_for({"benefits": [benefit]}, self.args, 3, {})["breakfast"]["coveredDays"], 0)

    def test_confirmed_benefit_needs_source(self):
        benefit = {"kind": "breakfast", "status": "confirmed", "coveredDays": 2}
        with self.assertRaisesRegex(ValueError, "источник"):
            benefits_for({"benefits": [benefit]}, self.args, 3, {})

    def test_explicit_group_reserve_skips_the_model(self):
        card = {"travelers": 5, "fixedExpenses": {"reserve": {"amountRub": 5000, "unit": "group_trip"}}}
        with patch("stage3.complete") as model:
            result = estimate_category("reserve", None, card, 3, [], {}, self.args, {})
        model.assert_not_called()
        self.assertEqual(result["groupRub"], 5000)

    def test_foreign_reference_is_rejected(self):
        with patch("stage3.complete", return_value={"amountRub": 5, "references": ["made_up"], "assumption": "Тест."}):
            with self.assertRaisesRegex(ValueError, "Непригодная оценка"):
                estimate_category("transport", None, {"travelers": 2, "hotel": {"city": "Москва"}},
                                  3, [], {}, self.args, {})

    def test_included_meals_only_reduce_their_own_expenses(self):
        card = {"travelers": 2}
        breakfast = {"status": "confirmed", "coveredDays": 2, "scope": "Завтрак"}
        meals = {meal: {"amountRub": 0, "references": [], "assumption": "Пропущен."} for meal in MEALS}
        for meal in ("breakfast", "lunch"):
            meals[meal] = {"amountRub": 1400, "references": ["cafe_lunch"], "assumption": "В кафе."}
        with patch("stage3.suggest", return_value=meals) as model:
            result = estimate_category("food", "Завтрак и обед.", card, 3, [],
                                       {"breakfast": breakfast}, self.args, {})
        model.assert_called_once()
        self.assertEqual(result["meals"]["breakfast"]["groupRub"], 2800)
        self.assertEqual(result["meals"]["lunch"]["groupRub"], 8400)
        self.assertEqual(result["groupRub"], 11200)

    def test_airport_transfer_does_not_change_city_estimate(self):
        transfer = {"status": "confirmed", "coveredDays": 1, "scope": "Аэропорт → отель"}
        with patch("stage3.suggest", return_value={
            "amountRub": 160, "references": ["metro_ride"], "assumption": "Две поездки.",
        }) as model:
            result = estimate_category("transport", "Метро.", {"travelers": 2}, 3, [],
                                       {"local_shuttle": transfer}, self.args, {})
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result["coveredDays"], 0)
        self.assertEqual(result["groupRub"], 960)

    def test_free_shuttle_covers_only_its_scheduled_days(self):
        transfer = {"status": "confirmed", "coveredDays": 2, "dayIndices": [1, 3],
                    "scope": "Все запланированные поездки", "coversAllPlannedRides": True}
        with patch("stage3.suggest", return_value={
            "amountRub": 160, "references": ["metro_ride"], "assumption": "Две поездки.",
        }) as model:
            result = estimate_category("transport", "Метро.", {"travelers": 2}, 3, [],
                                       {"local_shuttle": transfer}, self.args, {})
        model.assert_called_once()
        self.assertEqual(result["groupRub"], 320)

    def test_tariff_lookup_requires_quote_about_the_selected_tariff(self):
        card = {"startDate": "2027-05-19", "endDate": "2027-05-21",
                "hotel": {"tariffName": "Стандартный"}}
        args = Namespace(verify_tariff=True)
        for quote, status, count in (("Завтрак доступен гостям.", "unknown", 0),
                                     ("Стандартный: завтрак включён.", "confirmed", 2)):
            with self.subTest(quote=quote), patch("source_reader.Reader"), patch("stage2.probe", return_value={
                "status": "confirmed", "quote": quote, "source": "https://example.com/tariffs",
            }):
                trace = {}
                result = benefits_for(card, args, 3, trace)["breakfast"]
                self.assertEqual((result["status"], result["coveredDays"]), (status, count))
                self.assertEqual(trace["tariffVerification"]["appliedStatus"], status)

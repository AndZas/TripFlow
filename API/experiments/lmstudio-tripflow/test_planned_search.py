"""Test deterministic execution of validated search plans."""

import unittest

from planned_search import CASES, ConfirmedPreferences, apply_confirmed, confirmation_needed, execute_plan


def plan(categories=(), basis="unknown", count=None, free_only=False, name=None):
    return {
        "categories": list(categories), "paidVisitBasis": basis, "paidVisitCount": count,
        "freeOnly": free_only, "preferredName": name,
    }


class PlannedSearchTests(unittest.TestCase):
    def test_daily_count_uses_inclusive_dates(self):
        trip = CASES["museum-per-day"].trip
        outcome = execute_plan(plan(("museums",), "daily", 1), trip)
        self.assertEqual(outcome["museumEstimate"]["suggestedVisitsPerPerson"], 4)
        self.assertEqual(outcome["museumEstimate"]["groupTotalRub"], 4_008)

    def test_free_only_preserves_unknown_candidate_prices(self):
        trip = CASES["free-only"].trip
        outcome = execute_plan(plan(("museums", "nature"), "none", free_only=True), trip)
        self.assertEqual(outcome["attractions"], [])
        self.assertEqual(outcome["museumEstimate"]["groupTotalRub"], 0)

    def test_explicit_opt_out_returns_no_attractions(self):
        outcome = execute_plan(plan(), CASES["no-places"].trip)
        self.assertEqual(outcome["attractions"], [])

    def test_named_attraction_and_exclusion_use_source_candidates(self):
        trip = CASES["refine-add-history"].trip
        outcome = execute_plan(plan(("museums", "historic"), name="Цветаевой"), trip)
        self.assertEqual([row["id"] for row in outcome["attractions"]],
                         ["historic-2", "museums-2", "historic-1"])
        self.assertIsNone(outcome["museumEstimate"])

    def test_regeneration_rejects_budget_changes(self):
        trip = CASES["refine-add-history"].trip
        with self.assertRaisesRegex(ValueError, "Unexpected budget"):
            execute_plan(plan(("museums",), "trip", 1), trip)

    def test_invalid_model_arguments_are_rejected(self):
        trip = CASES["friends-weekend"].trip
        for invalid in (plan(("museums", "museums")), plan(("fake",)),
                        plan(basis="trip", count=True), plan(basis="unknown", count=1)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                execute_plan(invalid, trip)

    def test_confirmed_scope_corrects_plausible_but_wrong_model_plan(self):
        trip = CASES["friends-weekend"].trip
        interpreted = plan(("museums", "nature"), "daily", 1)
        confirmed = apply_confirmed(interpreted, ConfirmedPreferences(visit_plan=("trip", 1)))
        estimate = execute_plan(confirmed, trip)["museumEstimate"]
        self.assertEqual(estimate["groupTotalRub"], 2_004)

    def test_confirmed_free_only_overrides_model_and_avoids_unknown_prices(self):
        trip = CASES["free-only"].trip
        interpreted = plan(("museums", "nature"), "trip", 2)
        confirmed = apply_confirmed(interpreted, ConfirmedPreferences(free_only=True))
        result = execute_plan(confirmed, trip)
        self.assertEqual(result["attractions"], [])
        self.assertEqual(result["museumEstimate"]["groupTotalRub"], 0)

    def test_confirmation_fields_follow_operation(self):
        self.assertEqual(confirmation_needed(CASES["refine-hotel-group-cap"].trip, ConfirmedPreferences()), [])
        self.assertEqual(
            confirmation_needed(CASES["refine-add-history"].trip, ConfirmedPreferences()),
            ["categories", "freeOnly"],
        )
        self.assertEqual(
            confirmation_needed(CASES["free-only"].trip, ConfirmedPreferences(("nature",), True)), [],
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from analyze import (FILTERS, EXPENSES, analyze, expense_clauses, expense_fields, read_filters,
                     review_candidates, search_query, validate)


def states(**entries):
    result = {value: {"state": "unset", "quote": None} for values in FILTERS.values() for value in values}
    result.update({value: {"state": state, "quote": quote} for value, (state, quote) in entries.items()})
    return result


class AnalyzeTests(unittest.TestCase):
    def test_empty_text_skips_inference(self):
        with patch("analyze.complete") as complete:
            result = analyze("  ", 1234, "stub", {})
        complete.assert_not_called()
        self.assertEqual(result, {"filters": [], "extra": [], "expenses": dict.fromkeys(
            ("food", "transport", "other", "reserve")
        )})

    def test_parses_two_steps_and_writes_labels_for_extra(self):
        extraction = {"states": states(),
                      "extra": [{"condition": "Живая музыка", "strength": "preferred",
                                 "quote": "Желательно с музыкой"}]}
        wording = {
            "label": "Живая музыка", "question": "Есть ли живая музыка?",
            "searchTerms": "живая музыка расписание",
            "labels": {"confirmed": "Есть живая музыка.", "contradicted": "Живой музыки нет.",
                       "unknown": "Живую музыку подтвердить не удалось."},
        }
        with patch("analyze.complete", side_effect=[
            extraction, {**dict.fromkeys(EXPENSES, []), "food": [1]}, wording,
        ]) as complete, patch("analyze.sleep"):
            result = analyze("Желательно с музыкой. Обедаем в кафе.", 1234, "stub", {})
        self.assertEqual(complete.call_count, 3)
        self.assertEqual(result["expenses"]["food"], "Обедаем в кафе.")
        self.assertEqual(search_query(result["extra"][0], "Отель А", "Москва"),
                         "Отель А Москва живая музыка расписание")

    def test_invalid_filter_pair_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Неподдерживаемый фильтр"):
            validate({"filters": [{"kind": "hotel_amenity", "value": "museums",
                                   "strength": "required", "excluded": False}],
                      "extra": [], "expenses": dict.fromkeys(EXPENSES)})

    def test_unknown_expense_excerpt_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Неизвестный индекс"):
            expense_fields({**dict.fromkeys(EXPENSES, []), "food": [1]}, ["Едим в кафе"])

    def test_unrelated_amenity_and_explicit_indifference_do_not_become_filters(self):
        text = "Едим в столовой. Wi-Fi не важен."
        raw = {"states": states(restaurant=("prefer", "Едим в столовой"),
                                wifi=("exclude", "Wi-Fi не важен"))}
        self.assertEqual(read_filters(raw, text), [])

    def test_ambiguous_negation_triggers_focused_review(self):
        raw = states(museums=("avoid", "Музеи смотрим охотно"))
        self.assertEqual(review_candidates(raw, "Музеи смотрим охотно, но без строгого требования."), ["museums"])

    def test_separates_expense_clauses(self):
        self.assertEqual(expense_clauses("Обеды берём с собой, а на городском транспорте ездим редко."),
                         ["Обеды берём с собой", "а на городском транспорте ездим редко."])

    def test_other_keeps_planned_cinema(self):
        result = expense_fields({**dict.fromkeys(EXPENSES, []), "other": [0]}, ["Разок сходим в кино."])
        self.assertEqual(result["other"], "Разок сходим в кино.")

    def test_reserve_is_not_miscellaneous_spending(self):
        clause = "На всякий случай оставим 6 000 ₽ на всю компанию."
        result = expense_fields({**dict.fromkeys(EXPENSES, []), "other": [0]}, [clause])
        self.assertIsNone(result["other"])
        self.assertEqual(result["reserve"], clause)

    def test_explicit_theatre_spending_survives_adjacent_reserve(self):
        clauses = expense_clauses("На театр заложим 2 500 ₽ на человека за поездку, а резерв ровно 4 000 ₽.")
        result = expense_fields({**dict.fromkeys(EXPENSES, []), "reserve": [1]}, clauses)
        self.assertEqual(result["other"], "На театр заложим 2 500 ₽ на человека за поездку")
        self.assertEqual(result["reserve"], "а резерв ровно 4 000 ₽.")

    def test_short_wifi_quote_preserves_train_scope(self):
        prefs = "Wi-Fi нужен в поезде, а у отеля нужна парковка."
        raw = {"states": states(wifi=("require", "Wi-Fi нужен"))}
        self.assertEqual(read_filters(raw, prefs), [])
        self.assertIn("wifi", review_candidates(raw["states"], prefs))

    def test_review_adds_missing_extra_without_losing_anchored_conditions(self):
        text = "Свой ресторан в отеле обязателен. По пятницам желательно с музыкой. Завтрак включён в тариф."
        extraction = {"states": states(restaurant=("prefer", "Свой ресторан в отеле обязателен")), "extra": [
            {"condition": "Свой ресторан в отеле обязателен", "strength": "required",
             "quote": "Свой ресторан в отеле обязателен"},
            {"condition": "Завтрак включён в тариф", "strength": "required", "quote": "Завтрак включён в тариф"},
        ]}
        recovery = {"extra": [{"condition": "Музыка по пятницам", "strength": "preferred",
                               "quote": "По пятницам желательно с музыкой"}]}

        def wording(condition):
            return {"label": condition, "question": f"Подтверждается ли {condition}?",
                    "searchTerms": condition, "labels": {key: f"{condition} ({key})"
                                                         for key in ("confirmed", "contradicted", "unknown")}}

        with patch("analyze.complete", side_effect=[
            extraction, dict.fromkeys(EXPENSES, []), recovery,
            wording("Завтрак включён в тариф"), wording("Музыка по пятницам"),
        ]), patch("analyze.sleep"):
            result = analyze(text, 1234, "stub", {})
        self.assertEqual([item["condition"] for item in result["extra"]],
                         ["Завтрак включён в тариф", "Музыка по пятницам"])
        self.assertEqual(result["filters"][0]["strength"], "required")

    def test_labels_fall_back_when_model_describes_strength_instead_of_fact(self):
        trace = {}
        with patch("analyze.complete", side_effect=[
            {"states": states(), "extra": [{"condition": "Бассейн", "strength": "preferred",
                                           "quote": "Бассейн желателен"}]},
            dict.fromkeys(EXPENSES, []),
            {"label": "Бассейн", "question": "Есть ли бассейн?", "searchTerms": "бассейн",
             "labels": {"confirmed": "Бассейн желателен.", "contradicted": "Бассейн не желателен.",
                        "unknown": "Подтвердить не удалось."}},
        ]), patch("analyze.sleep"):
            result = analyze("Бассейн желателен.", 1234, "stub", trace)
        self.assertEqual(result["extra"][0]["labels"]["confirmed"], "Источники подтверждают условие.")
        self.assertTrue(trace["wording"][0]["neutralLabels"])

    def test_hotel_rental_alone_does_not_imply_transport_plan(self):
        clauses = ["При гостинице можно взять велосипед напрокат.",
                   "Возьмём велосипед напрокат при гостинице и будем ездить по городу."]
        result = expense_fields({**dict.fromkeys(EXPENSES, []), "transport": [0, 1]}, clauses)
        self.assertEqual(result["transport"], clauses[1])

    def test_too_long_input_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze("я" * 2001, 1234, "stub", {})


if __name__ == "__main__":
    unittest.main()

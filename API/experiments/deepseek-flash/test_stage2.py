import unittest
from argparse import Namespace
from unittest.mock import patch

from evidence import Page, identity, judge, known_sources
from source_reader import public_url
from stage2 import admission, hotel_from_row, place_candidates, select


class EvidenceTests(unittest.TestCase):
    def test_breakfast_price_comes_from_the_same_rate(self):
        center = {"latitude": 55, "longitude": 37}
        rooms = [{"price_client": price, "placement_type": {"id": "1"}, "food_type": {"name": meal}}
                 for price, meal in [(3000, "Нет питания"), (4000, "Завтрак")]]
        row = {"id": "1", "name": "Отель", "city": {"name": "Москва"}, "address": "Адрес",
               "geo_lat": 55, "geo_lon": 37, "rooms": rooms}
        request = {"required": True, "included": True}
        result = hotel_from_row(row, {"city": "Москва"}, center, 4, 2, 32000, request)
        self.assertEqual((result["indicativeGroupRub"], result["breakfastStatus"]), (32000, "confirmed"))
        self.assertIsNone(hotel_from_row(row, {"city": "Москва"}, center, 4, 2, 31000, request))

    def test_fee_information_keeps_unknown_price_distinct_from_free(self):
        self.assertEqual(admission({}, ["no_fee.not_specified"]), ("unknown", None))
        self.assertEqual(admission({"fee": "yes"}, []), ("paid", None))
        self.assertEqual(admission({"fee": "no"}, []), ("free", 0))
        self.assertEqual(admission({"charge": "500 RUB"}, []), ("paid", 500))
    def test_namesake_with_different_address_is_rejected(self):
        hotel = {"name": "Славянка", "city": "Москва", "address": "Суворовская площадь, 2/3"}
        self.assertTrue(identity(hotel, "Славянка, Москва, Суворовская площадь, 2/3"))
        self.assertFalse(identity(hotel, "Славянка, Москва, площадь Европы, 2/3"))
        self.assertFalse(identity(hotel, "Славянка, Москва, Суворовская площадь 22. Заезд для 2/3 гостей."))

    def test_registry_does_not_use_id_alone(self):
        self.assertFalse(known_sources({"id": "16", "name": "Другой отель", "city": "Москва"}))
        self.assertTrue(known_sources({"id": "16", "name": "Золотое кольцо", "city": "Москва",
                                       "address": "Смоленская улица, 5"}))

    def test_url_reader_rejects_local_targets(self):
        self.assertFalse(public_url("https://127.0.0.1/"))
        self.assertFalse(public_url("file:///C:/Windows/"))
        self.assertFalse(public_url("https://example.com:1234/"))

    def test_html_keeps_visible_text_and_link(self):
        parsed = Page()
        parsed.feed('<script>Вымышленная фраза</script><p><a href="/news">Афиша</a></p>')
        self.assertEqual(parsed.lines(), ["Афиша"])
        self.assertEqual(parsed.links, [("/news", "Афиша")])

    def test_missing_page_does_not_call_model(self):
        with patch("evidence.complete") as model:
            result = judge({}, "Условие?", [], None, {})
        model.assert_not_called()
        self.assertEqual(result["status"], "unknown")

    def test_source_fragment_is_supplied_by_python(self):
        evidence = [{"id": 1, "url": "https://example.com/", "text": "Завтрак оплачивается отдельно."}]
        with patch("evidence.complete", return_value={
            "answer": "no", "evidenceId": 1, "reason": "Платный завтрак.", "supportQuote": "оплачивается отдельно",
        }):
            result = judge({}, "Включён ли завтрак?", evidence, None, {})
        self.assertEqual(result["quote"], evidence[0]["text"])
        self.assertEqual(result["source"], evidence[0]["url"])

    def test_unknown_source_id_downgrades_status(self):
        with patch("evidence.complete", return_value={
            "answer": "yes", "evidenceId": 2, "reason": "Ответ.", "supportQuote": "Текст",
        }):
            result = judge({}, "Есть ли парковка?", [{"id": 1, "url": "https://example.com/", "text": "Текст"}],
                           None, {})
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["source"])

    def test_recurring_music_is_not_confirmation_for_a_dated_trip(self):
        page = {"id": 1, "url": "https://example.com/", "text": "Живая музыка по средам. Ремонт до 19.05.2027."}
        with patch("evidence.complete", return_value={"answer": "yes", "evidenceId": 1, "reason": "По средам.",
                                                      "supportQuote": "Живая музыка по средам."}):
            result = judge({}, "Есть ли живая музыка?", [page], ["2027-05-19", "2027-05-20"], {})
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["source"], page["url"])

    def test_delivery_does_not_disprove_hotel_restaurant(self):
        page = {"id": 1, "url": "https://example.com/", "text": "Доставляем еду из ближайшего ресторана."}
        with patch("evidence.complete", return_value={"answer": "no", "evidenceId": 1, "reason": "Доставка.",
                                                      "supportQuote": "Доставляем еду из ближайшего ресторана."}):
            result = judge({}, "Есть ли собственный ресторан?", [page], None, {})
        self.assertEqual(result["status"], "unknown")

    def test_invented_quote_downgrades_verdict(self):
        page = {"id": 1, "url": "https://example.com/", "text": "Завтрак подаётся с 7:30."}
        with patch("evidence.complete", return_value={"answer": "yes", "evidenceId": 1, "reason": "Включён.",
                                                      "supportQuote": "Завтрак включён"}):
            result = judge({}, "Включён ли завтрак?", [page], None, {})
        self.assertEqual(result["status"], "unknown")

    def test_another_tariff_does_not_disprove_meal_inclusion(self):
        page = {"id": 1, "url": "https://example.com/", "text": "Завтрак входит в тариф «Гибкий»."}
        with patch("evidence.complete", return_value={"answer": "no", "evidenceId": 1, "reason": "Другой тариф.",
                                                      "supportQuote": page["text"]}):
            result = judge({}, "Включён ли завтрак в тариф «Базовый»?", [page], None, {})
        self.assertEqual(result["status"], "unknown")

    def test_general_late_checkout_does_not_disprove_specific_hour(self):
        page = {"id": 1, "url": "https://example.com/", "text":
                "Поздний выезд из номера после 12:00 возможен при наличии свободных номеров."}
        with patch("evidence.complete", return_value={"answer": "no", "evidenceId": 1, "reason": "Время не указано.",
                                                      "supportQuote": page["text"]}):
            result = judge({}, "Можно ли сделать поздний выезд до 15:00?", [page], None, {})
        self.assertEqual(result["status"], "unknown")

    def test_places_recheck_required_categories_and_remove_duplicates(self):
        museum = {"place_id": "one", "name": "Музей", "city": "Москва", "categories": ["entertainment.museum"]}
        park = {"place_id": "two", "name": "Парк", "city": "Москва", "categories": ["leisure.park"]}
        rules = [{"kind": "attraction_category", "value": "museums", "strength": "required", "excluded": False}]
        destination = {"city": "Москва", "coordinates": {"latitude": 55, "longitude": 37}}
        with patch.dict("os.environ", {"GEOAPIFY_API_KEY": "stub"}), patch("stage2.read_json", return_value={
            "features": [{"properties": properties} for properties in (museum, park, museum)],
        }):
            result = place_candidates(destination, rules, 5)
        self.assertEqual([row["id"] for row in result], ["one"])

    def test_hotel_search_continues_after_four_rejected_and_skips_optional_checks(self):
        hotels = [{"id": str(i)} for i in range(6)]
        required = {"question": "Обязательно?", "strength": "required"}
        optional = {"question": "Желательно?", "strength": "preferred"}
        card = {"destination": "ru-moscow", "startDate": "2027-05-19", "endDate": "2027-05-21",
                "travelers": 2, "preferences": "Тест"}

        def verdict(hotel, requirement, *_):
            status = "confirmed" if hotel["id"] == "4" else "unknown"
            return {"requirement": requirement, "status": status}

        with patch("stage2.analyze", return_value={"filters": [], "extra": [optional, required]}), \
                patch("stage2.hotel_candidates", return_value=hotels), \
                patch("stage2.place_candidates", return_value=[]), \
                patch("stage2.probe", side_effect=verdict) as probe:
            result = select(card, Namespace(), None)
        self.assertEqual([row["id"] for row in result["hotels"]], ["4"])
        self.assertEqual(sum(call.args[1] == optional for call in probe.call_args_list), 1)

    def test_exclusion_does_not_treat_missing_evidence_as_absence(self):
        rules = [{"kind": "hotel_amenity", "value": "wifi", "strength": "required", "excluded": True}]
        card = {"destination": "ru-moscow", "startDate": "2027-05-19", "endDate": "2027-05-21",
                "travelers": 2, "preferences": "Без Wi-Fi"}

        def verdict(hotel, requirement, *_):
            return {"requirement": requirement, "status": hotel["status"]}

        hotels = [{"id": "1", "status": "unknown"}, {"id": "2", "status": "contradicted"}]
        with patch("stage2.analyze", return_value={"filters": rules, "extra": []}), \
                patch("stage2.hotel_candidates", return_value=hotels), \
                patch("stage2.place_candidates", return_value=[]), \
                patch("stage2.probe", side_effect=verdict):
            result = select(card, Namespace(), None)
        self.assertEqual([row["id"] for row in result["hotels"]], ["2"])

import hashlib
import json
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from hotel_fixtures import CHECK_IN, HotelProvider, NAMES, completion
from tripflow_api.hotel_evidence import Rate, checked_rate, group_price, rate_applies, rate_quality, source_decimal, source_url
from tripflow_api.hotel_enrichment import collect_fields, parse_page, read_page
from tripflow_api.hotel_tools import BudgetStop, HotelTools
from tripflow_api.hotels import EXTRACT, PLAN, HotelSearch
from tripflow_api.main import app
from tripflow_api.preferences import encode
from tripflow_api.schemas import RecommendationsRequest


KYOTO = {"city": "Киото", "countryCode": "JP", "latitude": 35.01, "longitude": 135.77}
BUILDER = "/portal/data/builder"
DETAILS = "/portal/data/preferences/tasks/"


def isolated_test_url(resources):
    url = os.getenv("TRIPFLOW_TEST_DATABASE_URL", "")
    if not url:
        return url
    import psycopg
    from psycopg.conninfo import make_conninfo

    schema = "hotels_test_" + uuid4().hex
    connection = resources.enter_context(psycopg.connect(url, autocommit=True))
    connection.execute(f"CREATE SCHEMA {schema}")
    resources.callback(connection.execute, f"DROP SCHEMA {schema} CASCADE")
    return make_conninfo(url, options=f"-c search_path={schema}")


def recommendation(**kwargs):
    return {"taskId": uuid4().hex, "trip": {
        "destination": KYOTO, "startDate": "2027-05-15", "endDate": "2027-05-17",
        "travelers": 3, "budgetRub": 100_000, "preferences": None,
    }, "targets": "hotels", "count": 1, "maxTotalRub": 48000, "refinement": None, "excludedObjectIds": [], **kwargs}


class StageTwoTest(unittest.TestCase):
    def setUp(self):
        resources = ExitStack()
        self.addCleanup(resources.close)
        root = resources.enter_context(TemporaryDirectory())
        self.owner = {"email": "stage-two@example.test", "password": "stage-two-password"}
        resources.enter_context(patch.dict(os.environ, {
            "TRIPFLOW_STATE_PATH": str(Path(root) / "hotels.sqlite3"), "DATABASE_URL": isolated_test_url(resources),
            "TRIPFLOW_PORTAL_ADMIN_EMAIL": self.owner["email"], "TRIPFLOW_PORTAL_ADMIN_PASSWORD": self.owner["password"],
            "HOTEL_SEARCH_PROFILE": "A", "HOTEL_ENRICHMENT": "off", "DEEPSEEK_API_KEY": "test-hotels", "GEOAPIFY_API_KEY": "test-cities", "RENDER": "",
        }))
        self.provider = HotelProvider()
        self.model = None

        def transport(request):
            if self.model and request.url.path == "/chat/completions":
                data = json.loads(json.loads(request.content)["messages"][1]["content"])
                if "destination" not in data:
                    return self.model(data)
            return self.provider(request)

        original = httpx.AsyncClient
        resources.enter_context(patch("tripflow_api.main.httpx.AsyncClient", side_effect=lambda **kwargs:
                                      original(transport=httpx.MockTransport(transport), **kwargs)))
        self.client = resources.enter_context(TestClient(app, headers={"X-Portal-Request": "1"}))
        account = self.client.post("/portal/data/login", json=self.owner).json()["account"]
        self.owner_id = account["id"]
        self.headers = {"X-API-Key": self.client.post("/portal/data/keys/api/issue", json={}).json()["key"]}

    def submit(self, body, *, portal=False, path="recommendations"):
        headers = None if portal else self.headers
        response = self.client.post(f"{BUILDER if portal else '/v1'}/{path}", json=body, headers=headers)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.headers["Retry-After"], "2")
        for _ in range(100):
            result = self.client.get(response.headers["Location"], headers=headers).json()
            if result["status"] == "completed":
                return result["result"]
            time.sleep(0.05)
        self.fail("Task did not complete")

    def hotels(self, body, **kwargs):
        return self.submit(body, **kwargs)["results"]["hotels"]

    def diagnostics(self, body):
        return self.client.get(DETAILS + body["taskId"]).json()["hotels"]

    def test_validation_madrid_saved_indices_and_mixed_languages(self):
        name, address = "Hotel Europa", "Calle Carmen, 4, Madrid, Spain"
        spanish = "Habitaciones | Hotel Europa, Puerta del Sol, Madrid - Mejor precio"
        english = "Rooms | Hotel Europa, Puerta del Sol, Madrid - Best price"
        pages = [
            ("https://www.hoteleuropa.eu/habitaciones/", spanish, "### Habitación Europa Individual\n\nDesde87€por noche"),
            ("https://www.hoteleuropa.eu/de/zimmer/", "Zimmer | Hotel Europa, Puerta del Sol, Madrid - Bestpreis", ""),
            ("https://www.hoteleuropa.eu/en/rooms/", english, "## Rooms\n\n### Single\n\nFrom92€per night"),
            ("https://www.travala.com/hotel/hotel-europa-12591643", "Hotel Europa | Travala", address),
            ("https://www.trivago.ca/fr-CA/oar/hotel-europa-madrid", "Hotel Europa - Mai 2026", ""),
            ("https://de.hotels.com/ho403932576/hotel-europa-madrid-spanien/", "Hotel Europa in Madrid: Preise",
             "Calle Carmen, 4, Madrid, Madrid, 28013")]
        self.provider.city = "Madrid"
        self.provider.pages = lambda: [{"url": url, "title": title, "content": f"{title}\n{data}"} for url, title, data in pages]
        item = {"name": name, "identity": {"source": 1, "quote": name}, "city": {"source": 4, "quote": address},
                "address": {"source": 4, "quote": address}, "rates": [
            {"source": 1, "amount": "87", "basis": "room_night", "block": 1, "currency": "EUR", "kind": "from",
             "quote": "Desde87€por noche", "rooms": 1, "support": ["Habitación Europa Individual"]},
            {"source": 3, "amount": "92", "basis": "room_night", "block": 1, "currency": "EUR", "kind": "from",
             "quote": "From92€per night", "rooms": 1, "support": ["Single"]}]}
        self.provider.extraction = lambda data: [item] if len(data["pages"]) == 6 else []
        dest = {"city": "Мадрид", "countryCode": "ES", "latitude": 40.4168, "longitude": -3.7038}
        body = recommendation(maxTotalRub=None, targetHotelTotalRub=400000, trip={**recommendation()["trip"],
            "destination": dest, "travelers": 2, "endDate": "2027-05-18"})
        batch = self.hotels(body, portal=True)
        self.assertEqual([row["price"] for row in batch["items"]], [55200])
        report = self.diagnostics(body)
        self.assertEqual(report["hotels"][0]["price"]["rate"]["sourceUrl"], pages[2][0])
        self.assertEqual(report["hotels"][0]["price"]["level"], "offer")
        self.assertEqual(self.provider.plans[0]["targetRoomNightRub"], 66667)
        # A far-away price may trigger the separately bounded target search.
        no_target = {**body, "taskId": uuid4().hex, "targetHotelTotalRub": None}
        self.assertEqual([row["price"] for row in self.hotels(no_target)["items"]], [52200])
        self.assertEqual(self.diagnostics(no_target)["calls"]["search"], 0)

    def test_validation_istanbul_saved_localized_quote_and_different_branch(self):
        name = "Mövenpick Hotel Istanbul Marmara Sea"
        address = "Kazlıçeşme, Abay Cd. No: 167, Zeytinburnu, 34020 Istanbul, Thổ Nhĩ Kỳ"
        primary = "https://vn.trip.com/hotels/istanbul-hotel-detail-117059016/mvenpick-hotel-istanbul-marmara-sea/"
        template = "https://us.trip.com/hotels/detail/?cityEnName=Istanbul&hotelId={}&checkIn=2026-11-24&checkOut=2026-11-25&crn=1&curr=USD"
        vietnamese = {"url": primary, "title": name + ", Istanbul: Giá phòng | Trip.com",
                      "content": f"{name}\n{address}"}
        english = {"url": template.format("117059017"), "title": name + " (Istanbul) - 2026 Prices | Trip.com",
                   "content": f"{name}\nAbay St. 167, Zeytinburnu, Istanbul, Türkiye\n### Superior Twin Room City Side\n1 adult\n$160\n"
                              "### Deluxe Suite Room\nBreakfast included\n1 adult\n$237"}
        dummy = [{"url": f"https://directory.example.test/{i}", "title": f"Directory {i}", "content": "Istanbul"}
                 for i in range(4)]
        self.provider.pages = lambda: [vietnamese, *dummy, english]
        self.provider.city = "Istanbul"
        item = {"name": name, "identity": {"source": 1, "quote": name}, "city": {"source": 1, "quote": address},
                "address": {"source": 1, "quote": address}, "rates": [
            {"source": 6, "amount": "160", "basis": "room_night", "block": 1, "currency": "USD", "kind": "published",
             "quote": "Superior Twin Room City Side\n1 adult\n$160", "rooms": 1,
             "support": ["Superior Twin Room City Side", "1 adult"]},
            {"source": 6, "amount": "237", "basis": "room_night", "block": 2, "currency": "USD", "kind": "published",
             "quote": "Deluxe Suite Room\nBreakfast included\n1 adult\n$237", "rooms": 1,
             "support": ["Deluxe Suite Room", "Breakfast included"]}]}
        self.provider.extraction = lambda data: [item] if len(data["pages"]) == 6 else []
        dest = {"city": "Стамбул", "countryCode": "TR", "latitude": 41.008, "longitude": 28.978}
        body = recommendation(maxTotalRub=None, trip={**recommendation()["trip"], "destination": dest,
                                                      "travelers": 2, "endDate": "2027-05-18"})
        self.assertEqual(self.hotels(body)["items"], [])
        flags = self.diagnostics(body)["sourceIssues"]
        self.assertTrue(any(row["reason"] == "unlinked_property" and row["quoteFound"] for row in flags))
        english["url"] = template.format("117059016")
        good = {**body, "taskId": uuid4().hex, "trip": {**body["trip"], "budgetRub": 87000}}
        actual = [row["price"] for row in self.hotels(good, portal=True)["items"]]
        self.assertEqual(actual, [86400], self.diagnostics(good)["sourceIssues"])
        report = self.diagnostics(good)["hotels"][0]["price"]
        self.assertEqual((report["level"], report["basis"], report["rate"]["rooms"]),
                         ("offer", "other_period", 1))
        self.assertIn("hotelId=117059016", report["rate"]["sourceUrl"])

    def test_validation_trip_com_dorm_does_not_qualify_with_one_adult(self):
        name = "HI New York City Hostel"
        url = "https://us.trip.com/hotels/detail/?cityEnName=New+York&hotelId=2092657&checkIn=2026-11-25&checkOut=2026-11-26&adult=2&crn=1&curr=USD"
        address = "891 Amsterdam Avenue, New York, NY, US"
        price = "$95"
        room = "Bed In Men's 8-Bed Dormitory (Male Only)"
        page = {"url": url, "title": name, "content":
                f"{name}\n{address}\n## Location\n{room}\n\n1 bunk bed\n\n1 adult\n\n{price}"}
        self.provider.city = "New York"
        self.provider.pages = lambda: [page]
        self.provider.extraction = lambda _: [{
            "name": name, "identity": {"source": 1, "quote": name},
            "city": {"source": 1, "quote": address}, "address": {"source": 1, "quote": address},
            "rates": [{"source": 1, "amount": "95", "currency": "USD", "basis": "room_night",
                       "kind": "published", "block": 1, "quote": price, "support": ["1 adult"]}],
        }]
        dest = {"city": "Нью-Йорк", "countryCode": "US", "latitude": 40.71, "longitude": -74.01}
        body = recommendation(maxTotalRub=None, trip={**recommendation()["trip"], "destination": dest})
        self.assertEqual(self.hotels(body)["items"], [])
        report = self.diagnostics(body)
        self.assertEqual(report["coverage"]["cityConfirmed"], 1)
        self.assertIn("unverified_unit", {row["reason"] for row in report["sourceIssues"]})

        # Revalidate the old proof, which had already lost the dorm heading.
        old = {"sourceUrl": url, "quote": price, "unitQuote": "## Location\n1 adult\n$95", "currency": "USD",
               "amount": "95", "basis": "room_night", "rooms": 1, "scope": "offer",
               "start": "2026-11-25", "end": "2026-11-26", "printedAmount": ["95"],
               "minNights": None, "maxNights": None, "weekdays": None}
        trip = RecommendationsRequest.model_validate(body).trip
        self.assertIsNone(rate_quality(old, trip, 2))

    def test_validation_catalog_address_does_not_link_unverified_rate_page(self):
        name = "Oak Hotel"
        address = "12 Station Road, Kyoto"
        quote = "Single room for 1 adult | 5000 RUB per room per night"
        own = {"url": "https://oak-kyoto.example.test/location", "title": f"{name} — Kyoto", "content": address}
        unrelated = {"url": "https://oak-west.example.test/rooms", "title": f"{name} — rooms",
                     "content": f"## {name}\n{quote}"}
        city = {"source": 1, "quote": address}
        candidate = {"name": name, "identity": {"source": 1, "quote": name}, "city": city, "address": city}
        self.provider.pages = lambda: [own]
        self.provider.extraction = lambda data: [candidate]
        body = recommendation(maxTotalRub=None)
        self.assertEqual(self.hotels(body)["items"], [])
        self.provider.pages = lambda: [own, unrelated]
        self.provider.extraction = lambda data: [
            {**candidate, "rates": [{"source": 2, "quote": quote, "amount": "5000", "currency": "RUB",
                                    "basis": "room_night", "kind": "published"}]}
        ] if len(data["pages"]) == 2 else []
        retry = {**body, "taskId": uuid4().hex, "trip": {**body["trip"], "budgetRub": 200000}}
        self.assertEqual(self.hotels(retry)["items"], [])
        self.assertTrue(any(row["reason"] == "unlinked_property" and row["quoteFound"]
                            for row in self.diagnostics(retry)["sourceIssues"]))

    def test_validation_malformed_fields_and_block_recovery_preserve_object(self):
        name = "Hôtel Rive"
        title = name + ", Kyoto"
        quote = "From 8,000 RUB per room per night"
        page = {"url": "https://rive.example.test/rooms/", "title": title, "content":
                f"{title}\n### Single\n{quote}\n### Superior Single\nFrom 12,000 RUB per room per night"}
        self.provider.pages = lambda: [page]
        item = {"name": name, "identity": {"source": 1, "quote": name}, "stars": "five",
                "rates": [{"source": 1, "currency": "RUB", "amount": {"bad": 8000}},
                          {"source": 1, "currency": "RUB", "amount": "8000", "basis": "room_night",
                           "block": 0, "quote": quote, "kind": "from", "support": ["Single"]}]}
        self.provider.extraction = lambda data: [item]
        body = recommendation()
        self.assertEqual([row["price"] for row in self.hotels(body)["items"]], [48000])
        report = self.diagnostics(body)
        self.assertEqual(report["coverage"]["priceLevels"]["offer"], 1)
        self.assertTrue({"invalid_rate", "invalid_optional_field"} <= {row["reason"] for row in report["sourceIssues"]})
        # A new visit sees two plausible rooms with the same price.
        self.provider.pages = lambda: [{**page, "content": page["content"].replace(
            "From 12,000 RUB", "From 8,000 RUB")} | {"url": "https://rive.other.test/rooms/"}]
        item["rates"][1]["support"] = []
        dest = {"city": "Осака", "countryCode": "JP", "latitude": 34.69, "longitude": 135.50}
        self.provider.city = "Osaka"
        changed = self.provider.pages
        self.provider.pages = lambda: [{**p, "title": p["title"].replace("Kyoto", "Osaka"),
                                        "content": p["content"].replace("Kyoto", "Osaka")} for p in changed()]
        ambiguous = recommendation(trip={**body["trip"], "destination": dest})
        self.assertEqual(self.hotels(ambiguous)["items"], [])
        self.assertIn("ambiguous_rate_block", {row["reason"] for row in self.diagnostics(ambiguous)["sourceIssues"]})

    def test_validation_room_reference_and_market_price_same_group(self):
        names = ("First Hotel", "Second Hotel", "Third Hotel")
        self.provider.names = names
        quotes = ("Double room for 2 adults | 5,000 RUB per room per night",
                  "Single room for 1 adult | 15,000 RUB per room per night", "Contact us for prices")
        self.provider.price_line = lambda name: quotes[names.index(name)]
        def extract(data):
            return [{"name": p["heading"], "identity": {"source": p["id"], "quote": p["heading"]},
                     "city": {"source": p["id"], "quote": "Kyoto"},
                     "rates": [] if p["heading"] == names[2] else [
                         {"source": p["id"], "quote": quotes[names.index(p["heading"])], "basis": "room_night",
                          "kind": "published", "currency": "RUB", "amount": "5000" if p["heading"] == names[0] else "15000"}]}
                    for p in data["pages"]]
        self.provider.extraction = extract
        body = recommendation(count=2, maxTotalRub=60000, trip={**recommendation()["trip"], "travelers": 2,
                                                               "endDate": "2027-05-18"})
        batch = self.hotels(body, portal=True)
        self.assertEqual([item["price"] for item in batch["items"]], [30000, 60000])
        report = self.diagnostics(body)
        self.assertEqual(report["coverage"]["priceLevels"], {"offer": 1, "room_reference": 1, "market": 1})
        room, market = [row["price"] for row in report["hotels"]]
        self.assertEqual((room["level"], room["rate"]["amount"]), ("room_reference", "5000"))
        self.assertEqual((market["level"], market["rateRubPerRoomNight"], market["spreadRubPerRoomNight"]),
                         ("market", "10000", ["5000", "15000"]))
        self.assertEqual(len({row["objectId"] for row in market["analogs"]}), 2)
        warm = {**body, "taskId": uuid4().hex}
        self.assertEqual(self.hotels(warm), batch)
        self.assertEqual(self.diagnostics(warm)["calls"]["search"], 0)
        more = {**body, "taskId": uuid4().hex,
                "excludedObjectIds": [row["objectId"] for row in batch["items"]]}
        self.assertEqual(self.hotels(more)["items"], [])

        quotes = (*quotes[:2], "Single room for 1 adult | 9,000 RUB per room per night")
        # A distinct travel period exercises a fresh rate lookup for the same property.
        def updated_extract(data):
            items = extract(data)
            for item in items:
                if item["name"] == names[2]:
                    item["rates"] = [{"source": item["identity"]["source"], "quote": quotes[2],
                                      "basis": "room_night", "kind": "published", "currency": "RUB", "amount": "9000"}]
            return items
        self.provider.extraction = updated_extract
        later = {**body, "taskId": uuid4().hex, "trip": {**body["trip"], "startDate": "2027-05-16", "endDate": "2027-05-19"}}
        updated = self.hotels(later)
        third = next(item for item in updated["items"] if item["name"] == names[2])
        self.assertEqual(third["price"], 54000)
        self.assertEqual(next(row["price"]["level"] for row in self.diagnostics(later)["hotels"]
                              if row["item"]["name"] == names[2]), "offer")
        self.assertEqual(self.hotels(body, portal=True), batch)

    def test_validation_recovers_omitted_literal_rate_only_from_confirmed_property(self):
        name = "Station North Hotel"
        price = "From 5,400 RUB per room per night"
        page = {"url": "https://station-north.example.test/rooms", "title": f"{name} — Kyoto",
                "content": f"# {name}\n12 Station Road, Kyoto\n### Single\n{price}"}
        other = "Central South Hotel"
        other_price = price.replace("5,400", "5,500")
        second = {"url": "https://central-south.example.test/rooms", "title": f"{other} — Kyoto",
                  "content": f"# {other}\n21 Station Road, Kyoto\n### Single\n{other_price}"}
        self.provider.pages = lambda: [page, second]
        self.provider.extraction = lambda data: [{
            "name": hotel, "identity": {"source": index, "quote": hotel},
            "city": {"source": index, "quote": "Kyoto"},
            "rates": [] if index == 1 else [{"source": index, "quote": other_price, "amount": "5,500"}],
        } for index, hotel in enumerate((name, other), 1)]
        body = recommendation(count=2, maxTotalRub=None)
        batch = self.hotels(body)
        self.assertEqual({row["price"] for row in batch["items"]}, {32400, 33000})
        report = self.diagnostics(body)
        rate = next(row["price"]["rate"] for row in report["hotels"] if row["item"]["name"] == name)
        self.assertEqual((rate["quote"], rate["kind"], rate["sourceUrl"]), (price, "from", page["url"]))
        self.assertTrue(any(row["reason"] == "invalid_rate" and row["name"] == other for row in report["sourceIssues"]))
        self.assertEqual(self.provider.search_count, 1)

    def test_validation_market_search_finds_compatible_donors(self):
        target, low, high_one, high_two, peer = (
            "Garden Hotel", "Station Hotel", "Palace Hotel", "Grand River Hotel", "Park Hotel")
        rows = {target: (2, None), low: (2, 5000), high_one: (5, 90000),
                high_two: (5, 95000), peer: (3, 9000)}
        base = "https://market-class.example.test/"
        def content(name):
            stars, price = rows[name]
            line = f"Single room | {price} RUB per room per night" if price else "Contact us for prices"
            return f"{name}\nKyoto, Station Road\n{stars}-star hotel\n{line}"
        def pages():
            market = self.provider.queries[-1].endswith("private room nightly rates prices")
            return [{"url": base + str(i), "title": name, "content": content(name)}
                    for i, name in enumerate(rows) if market or name != peer]
        def extract(data):
            items = []
            for page in data["pages"]:
                name, sid = page["heading"], page["id"]
                stars, price = rows[name]
                proof = lambda quote: {"source": sid, "quote": quote}
                rates = [{**proof(content(name).splitlines()[-1]), "amount": str(price), "currency": "RUB",
                          "basis": "room_night", "kind": "published"}] if price else []
                items.append({"name": name, "identity": proof(name), "city": proof("Kyoto"),
                              "stars": proof(f"{stars}-star hotel"), "rates": rates})
            return items
        self.provider.pages = pages
        self.provider.extraction = extract
        body = recommendation(count=3, maxTotalRub=55000)
        self.assertEqual({row["price"] for row in self.hotels(body)["items"]}, {30000, 42000, 54000})
        report = self.diagnostics(body)
        self.assertIsNotNone(report["marketSearch"])
        estimate = next(row["price"] for row in report["hotels"] if row["item"]["name"] == target)
        self.assertEqual(estimate["level"], "market")
        self.assertEqual({row["name"] for row in estimate["analogs"]}, {low, peer})

    def test_rates_minsk_original_flash_quote_and_variable_price(self):
        title = "Цены на номера гостиницы «Беларусь», Минск"
        name = "Гостиница «Беларусь»"
        room, price = "Сингл — одноместный стандартный номер", "260 BYN/сут."
        caveat = "Цена зависит от загрузки гостиницы, и может меняться в зависимости от даты бронирования"
        page = {"url": "https://hotel-belarus.example.test/rooms", "title": title,
                "content": f"{name}\n«*{caveat}»\nПравила проживания\n{room}\n\n{price}"}
        self.provider.pages = lambda: [page]
        self.provider.extraction = lambda data: [{
            "name": name, "identity": {"source": 1, "quote": name}, "city": {"source": 1, "quote": title},
            "rates": [{"source": 1, "quote": f"{room}\n\n{price}", "support": [room, price],
                       "amount": "260", "currency": "BYN", "basis": "room_night", "kind": "published",
                       "rooms": 1, "caveat": caveat}]}]
        dest = {"city": "Минск", "countryCode": "BY", "latitude": 53.90, "longitude": 27.56}
        body = recommendation(maxTotalRub=None, trip={**recommendation()["trip"], "destination": dest,
                                                      "endDate": "2027-05-18", "travelers": 2})
        self.assertEqual([item["price"] for item in self.hotels(body, portal=True)["items"]], [46800])
        details = self.diagnostics(body)["hotels"][0]["price"]
        self.assertEqual((details["exchange"]["currency"], details["exchange"]["valueRub"], details["nights"]),
                         ("BYN", "30", 3))
        self.assertIn(caveat, details["rate"]["variableQuote"])

    def test_rates_unavailable_conversion_keeps_ruble_offer(self):
        names = ("Foreign Hotel", "Local Hotel")
        self.provider.names = names
        quotes = ("Single room for 1 adult | CAD 55 per room per night", "Single room for 1 adult | 8000 RUB per room per night")
        self.provider.price_line = lambda name: quotes[names.index(name)]
        def extract(data):
            return [{"name": p["heading"], "identity": {"source": p["id"], "quote": p["heading"]},
                     "city": {"source": p["id"], "quote": "Kyoto"},
                     "rates": [{"source": p["id"], "quote": quotes[names.index(p["heading"])],
                                "amount": "55" if p["heading"] == names[0] else "8000",
                                "currency": "CAD" if p["heading"] == names[0] else "RUB",
                                "basis": "room_night", "kind": "published"}]}
                    for p in data["pages"]]
        self.provider.extraction = extract
        first = recommendation(count=2)
        self.assertEqual([item["name"] for item in self.hotels(first)["items"]], [names[1]])
        self.assertEqual(self.diagnostics(first)["currencyIssues"][0]["currencies"], [
            {"currency": "CAD", "reason": "fx_currency_missing"}])
        self.client.portal.call(app.state.tasks.connection.execute, "DELETE FROM hotel_fx_cache")
        self.provider.fx_unavailable = True
        second = recommendation(count=2, maxTotalRub=None)
        self.assertEqual([item["name"] for item in self.hotels(second)["items"]], [names[1]])
        self.assertEqual(self.diagnostics(second)["currencyIssues"][0]["currencies"], [
            {"currency": "CAD", "reason": "fx_unavailable"}])

    def test_rates_target_reorders_rates_and_preserves_hard_ceiling_and_history(self):
        self.provider.names = ("Budget Hotel", "River Hotel", "Park Hotel")
        original = self.provider.pages
        totals = ((35000,), (65000, 380000), (430000,))
        dates = "2027-05-15 to 2027-05-18"
        def line(n):
            return f"2 separate single rooms, 1 adult each. {dates}, total {n} RUB per stay"
        self.provider.pages = lambda: [{**p, "content": p["content"].replace(self.provider.price_line(p["title"]),
                                                                             "\n".join(map(line, amounts)))}
                                       for p, amounts in zip(original(), totals)]
        self.provider.extraction = lambda data: [
            {"name": p["heading"], "identity": {"source": p["id"], "quote": p["heading"]},
             "city": {"source": p["id"], "quote": "Kyoto"},
             "rates": [{"source": p["id"], "quote": line(n), "amount": str(n), "currency": "RUB",
                        "basis": "group_stay", "kind": "published", "rooms": 2,
                        "start": "2027-05-15", "end": "2027-05-18"}
                       for n in totals[self.provider.names.index(p["heading"])]]}
            for p in data["pages"]]
        body = recommendation(count=2, maxTotalRub=None, targetHotelTotalRub=400000, trip={
            **recommendation()["trip"], "endDate": "2027-05-18", "travelers": 2})
        result = self.hotels(body, portal=True)
        prices = lambda batch: [item["price"] for item in batch["items"]]
        self.assertEqual(prices(result), [380000, 430000])
        self.assertEqual(self.diagnostics(body)["hotels"][0]["price"]["differenceRub"], -20000)
        new = {**body, "taskId": uuid4().hex, "targetHotelTotalRub": 40000}
        self.assertEqual(prices(self.hotels(new)), [35000, 65000])
        capped = {**body, "taskId": uuid4().hex, "maxTotalRub": 400000}
        self.assertEqual(prices(self.hotels(capped)), [380000, 35000])
        more = {**body, "taskId": uuid4().hex, "excludedObjectIds": [r["objectId"] for r in result["items"]]}
        self.assertEqual(prices(self.hotels(more)), [35000])
        self.assertTrue(self.diagnostics(more)["targetGap"])
        self.assertEqual(self.hotels(body, portal=True), result)
        self.assertEqual(self.client.post(f"{BUILDER}/recommendations", json={**body, "targetHotelTotalRub": 40000}).status_code, 409)
        legacy = {key: value for key, value in {**body, "taskId": uuid4().hex}.items() if key != "targetHotelTotalRub"}
        first = self.hotels(legacy, portal=True)
        self.assertEqual(self.hotels({**legacy, "targetHotelTotalRub": None}, portal=True), first)

    def test_rates_enrichment_is_cached_and_keeps_price_source(self):
        app.state.tasks.hotel_enrichment = True
        self.assertIn("img-src 'self' https:", self.client.get("/portal").headers["Content-Security-Policy"])
        dest = {"city": "Оренбург", "countryCode": "RU", "latitude": 51.77, "longitude": 55.10}
        name, address = "Гостиница Река", "Лесная улица, 10"
        supplier, official = "https://russhotels.ru/hotel/view?id=10", "https://reka.example.test/"
        self.provider.russ = [self.russ_row("10", name, dest, address, 5900)]
        self.provider.pages = lambda: [{"url": official, "title": name + " — официальный сайт", "content": "Оренбург"}]
        def page(url):
            html = (f"<title>{name}</title><meta property='og:image' content='/logo.png'>" if url == supplier else
                    f"<title>{name} — официальный сайт</title><address>Оренбург, {address}</address>"
                    f"<img src='/front.jpg' alt='{name} фасад'>")
            return parse_page(html, url)
        body = recommendation(maxTotalRub=None, trip={**recommendation()["trip"], "destination": dest})
        with patch("tripflow_api.hotel_enrichment.read_page", side_effect=page) as fetched:
            result = self.hotels(body, portal=True)
            item = result["items"][0]
            self.assertEqual((item["address"], item["sourceUrl"], item["imageUrl"]),
                             (address, supplier, official + "front.jpg"))
            report = self.diagnostics(body)
            self.assertEqual(report["hotels"][0]["metadata"]["website"]["value"], official)
            self.assertEqual(report["enrichmentCalls"], {"search": 1, "fetch": 2})
            self.assertEqual(fetched.call_count, 2)
            self.assertEqual(self.hotels({**body, "taskId": uuid4().hex}, portal=True), result)
            self.assertEqual(fetched.call_count, 2)

    def test_coverage_russhotels_two_rates_and_warm_catalog(self):
        destination = {"city": "Калининград", "countryCode": "RU", "latitude": 54.71, "longitude": 20.51}
        self.provider.russ = [
            self.russ_row("10", "Турист", destination, "Лесная улица, 3", 5900),
            self.russ_row("11", "Навигатор", destination, "Лесная улица, 6", 4910),
        ]
        trip = {**recommendation()["trip"], "destination": destination, "endDate": "2027-05-18", "travelers": 2}
        body = recommendation(count=2, trip=trip, maxTotalRub=None)
        batch = self.hotels(body, portal=True)
        self.assertEqual({item["name"]: item["price"] for item in batch["items"]}, {"Турист": 35400, "Навигатор": 29460})
        details = self.diagnostics(body)
        self.assertEqual(details["priceSources"], {"russhotels": 2})
        self.assertEqual(details["calls"]["flash"], 0)
        self.assertEqual({item["price"]["rate"]["providerAmount"] for item in details["hotels"]}, {5900, 4910})
        before = list(self.provider.calls)
        self.assertEqual(self.hotels({**body, "taskId": uuid4().hex}, portal=True), batch)
        self.assertEqual(self.provider.calls, before)
        exact = recommendation(count=2, trip=trip, maxTotalRub=35400)
        over = recommendation(count=2, trip=trip, maxTotalRub=35399)
        self.assertEqual(len(self.hotels(exact)["items"]), 2)
        self.assertEqual([item["name"] for item in self.hotels(over)["items"]], ["Навигатор"])

    @staticmethod
    def russ_row(key, name, destination, address, price):
        return {"id": key, "name": name, "address": address,
                "city": {"id": "27", "name": destination["city"]},
                "geo_lat": str(destination["latitude"]), "geo_lon": str(destination["longitude"]),
                "rooms": [{"id": key + "1", "name": "Стандарт (двуспальная кровать)",
                           "placement_type": {"name": "Одноместное", "sleeping_place": "1"},
                           "price_client": price, "updated_at": "1739423600"},
                          {"id": key + "2", "name": "Стандарт", "price_client": 500,
                           "placement_type": {"name": "Двухместное", "sleeping_place": "2"}}]}

    def test_coverage_structured_then_web_deduplicates_and_accepts_guest_house(self):
        destination = {"city": "Калининград", "countryCode": "RU", "latitude": 54.71, "longitude": 20.51}
        self.provider.russ = [self.russ_row("10", "Гостиница Янтарь", destination, "Лесная улица, 3", 5900)]
        self.provider.city = destination["city"]
        names = ("Гостиница Янтарь", "Гостевой дом Лесной")
        addresses = ("Лесная улица, 3", "Лесная улица, 5")
        self.provider.pages = lambda: [
            {"url": f"https://lodging.example.test/{i}", "title": name,
             "content": f"{name}\nКалининград\n{addr}\nОдноместный номер для 1 гостя, 6 100 ₽ за сутки"}
            for i, (name, addr) in enumerate(zip(names, addresses))]
        def extract(data):
            result = []
            for p in data["pages"]:
                name = p["heading"]
                quote = lambda value: {"source": p["id"], "quote": value}
                result.append({"name": name, "identity": quote(name), "city": quote("Калининград"),
                               "address": quote(addresses[names.index(name)]),
                               "rates": [{**quote("Одноместный номер для 1 гостя, 6 100 ₽ за сутки"),
                                          "amount": "6100", "currency": "RUB", "basis": "room_night", "kind": "published"}]})
            return result
        self.provider.extraction = extract
        trip = {**recommendation()["trip"], "destination": destination, "endDate": "2027-05-18", "travelers": 2}
        body = recommendation(count=2, trip=trip, maxTotalRub=None)
        batch = self.hotels(body, portal=True)
        ids = [item["objectId"] for item in batch["items"]]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(self.diagnostics(body)["considered"], 2)
        self.assertEqual(set(item["name"] for item in batch["items"]), set(names))
        guest = next(item for item in batch["items"] if item["name"] == names[1])
        self.assertEqual(guest["price"], 36600)
        self.assertEqual(self.hotels({**body, "taskId": uuid4().hex, "excludedObjectIds": ids})["items"], [])

    def test_coverage_kirov_rejects_other_region_and_keeps_geographic_candidate(self):
        destination = {"city": "Киров", "countryCode": "RU", "latitude": 54.07429, "longitude": 34.30260}
        other = {**destination, "latitude": 58.60357, "longitude": 49.66662}
        self.provider.city = "Киров"
        self.provider.russ = [self.russ_row("10", "Гостиница Чужая", other, "Кировская область, Ленина 1", 100)]
        self.provider.geo = [{"properties": {"name": "Гостиница Советская", "place_id": "local",
            "categories": ["accommodation.hotel"], "city": "Киров", "state": "Калужская область", "country_code": "ru",
            "formatted": "Калужская область, Киров, Ленина 5", "lat": 54.07429, "lon": 34.30260}}]
        self.provider.pages = lambda: [{"url": "https://lodging.example.test/kirov-kirov-oblast",
                                        "title": "Гостиница Чужая", "content": "Кировская область"}]
        body = recommendation(count=2, maxTotalRub=None, trip={**recommendation()["trip"], "destination": destination})
        batch = self.hotels(body, portal=True)
        self.assertEqual(batch["items"], [])
        report = self.diagnostics(body)
        self.assertEqual(report["considered"], 1)
        self.assertEqual(report["discoverySources"]["geoapify"], 1)
        self.assertEqual(report["rejected"][0]["reason"], "missing_rate")
        self.assertIn("region_mismatch", {row["reason"] for row in report["sourceIssues"]})
        self.assertTrue(all("Калужская область" in query for query in self.provider.queries))
        self.assertEqual(report["calls"]["fetch"], 0)

    def test_coverage_abu_dhabi_web_fallback_two_currencies_and_unproven_charge(self):
        self.provider.geo = None
        self.provider.city = "Абу-Даби"
        names = ("Corniche Hotel", "Harbour Hotel", "Bridge Hostel", "Bay Hotel")
        self.provider.names = names
        quotes = ("Single room for 1 adult | 240 AED per room per night",
                  "Single room for 1 adult | US$45 per room per night",
                  "Single room for 1 adult | $25 per room per night",
                  "Single room for 1 adult | 190 AED per room per night, taxes not included")
        self.provider.price_line = lambda name: quotes[names.index(name)]
        def extract(data):
            rows = []
            for p in data["pages"]:
                index = names.index(p["heading"])
                cite = lambda quote: {"source": p["id"], "quote": quote}
                amount, currency = (("240", "AED"), ("45", "USD"), ("25", "USD"), ("190", "AED"))[index]
                rows.append({"name": p["heading"], "identity": cite(p["heading"]), "city": cite("Абу-Даби"),
                             "rates": [{**cite(quotes[index]), "amount": amount, "currency": currency,
                                        "basis": "room_night", "kind": "published"}]})
            return rows
        self.provider.extraction = extract
        dest = {"city": "Абу-Даби", "countryCode": "AE", "latitude": 24.45, "longitude": 54.37}
        body = recommendation(count=2, maxTotalRub=None, trip={**recommendation()["trip"], "destination": dest,
                                                               "endDate": "2027-05-18", "travelers": 2})
        self.assertEqual({i["name"]: i["price"] for i in self.hotels(body, portal=True)["items"]},
                         {names[0]: 36000, names[1]: 24300})
        report = self.diagnostics(body)
        self.assertEqual(report["sourceStatus"]["geoapify"], "places_unavailable")
        self.assertEqual(report["newWebObjects"], 4)
        self.assertTrue({"unverified_amount", "rate_restriction"} <= {r["reason"] for r in report["sourceIssues"]})

    def test_coverage_foreign_city_and_missing_places_still_search_web(self):
        self.provider.city = "Istanbul"
        self.provider.pages = lambda: [{"url": "https://lodging.example.test/istanbul",
                                        "title": "Istanbul Hotel", "content": "Istanbul Hotel, Türkiye"}]
        app.state.tasks.hotel_profile = "B"
        dest = {"city": "Константинополь", "countryCode": "UA", "latitude": 47.88, "longitude": 37.04}
        body = recommendation(count=2, trip={**recommendation()["trip"], "destination": dest})
        result = self.hotels(body, portal=True)
        self.assertEqual((result["status"], result["items"], result["hasMore"]), ("succeeded", [], None))
        report = self.diagnostics(body)
        self.assertGreater(report["calls"]["search"], 0)
        self.assertEqual(report["calls"]["fetch"], 0)
        self.assertEqual(report["considered"], 0)
        self.assertFalse(report["usedExtension"])
        self.assertIn("city_mismatch", {row["reason"] for row in report["sourceIssues"]})

    def test_coverage_supplier_anomaly_needs_corroboration(self):
        dest = {"city": "Калининград", "countryCode": "RU", "latitude": 54.71, "longitude": 20.51}
        self.provider.russ = [self.russ_row(str(i), f"Отель {i}", dest, f"Лесная улица, {i}", price)
                              for i, price in enumerate((3500, 4900), start=1)]
        sample = self.provider.russ[0]["rooms"][0]
        self.provider.russ[0]["rooms"].append({**sample, "id": "90", "price_client": 10})
        self.provider.russ[1]["rooms"].append({**sample, "id": "91", "price_client": 2500, "name": "Два номера стандарт"})
        body = recommendation(count=2, maxTotalRub=None, trip={**recommendation()["trip"], "destination": dest})
        result = self.hotels(body)
        self.assertEqual(sorted(item["price"] for item in result["items"]), [21000, 29400])
        self.assertIn("supplier_price_needs_confirmation", {row["reason"] for row in self.diagnostics(body)["sourceIssues"]})

    def test_coverage_extra_flash_only_for_useful_seventh_call(self):
        self.provider.names = ("One Hotel", "Second Hotel", "Third Hotel", "Fourth Hotel", "Fifth Hotel", "Sixth Hotel")
        self.provider.truncate_at = 2
        pages = self.provider.pages
        self.provider.pages = lambda: [{**row, "content": row["content"].replace("8,000 RUB", "88,000 RUB")}
                                         if index in (1, 2, 4, 5) else row for index, row in enumerate(pages())]
        body = recommendation(count=2)
        partial = self.hotels(body)
        self.assertEqual((partial["status"], len(partial["items"])), ("partial", 1))
        self.assertEqual(self.diagnostics(body)["calls"]["flash"], 6)
        # New destination snapshot, identical evidence and limits at the provider boundary.
        app.state.tasks.hotel_profile = "B"
        self.provider.city = "Osaka"
        trip = {**body["trip"], "destination": {"city": "Осака", "countryCode": "JP", "latitude": 34.69, "longitude": 135.50}}
        extended = recommendation(count=2, trip=trip)
        full = self.hotels(extended)
        self.assertEqual((full["status"], len(full["items"])), ("succeeded", 2))
        report = self.diagnostics(extended)
        self.assertTrue(report["usedExtension"])
        self.assertEqual(report["calls"]["flash"], 7)
        self.assertIn("length", {attempt["finish_reason"] for attempt in report["attempts"]})
        self.assertEqual(self.hotels(extended), full)

    def test_second_review_amount_is_not_chosen_by_the_model(self):
        self.provider.names = NAMES[:1]
        self.provider.rate_overrides["amount"] = "8.000"
        self.assertEqual(self.hotels(recommendation(maxTotalRub=50))["items"], [])
        self.provider.rate_overrides["amount"] = "8000"
        self.assertEqual(self.hotels(recommendation(maxTotalRub=48000))["items"][0]["price"], 48000)
        self.assertEqual(self.hotels(recommendation(maxTotalRub=47999))["items"], [])

    def test_second_review_hayal_original_citations_and_observation(self):
        heading = "Официальные цены на номера отеля «Хаял» г. Казань"
        city = "Отель «Хаял» расположен в самом сердце исторической части города, на тихой улице университетская"
        rates = ["Стоимость номера от 8 500 руб. / сутки", "Стоимость номера от 7 500 руб. / сутки"]
        page = {"url": "https://hotels.example.test/hayal", "title": heading, "content":
                f"{heading}\n{city}\n## Одноместный «Стандарт»\n{rates[0]}\n"
                f"Самая выгодная цена на 14 ноября 2026\n[…]\n## Одноместный Джуниор\n{rates[1]}"}
        self.provider.pages = lambda: [page]
        self.provider.extraction = lambda data: [{"name": "Отель «Хаял»", "identity": {"source": 1, "quote": heading},
            "city": {"source": 1, "quote": city}, "address": {"source": 1, "quote": "улице университетская"},
            "rates": [{"source": 1, "quote": line, "amount": amount, "basis": "room_night", "currency": "RUB",
                       "kind": "from", "support": [room]}
                      for line, amount, room in zip(rates, ("8500", "7500"), ("Одноместный «Стандарт»", "Одноместный Джуниор"))]}]
        body = recommendation(maxTotalRub=None, trip={**recommendation()["trip"], "destination": {
            "city": "Казань", "countryCode": "RU", "latitude": 55.79, "longitude": 49.12},
            "startDate": "2026-12-01", "endDate": "2026-12-04", "travelers": 2})
        batch = self.hotels(body, portal=True)
        self.assertEqual([item["price"] for item in batch["items"]], [45000])
        self.assertEqual(self.diagnostics(body)["hotels"][0]["price"]["rate"]["sourceUrl"], page["url"])
        store = app.state.tasks
        def rates_in_catalog():
            row = store.connection.execute("SELECT data FROM hotel_catalog").fetchone()
            return {rate["amount"]: rate for rate in json.loads(row[0])["rates"].values()}
        self.assertEqual(self.client.portal.call(rates_in_catalog)["8500"]["observedOn"], "2026-11-14")
        longer = recommendation(maxTotalRub=60000, trip={**body["trip"], "endDate": "2026-12-05"})
        self.assertEqual([item["price"] for item in self.hotels(longer, portal=True)["items"]], [60000])
        report = self.diagnostics(longer)
        self.assertEqual(report["hotels"][0]["availability"]["state"], "unknown")
        self.assertEqual(sum(report["calls"].values()), 0)

    def test_second_review_mir_linked_single_room_and_explicit_usd(self):
        name, room, price = "Hotel Mir Kyiv", "### Standard Single Room", "From US$25 / night"
        title = f"{name}: 3 star Hotel with a Minimum Price 852UAH| UPDATED FOR 2026 | best-hotels-kiev.com"
        page = {"url": "https://hotels.example.test/mir", "title": title, "content":
                f"{title}\n{room}\n- 1 max\n- 1 Single bed\n- View\n- Private bathroom\n- 18 m²\n{price}"}
        self.provider.pages = lambda: [page]
        self.provider.extraction = lambda data: [{"name": name, "identity": {"source": 1, "quote": title},
            "city": {"source": 1, "quote": title}, "rates": [{"source": 1, "quote": f"{room}\n{price}",
              "support": ["Standard Single Room", "1 max"], "amount": "25", "currency": "USD",
              "basis": "room_night", "kind": "from"}]}]
        trip = {**recommendation()["trip"], "destination": {
            "city": "Київ", "countryCode": "UA", "latitude": 50.45, "longitude": 30.52},
            "startDate": "2026-12-01", "endDate": "2026-12-04", "travelers": 2}
        original = page["content"]
        page["content"] = original.replace(price, f"### Standard Double Room\n- 2 max\n{price}")
        wrong_room = recommendation(maxTotalRub=None, trip=trip)
        self.assertEqual(self.hotels(wrong_room, portal=True)["items"], [])
        price = "From $25 / night"
        page["content"] = original.replace("US$", "$")
        ambiguous_currency = recommendation(maxTotalRub=None, trip={**trip, "budgetRub": 86000})
        self.assertEqual(self.hotels(ambiguous_currency, portal=True)["items"], [])
        page["content"], price = original, "From US$25 / night"
        body = recommendation(maxTotalRub=None, trip={**trip, "budgetRub": 87000})
        self.assertEqual([item["price"] for item in self.hotels(body, portal=True)["items"]], [13500])
        price_details = self.diagnostics(body)["hotels"][0]["price"]
        self.assertEqual((price_details["rate"]["currency"], price_details["exchange"]["valueRub"],
                          price_details["rate"]["quote"]), ("USD", "90", price))

    def test_second_review_wrong_time_even_when_flash_confirms(self):
        for index, (topic, evidence) in enumerate([
            ("Завтрак до 07:00", "Ресепшен работает круглосуточно, завтрак с 09:00"),
            ("Заезд в 01:30", "Заселение в 01:30 невозможно"),
        ]):
            destination = KYOTO if index == 0 else {
                "city": "Осака", "countryCode": "JP", "latitude": 34.69, "longitude": 135.50}
            self.provider.city = "Kyoto" if index == 0 else "Osaka"
            for role in ("preferred", "required"):
                self.provider.facts[index] = evidence
                self.model = lambda _: completion({"conditions": [{"scope": "hotels", "role": role,
                    "meaning": topic, "quote": topic, "ambiguous": False}]})
                text = topic + (" желательно" if role == "preferred" else "")
                body = recommendation(trip={**recommendation()["trip"], "destination": destination,
                    "preferences": text, "budgetRub": 85000 + index * 2 + (role == "preferred")})
                batch = self.hotels(body, portal=True)
                self.assertEqual(bool(batch["items"]), role == "preferred")
                if batch["items"]:
                    proof = self.diagnostics(body)["hotels"][0]["conditions"][0]
                    self.assertEqual((proof["verdict"], proof["evidence"][0]["quote"]), ("refuted", evidence))

    def test_second_review_availability_rank_does_not_follow_price_dates(self):
        original = self.provider.pages
        dates = "2027-05-15 — 2027-05-17"
        phrases = [f"{dates}: 3 single rooms available", f"{dates}: not sold out", f"{dates}: no rooms available"]
        def pages():
            return [{**row, "content": row["content"] + "\n" + phrase}
                    for row, phrase in zip(original(), phrases)]
        self.provider.pages = pages
        def pick(data):
            found = []
            for page in data["pages"]:
                name, source = page["heading"], page["id"]
                index = NAMES.index(name)
                cite = lambda quote: {"source": source, "quote": quote}
                found.append({"name": name, "identity": cite(name), "city": cite("Kyoto"),
                    "availability": [cite(phrases[index])] if phrases[index] else [],
                    "rates": [{**cite(self.provider.price_line(name)), "amount": "8000",
                               "basis": "room_night", "currency": "RUB", "kind": "published"}]})
            return found
        self.provider.extraction = pick
        body = recommendation(count=3)
        self.assertEqual([item["name"] for item in self.hotels(body)["items"]], list(NAMES))
        self.assertEqual([hotel["availability"]["state"] for hotel in self.diagnostics(body)["hotels"]],
                         ["available", "unknown", "unavailable"])
        later = recommendation(count=3, trip={**body["trip"], "startDate": "2027-05-16", "endDate": "2027-05-18"})
        self.assertEqual([item["price"] for item in self.hotels(later)["items"]], [48000] * 3)
        self.assertTrue(all(hotel["availability"]["state"] == "unknown" for hotel in self.diagnostics(later)["hotels"]))
        self.assertEqual(self.diagnostics(later)["calls"]["search"], 0)
        longer = recommendation(count=3, maxTotalRub=95999,
            trip={**body["trip"], "endDate": "2027-05-19"})
        self.assertEqual(self.hotels(longer)["items"], [])
        self.assertEqual(self.diagnostics(longer)["overCeiling"], 3)

    def test_second_review_legacy_grand_hotel_duplicates_share_exclusions(self):
        self.provider.names = ("Grand Hotel Kazan",)
        self.provider.city = "Kazan"
        first_address = "Peterburgskaia Street, 1, Kazan, Republic of Tatarstan, 420107"
        alternate = "Kazan, st Peterburg 1"
        original_pages = self.provider.pages
        self.provider.pages = lambda: [{**page, "content": page["content"].replace(
            "1 Gion Street, Kazan", first_address)} for page in original_pages()]
        def extract(data):
            page = data["pages"][0]
            quote = lambda text: {"source": page["id"], "quote": text}
            return [{"name": self.provider.names[0], "identity": quote(self.provider.names[0]),
                     "city": quote(first_address), "address": quote(first_address),
                     "rates": [{**quote(self.provider.price_line(self.provider.names[0])), "amount": "8000",
                                "currency": "RUB", "basis": "room_night", "kind": "published"}]}]
        self.provider.extraction = extract
        body = recommendation(trip={**recommendation()["trip"], "destination": {
            "city": "Казань", "countryCode": "RU", "latitude": 55.79, "longitude": 49.12}})
        historical = self.hotels(body)
        first_id = historical["items"][0]["objectId"]
        duplicate_id = "hotel-z-legacy-duplicate"
        branch_id = "hotel-z-other-building"
        catalog = app.state.tasks.hotels

        def load_legacy_rows():
            city_id, original = catalog.db.execute(
                "SELECT city_id, data FROM hotel_catalog WHERE object_id = ?", (first_id,)).fetchone()
            saved = json.loads(original)
            for object_id, address in ((duplicate_id, alternate), (branch_id, "Kazan, st Peterburg 2")):
                catalog.db.execute("INSERT INTO hotel_catalog VALUES (?, ?, ?)",
                                   (city_id, object_id, encode({**saved, "address": address})))
            self.assertEqual(set(catalog.snapshot(city_id, [])), {first_id, branch_id})
            self.assertEqual(set(catalog.snapshot(city_id, [duplicate_id])), {branch_id})
            another_source = {**saved["identity"], "sourceUrl": "https://hotels.example.test/grand-kazan"}
            match, _ = catalog.store("RU", city_id, {**saved, "address": alternate, "identity": another_source})
            self.assertEqual(match, first_id)

        self.client.portal.call(load_legacy_rows)
        later = {**body, "taskId": uuid4().hex, "excludedObjectIds": [duplicate_id]}
        self.assertEqual([item["objectId"] for item in self.hotels(later)["items"]], [branch_id])
        self.assertEqual(self.hotels(body), historical)

    def test_second_review_cached_false_amount_is_unusable_for_direct_or_analog_price(self):
        self.provider.names = NAMES[:1]
        first = recommendation()
        historical = self.hotels(first)
        self.assertEqual(historical["items"][0]["price"], 48000)
        catalog = app.state.tasks.hotels

        def old_rate():
            object_id, data = catalog.db.execute("SELECT object_id, data FROM hotel_catalog").fetchone()
            hotel = json.loads(data)
            for rate in hotel["rates"].values():
                rate.pop("printedAmount")
                rate["amount"] = "8.000"
                trip = RecommendationsRequest.model_validate(first).trip
                self.assertIsNone(rate_quality(rate, trip, 2))
            catalog.db.execute("UPDATE hotel_catalog SET data = ? WHERE object_id = ?", (encode(hotel), object_id))

        self.client.portal.call(old_rate)
        self.provider.names = ()
        second = recommendation(maxTotalRub=50)
        self.assertEqual(self.hotels(second)["items"], [])
        self.assertEqual(self.diagnostics(second)["priced"], 0)
        self.assertEqual(self.hotels(first), historical)

    def test_cold_and_warm_price_reuse_with_exclusions_and_browser_task(self):
        body = recommendation()
        result = self.hotels(body)
        self.assertEqual((result["status"], result["hasMore"]), ("succeeded", True))
        hotel = result["items"][0]
        self.assertEqual(hotel["price"], 48_000)
        self.assertIsNone(hotel["coordinates"])
        self.assertIsNone(hotel["imageUrl"])
        self.assertTrue(hotel["sourceUrl"].startswith("https://"))
        proof = self.diagnostics(body)
        self.assertEqual(proof["calls"], {"search": 1, "fetch": 2, "flash": 2, "fx": 0})
        self.assertEqual(proof["usage"]["totalTokens"], 400)
        self.assertEqual(proof["hotels"][0]["price"]["rate"]["amount"], "8000")
        self.assertIn("per night", proof["hotels"][0]["price"]["rate"]["quote"])
        self.assertEqual(self.client.get(DETAILS + body["taskId"]).json()["hotels"], proof)

        before = len(self.provider.calls)
        changed = recommendation(trip={**body["trip"], "startDate": "2027-05-21", "endDate": "2027-05-23", "travelers": 2})
        warmer = self.hotels(changed, portal=True)
        self.assertEqual(warmer["items"][0]["objectId"], hotel["objectId"])
        self.assertEqual(warmer["items"][0]["price"], 32_000)
        self.assertEqual(self.diagnostics(changed)["catalogMatches"], 3)
        self.assertEqual(len(self.provider.calls), before)

        rejected = self.hotels(recommendation(maxTotalRub=47999))
        self.assertEqual((rejected["status"], rejected["items"], rejected["hasMore"]), ("succeeded", [], False))
        excluded = self.hotels(recommendation(excludedObjectIds=[hotel["objectId"]]))
        self.assertNotEqual(excluded["items"][0]["objectId"], hotel["objectId"])
        estimate = dict(taskId=uuid4().hex, trip=body["trip"], selectedHotel={"objectId": hotel["objectId"], "price": hotel["price"]},
                        selectedAttractions=[])
        self.assertEqual(self.submit(estimate, portal=True, path="budget")["status"], "succeeded")

    def test_city_validation_and_autocomplete(self):
        response = self.client.get(BUILDER + "/cities", params={"q": "Спрингфилд"})
        cities = response.json()["items"]
        self.assertEqual(len(cities), 2)
        self.assertEqual(cities[0]["latitude"], 0)
        self.assertNotEqual(cities[0]["label"], cities[1]["label"])
        self.assertEqual(self.client.get(BUILDER + "/cities").json()["status"], "empty")
        app.state.geoapify_key = ""
        self.assertEqual(self.client.get(BUILDER + "/cities?q=Kyoto").json()["status"], "unconfigured")

        old = {"destinationId": "ru-moscow"}
        bad = ({"destinationId": "bad"}, {"destination": {**KYOTO, "longitude": 181}},
               {"destination": {**KYOTO, "latitude": "35"}}, {"destination": {**KYOTO, "latitude": False}},
               {"destination": {**KYOTO, "city": "  "}}, {"destination": {"city": "Киото"}},
               {"destination": KYOTO, **old}, {})
        base = recommendation(targets="attractions")
        trip = {key: value for key, value in base["trip"].items() if key != "destination"}
        for geographic in bad:
            with self.subTest(geographic=geographic):
                body = dict(base, trip={**trip, **geographic})
                for prefix in (BUILDER, "/v1"):
                    self.assertEqual(self.client.post(prefix + "/recommendations", json=body, headers=self.headers).status_code, 422)
        body = recommendation(targets="attractions", trip={**trip, "destination": {**KYOTO, "city": " Киото ", "countryCode": "jp"}})
        report = self.submit(body)
        self.assertTrue(report["results"]["attractions"]["items"])
        self.assertEqual(self.submit(dict(body, trip={**trip, "destination": KYOTO})), report)
        body = recommendation(targets="attractions", trip={**trip, **old})
        self.assertTrue(self.submit(body)["results"]["attractions"]["items"])

    def test_historical_payload_matches_without_new_destination_field(self):
        body = recommendation()
        body["trip"].pop("destination")
        body["trip"]["destinationId"] = "ru-moscow"
        stored = {"taskId": body["taskId"], "event": "recommendations.finished", "results": {"hotels": {
            "items": [{"objectId": "historical", "price": None}], "status": "succeeded", "hasMore": None}}}
        store = app.state.tasks
        self.client.portal.call(store.connection.execute, """
            INSERT INTO tasks (client_id, task_id, operation, payload, result, created_at) VALUES (?, ?, ?, ?, ?, ?)
        """, (self.owner_id, body["taskId"], "recommendations", json.dumps(body), json.dumps(stored), 0))
        self.assertEqual(self.submit(body), stored)
        self.assertEqual(self.provider.calls, [])
        changed = dict(body, trip={**body["trip"], "travelers": 4})
        self.assertEqual(self.client.post("/v1/recommendations", json=changed, headers=self.headers).status_code, 409)

    def test_validation_of_identity_quote_currency_and_single_occupancy(self):
        self.provider.names = NAMES[:1]
        self.provider.bad_quote = True
        self.assertEqual(self.hotels(recommendation())["items"], [])
        self.provider.bad_quote = False
        self.provider.foreign_city = True
        self.assertEqual(self.hotels(recommendation())["items"], [])
        self.provider.foreign_city = False
        for quote in ("From 20,000 RUB, single room nightly", "Double occupancy: 8,000 RUB per night (2 adults)",
                      "Single-night stay: 8,000 RUB per night",
                      "Single room for 1 adult for 8,000 nights | 10,000 RUB per night", "Price on request"):
            with self.subTest(quote=quote):
                self.provider.rate_text = quote
                self.assertEqual(self.hotels(recommendation())["items"], [])
        self.assertEqual(source_url("https://example.test/hotel?room=1&utm_campaign=test&date=2027-05-15#map"),
                         "https://example.test/hotel?date=2027-05-15&room=1")

    def test_required_time_excluded_feature_and_removed_condition(self):
        requirement = "Нужен завтрак до 7:00"
        refinement = "Завтрак больше не нужен"
        self.provider.names = NAMES[:1]
        self.provider.facts[0] = "Breakfast served Saturday from 06:00 to 09:00."
        self.model = lambda data: completion({"changes": [{"index": 0, "quote": refinement, "replacement": None}], "additions": []}
            if "refinement" in data else {"conditions": [{"scope": "hotels", "role": "required", "meaning": requirement,
                                                         "quote": requirement, "ambiguous": False}]})
        body = recommendation()
        body["trip"]["preferences"] = requirement
        self.assertEqual(self.hotels(body)["items"], [])
        soft = dict(body, taskId=uuid4().hex, refinement=refinement)
        self.assertEqual(len(self.hotels(soft)["items"]), 1)
        record = self.client.get(DETAILS + soft["taskId"]).json()
        self.assertEqual(record["stages"][-1]["result"]["conditions"], [])
        self.assertEqual(record["hotels"]["hotels"][0]["conditions"], [])

        exclusion = "Курение запрещено"
        self.model = lambda data: completion({"conditions": [{"scope": "hotels", "role": "excluded", "meaning": exclusion,
                                                             "quote": exclusion, "ambiguous": False}]})
        new = recommendation(trip={**body["trip"], "preferences": exclusion})
        self.assertEqual(len(self.hotels(new)["items"]), 1)
        self.assertEqual(self.diagnostics(new)["hotels"][0]["conditions"][0]["verdict"], "confirmed")

    def test_late_arrival_has_verified_proof(self):
        after_midnight = "Обязателен заезд после полуночи"
        self.model = lambda _: completion({"conditions": [{"scope": "hotels", "role": "required",
            "meaning": after_midnight, "quote": after_midnight, "ambiguous": False}]})
        self.provider.names = NAMES[:1]
        self.provider.facts[1] = "Front desk open 07:00–23:00."
        body = recommendation()
        body["trip"]["preferences"] = after_midnight
        self.assertEqual(self.hotels(body)["items"], [])
        self.provider.facts[1] = CHECK_IN
        body = dict(body, taskId=uuid4().hex, trip={**body["trip"], "budgetRub": 100_001})
        self.assertTrue(self.hotels(body)["items"])
        check = self.diagnostics(body)["hotels"][0]["conditions"][0]
        self.assertEqual(check["evidence"][0]["quote"], CHECK_IN)
        self.assertEqual(check["verdict"], "confirmed")

    def test_currency_nominal_rounding_and_zero_nights(self):
        self.provider.currency = "JPY"
        body = recommendation()
        found = self.hotels(body)["items"][0]
        self.assertEqual(found["price"], 37844)
        report = self.diagnostics(body)
        self.assertEqual(report["hotels"][0]["price"]["exchange"]["nominal"], 100)
        self.assertEqual(report["calls"]["fx"], 1)
        before = len(self.provider.calls)
        self.assertEqual(self.hotels(recommendation())["items"][0]["price"], found["price"])
        self.assertEqual(len(self.provider.calls), before)
        same_date = recommendation(trip={**body["trip"], "endDate": body["trip"]["startDate"], "preferences": "Обязателен Wi-Fi"})
        self.assertEqual(self.hotels(same_date), {"items": [], "status": "succeeded", "hasMore": False})
        self.assertEqual(len(self.provider.calls), before)

    def test_review_russian_single_room_has_proven_price(self):
        self.provider.names = NAMES[:1]
        self.provider.rate_overrides["amount"] = "2100"
        for line in ("Одноместный номер — 2 100 ₽ за 1 ночь",
                     "Отдельный номер для 1 гостя — 2 100 ₽ за ночь, без питания, оплата не возвращается"):
            self.provider.rate_text = line
            body = recommendation(count=2)
            body["trip"].update(travelers=2, endDate="2027-05-18")
            self.assertEqual(self.hotels(body)["items"][0]["price"], 12600)

    def test_review_split_offer_and_rate_policy(self):
        self.provider.names = NAMES[:1]
        room, price, unit = "### Отдельный номер для 1 гостя", "2 100 ₽", "за 1 ночь"
        self.provider.rate_text = (
            f"{room}\nБез питания\nОплата не возвращается\n{price}\n{unit}\n"
            "Включён завтрак\n2 500 ₽\nза 1 ночь"
        )
        self.provider.rate_overrides.update(amount="2100", quote=price, support=[room, unit],
                                           caveat="Без питания, оплата не возвращается")
        body = recommendation()
        found = self.hotels(body)["items"][0]
        price_proof = self.diagnostics(body)["hotels"][0]["price"]["rate"]
        self.assertEqual(set(price_proof["policies"]), {"no_meals", "nonrefundable"})
        self.assertEqual(price_proof["support"], [room, unit])
        self.assertEqual(found["price"], 12600)

        topic = "Завтрак включён в стоимость"
        self.model = lambda _: completion({"conditions": [{"scope": "hotels", "role": "required",
            "meaning": topic, "quote": topic, "ambiguous": False}]})
        self.provider.facts[0] = "Завтрак включён в стоимость во всех тарифах."
        request = recommendation()
        request["trip"]["preferences"] = topic
        self.assertEqual(self.hotels(request)["items"], [])

    def test_review_block_cannot_merge_neighboring_tariffs_or_ellipses(self):
        self.provider.names = NAMES[:1]
        room, price, unit = "### Одноместный номер", "2 100 ₽", "за 1 ночь"
        self.provider.rate_text = (
            f"{room}\nНет свободных номеров\n### Двухместный номер\n{price}\n{unit}"
        )
        self.provider.rate_overrides.update(amount="2100", quote=price, support=[room, unit])
        body = recommendation()
        self.assertEqual(self.hotels(body)["items"], [])
        self.assertIn("unlinked_rate_quotes", {issue["reason"] for issue in self.diagnostics(body)["sourceIssues"]})
        self.provider.rate_overrides.update(quote=room + " ... " + price, support=[])
        body = recommendation(maxTotalRub=None)
        self.assertEqual(self.hotels(body)["items"], [])
        self.assertIn("missing_rate_quote", {issue["reason"] for issue in self.diagnostics(body)["sourceIssues"]})

    def test_review_dated_offer_is_marked_when_used_as_an_estimate(self):
        self.provider.names = NAMES[:1]
        self.provider.rate_text = "Одноместный номер 4 310 ₽ за ночь"
        self.provider.rate_overrides["amount"] = "4310"
        original_pages = self.provider.pages

        def dated_pages():
            return [{**page, "url": page["url"] + "?checkin=2026-11-06&checkout=2026-11-09",
                     "content": "Цены на выбранный период 06.11.2026 — 09.11.2026\n" + page["content"]}
                    for page in original_pages()]

        self.provider.pages = dated_pages
        november = recommendation()
        november["trip"].update(startDate="2026-11-06", endDate="2026-11-09", travelers=2)
        self.assertEqual(self.hotels(november)["items"][0]["price"], 25860)
        december = recommendation(trip={**november["trip"], "startDate": "2026-12-01", "endDate": "2026-12-04"})
        self.assertEqual([item["price"] for item in self.hotels(december)["items"]], [25860])
        quote = self.diagnostics(december)["hotels"][0]
        self.assertEqual(quote["price"]["basis"], "other_period")
        self.assertEqual(quote["availability"]["state"], "unknown")

    def test_review_old_rate_needs_rechecking_and_keeps_id(self):
        self.provider.names = NAMES[:1]
        original = self.hotels(recommendation())["items"][0]
        store = app.state.tasks

        def erase_scope():
            db = store.connection
            hotel = json.loads(db.execute("SELECT data FROM hotel_catalog WHERE object_id = ?", (original["objectId"],)).fetchone()[0])
            for rate in hotel["rates"].values():
                rate.pop("scope")
            db.execute("UPDATE hotel_catalog SET data = ? WHERE object_id = ?", (encode(hotel), original["objectId"]))

        self.client.portal.call(erase_scope)
        before = len(self.provider.calls)
        new = recommendation(maxTotalRub=None)
        self.assertEqual(self.hotels(new)["items"][0]["objectId"], original["objectId"])
        self.assertGreater(len(self.provider.calls), before)
        self.assertEqual(self.diagnostics(new)["catalogMatches"], 0)

    def test_review_adaptive_extraction_and_work_ledger(self):
        original_pages = self.provider.pages
        self.provider.names = NAMES[:2]
        self.provider.pages = lambda: [{**page, "content": page["content"] + "\n" + (
            "Подробнее: описание номера, завтрак, цены, условия бронирования.\n" * 120)}
            for page in original_pages()]
        body = recommendation(count=2)
        request = RecommendationsRequest.model_validate(body)
        sample = HotelSearch(None, None, True, request.trip.destination, request, [])
        sample.city_names.append("Kyoto")
        first = {**self.provider.pages()[0], "stored": False}
        one = sample.flash_data({1: sample.make_source(first, 420)})
        plan = {"destination": sample.destination.model_dump(), "conditions": [],
                "startDate": sample.dates[0], "endDate": sample.dates[1], "rooms": 3}
        plan_bytes = len(encode(HotelTools.flash_body(PLAN, plan, 650)).encode("utf-8"))
        one_bytes = len(encode(HotelTools.flash_body(EXTRACT, one, 650)).encode("utf-8"))
        with patch("tripflow_api.hotel_tools.MAX_FLASH_BYTES", plan_bytes + one_bytes + 140):
            first_result = self.hotels(body)
        self.assertEqual((first_result["status"], first_result["hasMore"], len(first_result["items"])), ("partial", None, 1))
        stopped = self.diagnostics(body)
        self.assertEqual(stopped["stop"]["unit"], "input_bytes")
        self.assertEqual(stopped["calls"], {"search": 1, "fetch": 2, "flash": 2, "fx": 0})
        retry = dict(body, taskId=uuid4().hex)
        full = self.hotels(retry)
        self.assertEqual(len(full["items"]), 2, self.diagnostics(retry).get("sourceIssues"))
        self.assertGreaterEqual(self.diagnostics(retry)["reusedCalls"]["search"], 1)
        self.assertEqual(self.diagnostics(body), stopped)
        warm = dict(body, taskId=uuid4().hex)
        self.assertEqual(self.hotels(warm)["items"], full["items"])
        self.assertEqual(sum(self.diagnostics(warm)["calls"].values()), 0)

    def test_review_petersburg_two_hotels_and_price_evidence(self):
        self.provider.names = ("Гостиница Лайт", "Отель Мэдоу")
        self.provider.city = "Санкт-Петербург"
        self.provider.street = "Невский проспект"
        self.provider.rate_text = "Включён завтрак\nОплата не возвращается\n2 100 ₽\nза 1 ночь"
        self.provider.rate_overrides.update(amount="2100", caveat="Включён завтрак, оплата не возвращается")
        topic = "Завтрак до 07:00"
        self.provider.facts[0] = "Завтрак с 06:30 ежедневно"
        self.model = lambda _: completion({"conditions": [{"scope": "hotels", "role": "required",
            "meaning": topic, "quote": topic, "ambiguous": False}]})
        body = recommendation(count=2, maxTotalRub=None, trip={
            "destination": {"city": "Санкт-Петербург", "countryCode": "RU",
                            "latitude": 59.938732, "longitude": 30.316229},
            "startDate": "2026-12-01", "endDate": "2026-12-04",
            "travelers": 2, "budgetRub": 85000, "preferences": topic,
        })
        self.assertEqual(self.hotels(body, portal=True)["items"], [])
        self.assertIn("unverified_occupancy", {issue["reason"] for issue in self.diagnostics(body)["sourceIssues"]})
        self.provider.rate_text = "### Одноместный номер\n" + self.provider.rate_text
        self.provider.rate_overrides.update(quote="2 100 ₽", support=["### Одноместный номер", "за 1 ночь"])
        # Changing the evidence set simulates the next search finding an additional source.
        body = dict(body, taskId=uuid4().hex, trip={**body["trip"], "preferences": topic + ". По возможности номер потише."})
        batch = self.hotels(body, portal=True)
        self.assertEqual([hotel["price"] for hotel in batch["items"]], [12600, 12600])
        for proof in self.diagnostics(body)["hotels"]:
            self.assertEqual(proof["conditions"][0]["verdict"], "confirmed")
            self.assertEqual(proof["price"]["rate"]["quote"], "2 100 ₽")
        repeat = dict(body, taskId=uuid4().hex)
        self.assertEqual(self.hotels(repeat)["items"], batch["items"])
        self.assertEqual(self.diagnostics(repeat)["calls"], {"search": 0, "fetch": 0, "flash": 0, "fx": 0})

    def test_review_budget_stops_before_useless_search_and_fetch(self):
        body = recommendation()
        request = RecommendationsRequest.model_validate(body)
        trip = request.trip
        plan = {"destination": trip.destination.model_dump(), "conditions": [], "startDate": trip.startDate.isoformat(),
                "endDate": trip.endDate.isoformat(), "rooms": 3}
        size = len(encode(HotelTools.flash_body(PLAN, plan, 650)).encode("utf-8"))
        with patch("tripflow_api.hotel_tools.MAX_FLASH_BYTES", size):
            batch = self.hotels(body)
        self.assertEqual((batch["status"], batch["items"], batch["hasMore"]), ("failed", [], None))
        report = self.diagnostics(body)
        self.assertEqual(report["calls"], {"search": 0, "fetch": 0, "flash": 1, "fx": 0})
        self.assertEqual(report["stop"]["unit"], "input_bytes")
        self.assertEqual(report["stop"]["used"], size)

    def test_review_truncated_response_retries_with_a_smaller_batch(self):
        self.provider.truncate_at = 3
        body = recommendation(count=2)
        result = self.hotels(body)
        self.assertEqual((result["status"], len(result["items"])), ("succeeded", 2))
        diagnostics = self.diagnostics(body)
        failed = [attempt for attempt in diagnostics["attempts"] if attempt["error"] == "flash_truncated"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["usage"]["outputTokens"], 80)
        self.assertFalse(failed[0]["retry"])
        self.assertEqual(diagnostics["calls"]["search"], 1)

    def test_review_same_city_in_a_foreign_country_is_rejected(self):
        self.provider.names = NAMES[:1]
        self.provider.city = "Paris, Texas, USA"
        trip = {**recommendation()["trip"], "destination": {
            "city": "Paris", "countryCode": "FR", "latitude": 48.8566, "longitude": 2.3522}}
        self.assertEqual(self.hotels(recommendation(trip=trip))["items"], [])
        self.provider.city = "Paris"
        self.assertEqual(self.hotels(recommendation(trip={**trip, "budgetRub": 100_001}))["items"], [])
        self.provider.city = "Paris, France"
        self.assertTrue(self.hotels(recommendation(trip={**trip, "budgetRub": 100_002}))["items"])
        self.assertTrue(self.hotels(recommendation(trip={**trip, "budgetRub": 100_002}))["items"])

    def test_review_timing_needs_the_right_service_and_interval(self):
        self.provider.names = NAMES[:1]
        for index, (topic, fact, good) in enumerate([
            ("Завтрак до 07:00", "24-hour reception", False),
            ("Заезд в 01:30", "Стойка регистрации с 07:00 до 23:00", False),
            ("Заезд в 01:30", "Заселение с 22:00 до 02:00", True),
            ("Завтрак до 07:00", "Завтрак с 06:30 ежедневно", True),
        ]):
            with self.subTest(topic=topic, fact=fact):
                self.provider.facts[0 if "Завтрак" in topic else 1] = fact
                self.model = lambda _: completion({"conditions": [{"scope": "hotels", "role": "required",
                    "meaning": topic, "quote": topic, "ambiguous": False}]})
                request = recommendation()
                request["trip"].update(preferences=topic, budgetRub=100_000 + index)
                self.assertEqual(bool(self.hotels(request)["items"]), good)

    def test_exhaustion_interruption_and_catalog_fallback(self):
        self.provider.names = ()
        self.assertEqual(self.hotels(recommendation()), {"items": [], "status": "succeeded", "hasMore": False})
        self.provider.outages = {"/v1/tools/search"}
        failed = self.hotels(recommendation(maxTotalRub=None))
        self.assertEqual((failed["status"], failed["items"], failed["hasMore"]), ("failed", [], None))

        self.provider.outages.clear()
        self.provider.names = NAMES[:1]
        self.provider.failed_after = self.provider.search_count + 1
        partial = self.hotels(recommendation(count=2))
        self.assertEqual((partial["status"], len(partial["items"]), partial["hasMore"]), ("partial", 1, None))
        self.assertTrue(partial["error"])
        warm = self.hotels(recommendation())
        self.assertEqual((warm["status"], warm["hasMore"]), ("succeeded", None))
        self.assertEqual(warm["items"], partial["items"])

    def test_parallel_and_lease_recovery(self):
        self.provider.names = NAMES[:1]
        first, second = recommendation(), recommendation()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.hotels, (first, second)))
        self.assertEqual(results[0]["items"], results[1]["items"])
        reports = [self.diagnostics(body) for body in (first, second)]
        self.assertEqual(sum(report["calls"]["search"] for report in reports), 1)
        self.assertEqual(sum(report["calls"]["flash"] for report in reports), 2)

        body = recommendation()
        store = app.state.tasks
        self.client.portal.call(store.accept, self.owner_id, "recommendations", RecommendationsRequest.model_validate(body))
        identity = (self.owner_id, body["taskId"])

        async def seed_expired_worker():
            lease = "expired-worker"
            self.assertIsNotNone(store.claim_hotels(identity, lease))
            tools = HotelTools(store.connection, store.provider, store.external, identity, lease)
            await tools.search("unused recovery checkpoint")
            store.connection.execute("UPDATE hotel_worker_slots SET expires_at = 0 WHERE lease = ?", (lease,))
            store.connection.execute("UPDATE tasks SET hotel_expires_at = 0 WHERE client_id = ? AND task_id = ?", identity)

        self.client.portal.call(seed_expired_worker)
        call_count = len(self.provider.calls)
        self.client.portal.call(store.run, *identity)
        self.assertEqual(self.hotels(body)["items"], results[0]["items"])
        self.assertEqual(len(self.provider.calls), call_count)
        self.assertEqual(self.diagnostics(body)["calls"]["search"], 1)

    def test_validation_replays_priced_search_when_fetch_has_no_prices(self):
        name, other = NAMES[:2]
        self.provider.names = (name, other)
        price_line = self.provider.price_line(name)
        self.provider.price_line = lambda hotel: price_line if hotel == name else "Contact us for prices"
        page_url = self.provider.pages()[0]["url"]
        self.provider.fetch_content[page_url] = f"{name}\n1 Gion Street, Kyoto\nContact us for prices"
        self.provider.extraction = lambda data: []
        body = recommendation()
        self.assertEqual(self.hotels(body)["items"], [])

        def extract(data):
            self.assertEqual([page["heading"] for page in data["pages"]], [name])
            sid = data["pages"][0]["id"]
            return [{"name": name, "identity": {"source": sid, "quote": name},
                     "city": {"source": sid, "quote": "Kyoto"},
                     "rates": [{"source": sid, "quote": price_line, "amount": "8000", "currency": "RUB",
                                "basis": "room_night", "kind": "published"}]}]

        self.provider.extraction = extract
        second = {**body, "taskId": uuid4().hex}
        self.assertEqual([row["name"] for row in self.hotels(second)["items"]], [name])
        details = self.diagnostics(second)
        self.assertEqual([details["calls"][key] for key in ("search", "fetch")], [0, 0])
        self.assertEqual(details["hotels"][0]["price"]["rate"]["quote"], price_line)

    def test_cold_recovery_reuses_the_saved_search_response(self):
        self.provider.names = NAMES[:1]
        body = recommendation()
        store = app.state.tasks
        self.client.portal.call(store.accept, self.owner_id, "recommendations", RecommendationsRequest.model_validate(body))
        identity = (self.owner_id, body["taskId"])

        async def simulate_interruption():
            lease = "checkpoint-before-restart"
            self.assertIsNotNone(store.claim_hotels(identity, lease))
            tools = HotelTools(store.connection, store.provider, store.external, identity, lease)
            await tools.search("Kyoto hotels single room")
            payload = {"url": self.provider.pages()[0]["url"]}
            step = hashlib.sha256(encode(["fetch", payload]).encode()).hexdigest()
            store.connection.execute("""
                INSERT INTO hotel_attempts (client_id, task_id, attempt, kind, step, started_at, request_bytes,
                                           output_reserved) VALUES (?, ?, 2, 'fetch', ?, ?, 0, 0)
            """, (*identity, step, int(time.time())))
            store.connection.execute("UPDATE hotel_worker_slots SET expires_at = 0 WHERE lease = ?", (lease,))
            store.connection.execute("UPDATE tasks SET hotel_expires_at = 0 WHERE client_id = ? AND task_id = ?", identity)

        self.client.portal.call(simulate_interruption)
        self.client.portal.call(store.run, *identity)
        self.assertTrue(self.hotels(body)["items"])
        self.assertEqual(self.provider.search_count, 1)
        details = self.diagnostics(body)
        self.assertEqual(details["calls"]["fetch"], 2)
        self.assertTrue(details["retries"])
        stopped = next(attempt for attempt in details["attempts"] if attempt["error"] == "interrupted")
        self.assertIsNone(stopped["billable"])

    def test_aliases_and_forks(self):
        first = recommendation()
        self.provider.names = NAMES[:1]
        object_id = self.hotels(first)["items"][0]["objectId"]
        db = app.state.tasks
        city_id = next(iter(self.client.portal.call(db.connection.records, "SELECT id FROM hotel_destinations")))["id"]
        original = self.client.portal.call(db.hotels.snapshot, city_id, ())[object_id]
        variant = {**original, "name": "Hotel Kamo Garden", "address": "Kyoto, 1 Gion St.",
                   "identity": {**original["identity"], "sourceUrl": "https://second.example.test/property"}}
        found = self.client.portal.call(db.hotels.store, "JP", city_id, variant)
        self.assertEqual(found[0], object_id)
        branch = {**variant, "address": "Different branch, Kyoto",
                  "identity": {**original["identity"], "sourceUrl": "https://second.example.test/another-property"}}
        self.assertNotEqual(self.client.portal.call(db.hotels.store, "JP", city_id, branch)[0], object_id)

    def test_analogs_need_two_distinct_properties_and_survive_warm_search(self):
        base_price = self.provider.price_line
        self.provider.price_line = lambda name: "Call the hotel for rates" if name == NAMES[0] else base_price(name)
        self.provider.names = NAMES[:2]
        short = self.hotels(recommendation(count=2))
        self.assertEqual([item["name"] for item in short["items"]], [NAMES[1]])
        self.provider.names = NAMES
        body = recommendation(count=3)
        full = self.hotels(body)
        target = next(item for item in full["items"] if item["name"] == NAMES[0])
        self.assertEqual(target["price"], 48000)
        proof = next(item["price"] for item in self.diagnostics(body)["hotels"] if item["item"] == target)
        self.assertEqual(proof["type"], "analogs")
        self.assertEqual(len({analog["objectId"] for analog in proof["analogs"]}), 2)
        before = len(self.provider.calls)
        self.assertEqual(self.hotels(recommendation(count=3))["items"], full["items"])
        self.assertEqual(len(self.provider.calls), before)

    def test_two_accounts_share_catalog_but_not_search_diagnostics(self):
        original = recommendation()
        result = self.hotels(original)
        original_report = self.diagnostics(original)
        developer = {"email": "hotel-developer@example.test", "password": "hotel-developer-password"}
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/portal/data/register", json=developer).status_code, 200)
        self.client.post("/portal/data/login", json=self.owner)
        pending = self.client.get("/portal/data/admin/accounts").json()["accounts"]
        account_id = next(row["id"] for row in pending if row["email"] == developer["email"])
        path = "/portal/data/admin/accounts/" + account_id
        self.assertEqual(self.client.post(path, json={"action": "approve"}).status_code, 200)
        self.client.post("/portal/data/login", json=developer)
        self.assertEqual(self.client.get(DETAILS + original["taskId"]).status_code, 404)
        second = recommendation()
        self.assertEqual(self.hotels(second, portal=True)["items"], result["items"])
        self.assertEqual(self.diagnostics(second)["calls"]["flash"], 0)
        self.client.post("/portal/data/login", json=self.owner)
        self.assertEqual(self.diagnostics(original), original_report)
        self.assertEqual(self.client.get(DETAILS + second["taskId"]).status_code, 404)


class HotelRateTest(unittest.TestCase):
    def test_rates_directory_cannot_supply_official_site_or_generic_image(self):
        dest = RecommendationsRequest.model_validate(recommendation()).trip.destination
        hotel = {"name": "Гостиница Река", "address": "Лесная улица, 10"}
        html = "<title>Гостиница Река</title><address>Киото, Лесная улица, 10</address>"
        generic = parse_page(html + "<meta property='og:image' content='/town.jpg'>",
                             "https://travel.orb.ru/hotel/river")
        self.assertEqual(collect_fields(generic, hotel, dest, official=True), {})
        profile = parse_page(html + "<img alt='Фасад гостиницы Река' src='/facade.jpg'>",
                             "https://river.example.test/")
        self.assertEqual(set(collect_fields(profile, hotel, dest, official=True)), {"website", "image"})

    def test_rates_currency_header_byn_abbreviation_and_unknown_surcharge(self):
        from tripflow_api.hotel_evidence import offer_blocks
        header = "Стоимость номера за сутки (BYN)"
        room = "Сингл — одноместный стандартный номер"
        for line in ("BYN 260/сут.", "260 бел. руб. за сутки", "260/сут."):
            with self.subTest(line=line):
                rate = Rate(source=1, quote=line, amount="260", currency="BYN", basis="room_night", kind="published")
                offer = offer_blocks("\n".join((header, room, line)))[0]
                proof = {"sourceUrl": "https://example.test/rates", "quote": line}
                self.assertIsNotNone(checked_rate(rate, proof, "BY", offer=offer))
                self.assertIsNone(checked_rate(rate, proof, "BY", offer=offer + "\nОбязательный сбор"))
        with patch("tripflow_api.hotel_enrichment.socket.getaddrinfo",
                   return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]), patch(
                       "tripflow_api.hotel_enrichment.socket.create_connection") as socket_connect:
            self.assertIsNone(read_page("https://example.test/"))
            socket_connect.assert_not_called()

    def test_coverage_package_installments_and_dorm_bed(self):
        trip = RecommendationsRequest.model_validate(recommendation(trip={
            **recommendation()["trip"], "endDate": "2027-05-18", "travelers": 2})).trip
        price = "13 000 ₽ за одну ночь за два отдельных номера"
        offer = "Два отдельных номера, по одному гостю в каждом\n" + price
        def checked(line, amount, basis="room_night", rooms=1, offer=None):
            rate = Rate(source=1, quote=line, amount=amount, currency="RUB", basis=basis, kind="published", rooms=rooms)
            return checked_rate(rate, {"sourceUrl": "https://example.test/rooms", "quote": line}, "RU", offer=offer)
        self.assertIsNone(checked(price, "13000", offer=offer))
        rate = checked(price, "13000", "group_night", 2, offer)
        self.assertTrue(rate_applies(rate, trip, 3))
        self.assertEqual(group_price(rate, {"valueRub": "1", "nominal": 1}, 2, 3), 39000)
        self.assertIsNone(checked("Одноместный номер 2 512 ₽ за ночь, 4 платежа", "2512"))
        self.assertIsNone(checked("Койка в общем номере, 1 взрослый, 900 ₽ за ночь", "900"))
        legacy = {**rate, "basis": "room_night", "rooms": 1}
        legacy.pop("unitQuote")
        self.assertFalse(rate_applies(legacy, trip, 3))

    def test_second_review_source_money_formats(self):
        for raw, currency, amount in [("8 000", "RUB", "8000"), ("8\u00a0000", "RUB", "8000"),
                                      ("8\u202f000", "RUB", "8000"), ("8,000.50", "USD", "8000.50"),
                                      ("8.000,50", "EUR", "8000.50"), ("8,000", "RUB", "8000")]:
            with self.subTest(raw=raw):
                self.assertEqual(str(source_decimal(raw, currency)), amount)
        self.assertIsNone(source_decimal("8,000", "KWD"))
        self.assertIsNone(source_decimal("8,00,0", "USD"))

    def test_review_budget_measures_exact_bytes_and_output_reserve(self):
        tool = HotelTools(None, None, None, ("account", "task"), "test")
        body = HotelTools.flash_body("Проверить тариф", {"text": "Условия и цена " * 900}, 650)
        size = len(encode(body).encode("utf-8"))
        with patch("tripflow_api.hotel_tools.MAX_FLASH_BYTES", size), patch("tripflow_api.hotel_tools.MAX_FLASH_OUTPUT", 650):
            tool.require_budget("flash", body, [])
            with self.assertRaises(BudgetStop) as over:
                tool.require_budget("flash", body, [(1, "flash", 1, 0, "earlier", None)])
            self.assertEqual(over.exception.detail, {"stage": "flash", "unit": "input_bytes",
                "used": 1, "limit": size, "requested": size})
            with self.assertRaises(BudgetStop) as reserve:
                tool.require_budget("flash", body, [(1, "flash", 0, 1, "earlier", None)])
            self.assertEqual(reserve.exception.detail["unit"], "output_reserve")

    def test_review_seasonal_period_and_booking_parameters(self):
        november = RecommendationsRequest.model_validate(recommendation(trip={**recommendation()["trip"],
            "startDate": "2026-11-06", "endDate": "2026-11-09"})).trip
        december = november.model_copy(update={"startDate": date(2026, 12, 1), "endDate": date(2026, 12, 4)})
        line = "Одноместный номер 4 310 ₽ за 1 ночь"
        rate = Rate(source=1, quote=line, amount="4310", currency="RUB", basis="room_night", kind="published")
        page = {"sourceUrl": "https://example.test/rooms", "quote": line}
        seasonal = checked_rate(rate, page, "RU", context="Тариф действует 01.11.2026 — 01.12.2026\n" + line)
        self.assertTrue(rate_applies(seasonal, november, 3))
        self.assertEqual(rate_quality(seasonal, december, 3), "other_period")
        site = {**page, "sourceUrl": page["sourceUrl"] + "?public_filter_checkin_date=2026-11-06&public_filter_checkout_date=2026-11-09"}
        fixed = checked_rate(rate, site, "RU")
        self.assertTrue(rate_applies(fixed, november, 3))
        self.assertEqual(rate_quality(fixed, november.model_copy(update={"startDate": date(2026, 11, 7)}), 2), "other_period")
        camel = {**page, "sourceUrl": page["sourceUrl"] + "?checkinDate=2026-11-06&checkoutDate=2026-11-09"}
        fixed = checked_rate(rate, camel, "RU")
        self.assertEqual(fixed["scope"], "offer")
        self.assertTrue(rate_applies(fixed, november, 3))
        self.assertEqual(rate_quality(fixed, december, 3), "other_period")
        self.assertFalse(rate_applies({**fixed, "scope": "general", "start": None, "end": None}, december, 3))
        general = checked_rate(rate, page, "RU", context="Статья опубликована 11.10.2026\n" + line)
        self.assertTrue(rate_applies(general, december, 3))
    def test_period_room_and_group_rates(self):
        trip = RecommendationsRequest.model_validate(recommendation()).trip
        for basis, line, amount, rooms in (
            ("room_stay", "Single room for 1 adult. 2027-05-15 to 2027-05-17, total 16,000 RUB per stay", "16000", 1),
            ("group_stay", "3 single rooms for 1 adult each. 2027-05-15 to 2027-05-17, total 48,000 RUB per stay", "48000", 3),
        ):
            with self.subTest(basis=basis):
                raw = Rate(source=1, quote=line, amount=amount, currency="RUB", basis=basis, kind="published",
                           start="2027-05-15", end="2027-05-17", rooms=rooms)
                validated = checked_rate(raw, {"sourceUrl": "https://example.test/rooms", "quote": line}, "JP")
                self.assertIsNotNone(validated)
                self.assertTrue(rate_applies(validated, trip, 2))
                self.assertEqual(group_price(validated, {"valueRub": "1", "nominal": 1}, 3, 2), 48000)
                self.assertFalse(rate_applies(validated, trip.model_copy(update={"startDate": date(2027, 5, 16)}), 1))

"""Reproducible HTTP responses for hotel integration tests."""
import json

import httpx


NAMES = ("Kamo Garden Hotel", "Higashi Station Hotel", "Nijo Court Hotel")
BASE = "https://hotels.example.test/"
USAGE = {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}
BREAKFAST = "Breakfast served daily from 06:00 to 09:00."
CHECK_IN = "24-hour check-in, including arrivals after midnight."
SEWING = "A sewing machine is available for guest use in the lobby."


def completion(body):
    return httpx.Response(200, json={"usage": USAGE, "choices": [
        {"finish_reason": "stop", "message": {"content": json.dumps(body, ensure_ascii=False)}},
    ]})


class HotelProvider:
    def __init__(self, names=NAMES, *, currency="RUB"):
        self.calls = []
        self.search_count = 0
        self.names = names
        self.currency = currency
        self.failed_after = None
        self.city = "Kyoto"
        self.street = "Gion Street"
        self.rate_text = None
        self.facts = [BREAKFAST, CHECK_IN, SEWING, "The metro is 200 m away.", "The hotel is smoke-free."]
        self.query_limit = None
        self.bad_quote = False
        self.foreign_city = False
        self.rate_overrides = {}
        self.outages = set()
        self.truncate_at = None
        self.extraction = None
        self.fetch_content = {}
        self.russ = []
        self.geo = []
        self.geography = []
        self.queries = []
        self.plans = []
        self.fx_unavailable = False

    def price_line(self, name):
        amount = {"RUB": "8,000", "JPY": "12,001"}[self.currency]
        return self.rate_text or f"Single room for 1 adult | {amount} {self.currency} per room per night"

    def pages(self):
        rows = []
        for index, name in enumerate(self.names, 1):
            address = f"{index} {self.street}, {self.city}"
            content = f"# {name}\n{address}\nGion district\n3-star hotel\n{self.price_line(name)}\n" + "\n".join(self.facts)
            rows.append({"url": BASE + str(index), "title": name, "content": content})
        return rows

    def __call__(self, request):
        self.calls.append(request.url.path)
        if request.url.host == "russhotels.ru":
            return httpx.Response(503) if self.russ is None else httpx.Response(200, json=self.russ)
        if request.url.host == "api.geoapify.com":
            if request.url.path == "/v2/places":
                return httpx.Response(503) if self.geo is None else httpx.Response(200, json={"features": self.geo})
            if request.url.path == "/v1/geocode/reverse":
                return httpx.Response(200, json={"results": self.geography})
            query = request.url.params.get("text", "").casefold()
            if query == "москва":
                return httpx.Response(200, json={"results": [
                    {"city": "Москва", "state": "Москва", "country": "Россия", "country_code": "ru",
                     "lat": 55.75204, "lon": 37.61781},
                ]})
            if query == "киото":
                return httpx.Response(200, json={"results": [
                    {"city": "Киото", "state": "Префектура Киото", "country": "Япония", "country_code": "jp",
                     "lat": 35.01, "lon": 135.77},
                ]})
            return httpx.Response(200, json={"results": [
                {"city": "Спрингфилд", "state": "Миссури", "country": "США", "country_code": "us", "lat": 0, "lon": 0},
                {"city": "Спрингфилд", "state": "Иллинойс", "country": "США", "country_code": "us", "lat": 39.8, "lon": -89.6},
            ]})
        if request.url.host == "www.cbr.ru":
            if self.fx_unavailable:
                return httpx.Response(503)
            return httpx.Response(200, text='<ValCurs Date="23.11.2026"><Valute><CharCode>JPY</CharCode>'
                                 '<Nominal>100</Nominal><Value>52,5555</Value></Valute>'
                                 '<Valute><CharCode>USD</CharCode><Nominal>1</Nominal><Value>90</Value></Valute>'
                                 '<Valute><CharCode>AED</CharCode><Nominal>1</Nominal><Value>25</Value></Valute>'
                                 '<Valute><CharCode>BYN</CharCode><Nominal>1</Nominal><Value>30</Value></Valute>'
                                 '<Valute><CharCode>EUR</CharCode><Nominal>1</Nominal><Value>100</Value></Valute>'
                                 '<Valute><CharCode>GBP</CharCode><Nominal>1</Nominal><Value>120</Value></Valute></ValCurs>')
        if request.url.path in self.outages:
            return httpx.Response(503)
        body = json.loads(request.content)
        if request.url.path == "/v1/tools/search":
            self.search_count += 1
            self.queries.append(body["query"])
            if self.failed_after is not None and self.search_count > self.failed_after:
                return httpx.Response(503)
            return httpx.Response(200, json={"results": self.pages() if self.query_limit is None or self.search_count <= self.query_limit else []})
        if request.url.path == "/v1/tools/fetch":
            row = next((row for row in self.pages() if row["url"] == body["url"]), None)
            if row:
                return httpx.Response(200, json={**row, "content": self.fetch_content.get(body["url"], row["content"])})
            return httpx.Response(404)
        data = json.loads(body["messages"][1]["content"])
        if "pages" not in data:
            if "destination" in data:
                self.plans.append(data)
                return completion({"queries": ["Kyoto hotels single room"], "cityNames": [self.city]})
            if "refinement" in data:
                return completion({"changes": [], "additions": []})
            return completion({"conditions": []})
        if self.truncate_at is not None and len(data["pages"]) >= self.truncate_at:
            return httpx.Response(200, json={"usage": USAGE, "choices": [
                {"finish_reason": "length", "message": {"content": '{"items": ['}},
            ]})
        if self.extraction:
            return completion({"items": self.extraction(data)})
        items = []
        for page in data["pages"]:
            name = page["heading"]
            if name not in self.names:
                continue
            index = self.names.index(name) + 1
            addr = f"{index} {self.street}, {self.city}"
            proof = lambda quote: {"source": page["id"], "quote": quote}
            rate = self.price_line(name)
            result = {"name": name, "city": proof("Elsewhere" if self.foreign_city else self.city),
                      "identity": proof("Invented Hotel" if self.bad_quote else name),
                      "address": proof(addr), "district": proof("Gion district"), "stars": proof("3-star hotel"),
                      "rates": [{**proof(rate), "amount": "12001" if self.currency == "JPY" else "8000",
                                 "currency": self.currency, "basis": "room_night", "kind": "published",
                                 **self.rate_overrides}], "checks": []}
            for position, condition in enumerate(data["conditions"]):
                meaning = condition["meaning"].casefold()
                fact = next((self.facts[i] for i, words in enumerate((
                    ("завтрак", "breakfast"), ("заезд", "заселен", "check-in", "midnight"),
                    ("машинк", "sewing"), ("метро", "metro"), ("курен", "smoking"),
                )) if i < len(self.facts) and any(word in meaning for word in words)), None)
                if fact:
                    check = {**proof(fact), "condition": position, "verdict": "confirmed"}
                    if "Saturday" in fact:
                        check.update(weekdays=[5], dayBasis="stay")
                    result["checks"].append(check)
            items.append(result)
        return completion({"items": items})

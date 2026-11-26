import asyncio
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote

import httpx

from .hotel_catalog import proximity
from .hotel_evidence import INSTALLMENT, MULTI_ADDRESS, SHARED_BED, Rate, checked_rate, city_aliases, normalized, room_counts, source_url
from .hotel_tools import SearchInterrupted, short_text
from .preferences import encode


GEO = "https://api.geoapify.com"
RUSS = "https://russhotels.ru"
RUSS_DOC = "https://wiki.russhotels.ru/doku.php?id=site:api#поиск_отелейпредложений_index"
RADIUS_KM = 5
CATEGORIES = {"accommodation.hotel": "hotel", "accommodation.hostel": "hostel",
              "accommodation.guest_house": "guest_house", "accommodation.motel": "motel"}
KIROV_REGIONS = {
    "Калужская область": re.compile(r"калужск\w*\s+обл|kaluzhsk\w*\s+obl|kaluga\s+(?:oblast|region)", re.I),
    "Кировская область": re.compile(r"кировск\w*\s+обл|kirovsk\w*\s+obl|kirov\s+(?:oblast|region)", re.I),
}


def city_matches(city, destination):
    return isinstance(city, str) and normalized(city) in {normalized(name) for name in city_aliases(destination)}


def region_proof(text, region):
    for key, pattern in KIROV_REGIONS.items():
        if pattern.search(normalized(region)):
            return bool(pattern.search(normalized(unquote(text))))
    return bool(region and len(normalized(region)) >= 4 and normalized(region) in normalized(text))


def wrong_city_title(text, destination):
    return (destination.countryCode == "UA" and normalized(destination.city) in ("константинополь", "костянтинопіль",
            "constantinople", "konstantinopol", "kostiantynopil")
            and bool(re.search(r"\b(?:istanbul|стамбул|стамбулі)\b", normalized(unquote(text)))))


def region_conflicts(text, region):
    expected = next((key for key, pattern in KIROV_REGIONS.items() if pattern.search(normalized(region))), None)
    raw = normalized(unquote(text))
    return bool(expected and any(key != expected and pattern.search(raw) for key, pattern in KIROV_REGIONS.items()))


def local_region(destination):
    if destination.countryCode == "RU" and normalized(destination.city) in ("киров", "kirov"):
        for lat, lon, name in ((54.07429, 34.30260, "Калужская область"),
                               (58.60357, 49.66662, "Кировская область")):
            if proximity(lat, lon, destination.latitude, destination.longitude) < 15:
                return name
    return ""


def nearby(destination, lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if abs(lat) <= 90 and abs(lon) <= 180 and proximity(lat, lon, destination.latitude, destination.longitude) <= RADIUS_KM:
            return {"latitude": lat, "longitude": lon}
    except (ValueError, TypeError):
        pass
    return None


def observed_at(raw):
    try:
        timestamp = int(raw)
        if 0 < timestamp <= time.time():
            return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        pass
    return None


def candidate(name, address, coordinates, url, city, region, category, provider, external_id, **fields):
    return {"name": name, "identity": {"sourceUrl": url, "quote": name},
            "cityEvidence": {"sourceUrl": url, "quote": ", ".join(filter(None, (city, region)))},
            "locationAliases": [], "address": address or None, "coordinates": coordinates,
            "district": None, "stars": None, "imageUrl": None, "rates": {}, "facts": [], "availability": [],
            "lodgingType": category, "discovery": [provider], "providerIds": {provider: external_id}, **fields}


def geo_candidate(row, destination, region):
    if not isinstance(row, dict) or not isinstance(row.get("properties"), dict):
        return None
    data = row["properties"]
    name, external_id = short_text(data.get("name"), 200), short_text(data.get("place_id"), 240)
    category = next((CATEGORIES[k] for k in data.get("categories", ()) if k in CATEGORIES), None) if isinstance(data.get("categories"), list) else None
    city, state = data.get("city"), short_text(data.get("state"), 100)
    address = short_text(data.get("formatted"), 240)
    coordinates = nearby(destination, data.get("lat"), data.get("lon"))
    if not (name and external_id and category and coordinates and city_matches(city, destination)
            and str(data.get("country_code")).upper() == destination.countryCode
            and not region_conflicts(f"{state} {address}", region)):
        return None
    # The provider place ID stays private. A map link carries only public coordinates.
    url = "https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}".format(**coordinates)
    return candidate(name, address, coordinates, url, destination.city, state, category, "geoapify", external_id,
                     website=source_url(short_text(data.get("website"), 2048)))


def russ_candidate(row, destination, region):
    if not isinstance(row, dict) or not isinstance(row.get("city"), dict):
        return None
    name, external_id = short_text(row.get("name"), 200), str(row.get("id", ""))
    city = row["city"].get("name")
    address = short_text(row.get("address"), 240)
    regional_address = short_text(row.get("post_address"), 240)
    coordinates = nearby(destination, row.get("geo_lat"), row.get("geo_lon"))
    city_name, _, qualifier = city.partition("(") if isinstance(city, str) else ("", "", "")
    scoped = bool(qualifier and region_proof(qualifier, region))
    if not (name and external_id.isdecimal() and coordinates and city_matches(city_name.strip(), destination)
            and (not qualifier or scoped) and not region_conflicts(f"{city} {address} {regional_address}", region)
            and str(row.get("active")) != "0"):
        return None
    public_url = f"{RUSS}/hotel/view?id={external_id}"
    category_label = row.get("placement_type")
    label = short_text(category_label.get("name"), 80) if isinstance(category_label, dict) else ""
    category = "hostel" if "хостел" in label.casefold() else "guest_house" if "гостевой дом" in label.casefold() else "hotel"
    names = [normalized(name)]
    if alias := re.search(r"\(бывш\.?\s+([^()]+)\)", name, re.I):
        names.append(normalized(alias[1]))
    multi_address = bool(MULTI_ADDRESS.search(name))
    hotel = candidate(name, "" if multi_address else address, coordinates, public_url, destination.city, region, category, "russhotels", external_id,
                      publicUrl=public_url, providerScopedCity=scoped, names=names)
    rooms = row.get("rooms")
    for room in rooms[:30] if isinstance(rooms, list) else ():
        if not isinstance(room, dict) or not isinstance(room.get("placement_type"), dict):
            continue
        placement = room["placement_type"]
        label = short_text(placement.get("name"), 100)
        room_name = short_text(room.get("name"), 200)
        if (normalized(label) != "одноместное" or str(placement.get("sleeping_place", "1")) != "1" or not room_name
                or room_counts(room_name) - {1} or SHARED_BED.search(room_name) or INSTALLMENT.search(room_name)):
            continue
        try:
            amount = format(Decimal(str(room.get("price_client"))), "f")
        except InvalidOperation:
            continue
        if not re.fullmatch(r"[1-9]\d{0,10}(?:\.\d{1,2})?", amount):
            continue
        price_line = f"{amount} RUB за сутки"
        # The room label can describe a double bed; placement says how the private room is sold.
        rate = Rate(source=1, quote=price_line, amount=amount, currency="RUB", basis="room_night", kind="published")
        evidence = {"quote": price_line, "sourceUrl": public_url}
        if checked := checked_rate(rate, evidence, "RU", offer=f"{label} размещение\n{price_line}"):
            observed = observed_at(room.get("updated_at")) or observed_at(row.get("last_modified"))
            checked.update(provider="russhotels", providerHotelId=external_id, providerRoomId=str(room.get("id", "")),
                           providerRoom=room_name, providerPlacement=label, providerAmount=room["price_client"],
                           observedOn=observed, documentationUrl=RUSS_DOC)
            offer_address = short_text(room.get("address"), 240)
            if multi_address and offer_address and city_matches(city_name.strip(), destination) and not region_conflicts(offer_address, region):
                checked["offerAddress"] = {"value": offer_address, "sourceUrl": public_url, "roomId": checked["providerRoomId"]}
            hotel["rates"][encode(checked)] = checked
    return hotel


class HotelSources:
    def __init__(self, tools, geo_key):
        self.tools = tools
        self.geo_key = geo_key

    async def request(self, kind, url, parameters, *, post=False):
        async def operation(payload):
            query = {} if post else {**payload, "apiKey": self.geo_key}
            retryable = False
            try:
                async with asyncio.timeout(12 if post else 7), self.tools.external.stream(
                    "POST" if post else "GET", url, params=query, json=payload if post else None, timeout=None,
                ) as response:
                    response.raise_for_status()
                    content = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        content.extend(chunk)
                        if len(content) > 2_000_000:
                            raise ValueError
                parsed = json.loads(content)
                if kind == "russhotels" and isinstance(parsed, list):
                    return parsed[:20], None, None
                field = "results" if kind == "geocode" else "features"
                if isinstance(parsed, dict) and isinstance(parsed.get(field), list):
                    return parsed[field][:20], None, None
            except httpx.HTTPStatusError as failure:
                status = failure.response.status_code
                retryable = status in (408, 429) or status >= 500
            except (httpx.HTTPError, TimeoutError):
                retryable = True
            except (ValueError, RecursionError):
                pass
            raise SearchInterrupted(kind + "_unavailable", post and retryable)

        return await self.tools.step(kind, parameters, operation)

    async def geography(self, destination):
        if not self.geo_key:
            return None
        rows = await self.request("geocode", GEO + "/v1/geocode/reverse", {
            "lat": destination.latitude, "lon": destination.longitude, "lang": "ru", "type": "city", "format": "json",
        })
        for row in rows:
            if (isinstance(row, dict) and city_matches(row.get("city"), destination)
                    and str(row.get("country_code")).upper() == destination.countryCode):
                return {"region": short_text(row.get("state"), 100), "placeId": short_text(row.get("place_id"), 240)}
        return None

    async def places(self, destination):
        return await self.request("places", GEO + "/v2/places", {
            "categories": ",".join(CATEGORIES), "filter": f"circle:{destination.longitude},{destination.latitude},5000",
            "bias": f"proximity:{destination.longitude},{destination.latitude}", "limit": 20, "lang": "ru",
        }) if self.geo_key else []

    async def russian(self, destination):
        # Without dates, hotel/index documents price_client per room per night in RUB.
        return await self.request("russhotels", RUSS + "/api/hotel/index", {
            "city_name": destination.city, "geo_lat_center": destination.latitude,
            "geo_lon_center": destination.longitude, "radius": RADIUS_KM, "limit": 20, "offset": 0,
        }, post=True)

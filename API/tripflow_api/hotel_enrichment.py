"""Bounded metadata reads for the final hotels in a task."""

import asyncio
import ipaddress
import json
import re
import socket
import ssl
import time
from html.parser import HTMLParser
from http.client import HTTPException, HTTPSConnection
from urllib.parse import urljoin, urlsplit

from .hotel_catalog import proximity
from .hotel_evidence import IMAGE_EXCLUDED, MULTI_ADDRESS, hotel_name_matches, name_matches, source_url
from .hotel_tools import SearchInterrupted


TLS = ssl.create_default_context()
MAX_HTML = 256_000
CACHE_SECONDS = 24 * 3600
META_FIELDS = {"og:title", "og:image", "og:image:secure_url", "og:image:alt", "twitter:title", "twitter:image"}
AGGREGATORS = ("booking.com", "ostrovok.ru", "russhotels.ru", "edem-v-gosti.ru", "tinkoff.ru", "yandex.ru",
               "2gis.ru", "orgsprav.com", "travel.orb.ru", "prohotel.ru", "komandirovka.ru",
               "aviasales.ru", "domik.travel", "putevka.com", "broni.travel")
DIRECTORY = re.compile(r"справочник|адрес.{0,25}телефон.{0,30}(?:режим|часы)|directory|reviews and photos", re.I)
STREET = r"(?:ул(?:ица)?|пр(?:оспект| кт| т)?|переулок|наб(?:ережная)?)"
HOUSE = r"[1-9]\d{0,4}[a-zа-я]?(?:/[1-9]\d{0,3}[a-zа-я]?)?"
OFFICIAL = re.compile(r"официальн\w*\s+сайт|official\s+(?:site|website)", re.I)


class HotelPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.images = []
        self.parts = []
        self.title = []
        self.in_title = False
        self.ignored = False
        self.ld_buffer = None
        self.businesses = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag in ("script", "style"):
            self.ignored = True
            if tag == "script" and (data.get("type") or "").casefold() == "application/ld+json":
                self.ld_buffer = []
        elif tag == "meta":
            key = data.get("property") or data.get("name")
            if key and key.lower() in META_FIELDS and data.get("content"):
                self.meta.setdefault(key.lower(), data["content"][:1000])
        elif tag == "img" and len(self.images) < 120:
            raw = data.get("data-src") or data.get("src")
            if raw:
                self.images.append([data.get("alt") or "", raw[:2048]])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag in ("script", "style"):
            self.ignored = False
            if tag == "script" and self.ld_buffer is not None:
                try:
                    block = json.loads("".join(self.ld_buffer))
                    self.businesses.extend(lodging_records(block))
                except (ValueError, RecursionError):
                    pass
                self.ld_buffer = None

    def handle_data(self, data):
        if self.ld_buffer is not None:
            self.ld_buffer.append(data)
        if self.in_title:
            self.title.append(data.strip())
        if not self.ignored and data.strip():
            self.parts.append(data.strip())


def lodging_records(block):
    records = block if isinstance(block, list) else [block]
    for row in records:
        if isinstance(row, dict):
            for entry in [row, *(row.get("@graph") if isinstance(row.get("@graph"), list) else [])]:
                if isinstance(entry, dict):
                    types = entry.get("@type", "")
                    values = types if isinstance(types, list) else [types]
                    if any(kind in ("Hotel", "Hostel", "Motel", "LodgingBusiness", "Resort", "BedAndBreakfast")
                           for kind in values):
                        yield entry


def parse_page(html, url):
    page = HotelPage()
    page.feed(html)
    return {"url": url, "title": " ".join(page.title)[:300] or page.meta.get("og:title", ""),
            "text": "\n".join(page.parts)[:50_000], "meta": page.meta, "images": page.images,
            "businesses": page.businesses[:12]}


def permitted_ip(raw):
    address = ipaddress.ip_address(raw)
    return address.is_global and not address.is_multicast and not address.is_reserved


def read_page(raw_url):
    url = source_url(raw_url)
    stop = time.monotonic() + 5
    for _ in range(2):
        if not url or time.monotonic() >= stop:
            return None
        parts = urlsplit(url)
        host = parts.hostname
        connection = None
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            if not addresses or not all(permitted_ip(row[4][0]) for row in addresses):
                return None
            # The connection uses the checked IP and verifies TLS for the original host.
            remaining = stop - time.monotonic()
            if remaining <= 0:
                return None
            with socket.create_connection((addresses[0][4][0], 443), timeout=remaining) as tcp:
                with TLS.wrap_socket(tcp, server_hostname=host) as sock:
                    connection = HTTPSConnection(host, timeout=remaining, context=TLS)
                    connection.sock = sock
                    path = parts.path or "/"
                    if parts.query:
                        path += "?" + parts.query
                    connection.request("GET", path, headers={"Accept": "text/html", "User-Agent": "TripFlow/1.0"})
                    with connection.getresponse() as response:
                        if response.status in (301, 302, 303, 307, 308):
                            redirect = response.getheader("Location")
                            url = source_url(urljoin(url, redirect)) if redirect else None
                            continue
                        media = response.getheader("Content-Type", "")
                        if response.status != 200 or media.split(";")[0].strip().lower() != "text/html":
                            return None
                        raw = bytearray()
                        while time.monotonic() < stop:
                            sock.settimeout(max(0.05, stop - time.monotonic()))
                            chunk = response.read1(8192)
                            if not chunk:
                                break
                            raw.extend(chunk)
                            if len(raw) > MAX_HTML:
                                return None
                        else:
                            return None
            charset = re.search(r"charset=([\w-]+)", media, re.I)
            return parse_page(raw.decode(charset[1] if charset else "utf-8", "replace"), url)
        except (OSError, HTTPException, LookupError, ValueError):
            return None
        finally:
            if connection:
                connection.close()
    return None


def compact(value):
    compacted = " ".join(re.findall(r"\w+(?:/\d+)?", value.casefold().replace("ё", "е")))
    return re.sub(r"\b(?:пр кт|пр т|проспект|пр)\b", "проспект", compacted)


def street_locator(address):
    value = compact(address)
    match = re.search(rf"\b{STREET}\s+(.{{2,65}}?)\s+(?:(?:д|дом|зд|здание|вл)\s+)?({HOUSE})(?![\w/])", value)
    if not match:
        return None
    words = [word for word in match[1].split() if len(word) > 1]
    return tuple(words), match[2]


def address_on_page(address, lines):
    if not address:
        return False
    parts = [compact(piece) for piece in address.split(",") if piece.strip()]
    text = " " + compact(lines) + " "
    # Full address or consecutive street and house components.
    if locator := street_locator(address):
        words, house = locator
        if words and re.search(r"\b" + r"(?:\s+[а-яa-z]){0,2}\s+".join(map(re.escape, words)) +
                               r"\s+(?:(?:д|дом|зд|здание|вл)\s+)?" + re.escape(house) + r"(?![\w/])", text):
            return True
    return " " + " ".join(parts) + " " in text or (
        len(parts) >= 2 and bool(re.search(r"\d", parts[-1])) and
        " " + " ".join(parts[-2:]) + " " in text)


def collect_fields(page, hotel, destination, *, supplier=False, official=False, direct_site=False):
    title, text, url = page["title"], page["text"], page["url"]
    if not hotel_name_matches(hotel["name"], title):
        return {}
    address = hotel["address"]
    title_and_excerpt = title + "\n" + text
    at_address = address_on_page(address, title_and_excerpt)
    city = any(name_matches(alias, title_and_excerpt) for alias in (destination.city, *hotel.get("locationAliases", ())))
    fields = {}
    if not address and direct_site and city and official:
        proofs = {}
        for line in text.splitlines():
            if name_matches(destination.city, line) and (locator := street_locator(line)):
                proofs.setdefault(locator, line[:240])
        if len(proofs) == 1:
            at_address = True
            fields["address"] = {"value": next(iter(proofs.values())), "sourceUrl": url}
    for listing in page.get("businesses", ()):
        if not isinstance(listing.get("name"), str) or not hotel_name_matches(hotel["name"], listing["name"]):
            continue
        address_data = listing.get("address")
        coords = hotel.get("coordinates")
        point = listing.get("geo")
        if not (isinstance(address_data, dict) and isinstance(point, dict) and coords):
            continue
        locality = address_data.get("addressLocality")
        street = address_data.get("streetAddress")
        if not (isinstance(locality, str) and isinstance(street, str) and street.strip()
                and name_matches(destination.city, locality)):
            continue
        try:
            lat, lon = float(point["latitude"]), float(point["longitude"])
            near = proximity(lat, lon, coords["latitude"], coords["longitude"]) <= 0.12
        except (ValueError, TypeError, KeyError):
            near = False
        if near:
            at_address = True
            city = True
            if not address:
                fields["address"] = {"value": f"{locality}, {street}"[:240], "sourceUrl": url}
            own_url = source_url(listing.get("url")) if isinstance(listing.get("url"), str) else None
            official |= bool(own_url and urlsplit(own_url).hostname == urlsplit(url).hostname)
            break
    if not (supplier or (city and at_address)):
        return {}

    host = urlsplit(url).hostname
    own_page = (official and not supplier and not DIRECTORY.search(title)
                and not any(host == domain or host.endswith("." + domain) for domain in AGGREGATORS))
    if own_page:
        fields["website"] = {"value": url, "sourceUrl": url, "quote": title, "verified": True}
    for alt, path in page["images"]:
        if IMAGE_EXCLUDED.search(alt + " " + path):
            continue
        if hotel_name_matches(hotel["name"], alt):
            if image := source_url(urljoin(url, path)):
                fields["image"] = {"value": image, "sourceUrl": url, "quote": alt}
                return fields
    if supplier or own_page:
        for key in ("og:image:secure_url", "og:image", "twitter:image"):
            path = page["meta"].get(key)
            alt = page["meta"].get("og:image:alt") or title
            if (path and (not supplier or page["meta"].get("og:image:alt"))
                    and not IMAGE_EXCLUDED.search(path + " " + alt)
                    and hotel_name_matches(hotel["name"], alt)
                    and (image := source_url(urljoin(url, path)))):
                fields["image"] = {"value": image, "sourceUrl": url, "quote": alt}
                break
    return fields


class HotelEnrichment:
    def __init__(self, search):
        self.search = search
        self.tools = search.tools
        self.catalog = search.catalog

    async def load(self, url):
        async def operation(payload):
            try:
                doc = await asyncio.wait_for(asyncio.to_thread(read_page, payload["url"]), timeout=6)
            except TimeoutError:
                doc = None
            return doc or {}, None, None

        return await self.tools.step("enrich_fetch", {"url": url}, operation)

    def saved_fields(self, match, hotel):
        saved = dict(match.get("metadata", {}))
        previous_site = saved.get("website")
        if previous_site and not previous_site.get("verified"):
            saved.pop("website")
            if saved.get("image", {}).get("sourceUrl") == previous_site["sourceUrl"]:
                saved.pop("image")
        if saved.get("image") and IMAGE_EXCLUDED.search(saved["image"]["value"]):
            del saved["image"]
        evidence = (match["price"].get("rate") or {}).get("sourceUrl") or match["item"]["sourceUrl"]
        if match["item"]["address"]:
            saved.setdefault("address", {"value": match["item"]["address"],
                             "sourceUrl": hotel["cityEvidence"]["sourceUrl"]})
        if hotel.get("imageUrl") and not IMAGE_EXCLUDED.search(hotel["imageUrl"]):
            saved.setdefault("image", {"value": hotel["imageUrl"], "sourceUrl": hotel["identity"]["sourceUrl"]})
        return saved, evidence

    async def run(self):
        for index, match in enumerate(self.search.matches[:self.search.request.count]):
            item = match["item"]
            hotel = self.search.current_hotels[item["objectId"]]
            if MULTI_ADDRESS.search(hotel["name"]):
                continue
            fields, price_source = self.saved_fields(match, hotel)
            match["metadata"] = fields
            item["imageUrl"] = (fields.get("image") or {}).get("value")
            if fields.get("address"):
                item["address"] = fields["address"]["value"]
            if index >= 2 or (fields.get("image") and fields.get("website")):
                continue
            if hotel.get("enrichedAt", 0) >= time.time() - CACHE_SECONDS:
                continue
            self.catalog.save_enrichment(self.search.destination.countryCode, item["objectId"], {}, attempted=True)
            hints = []
            if website := (fields.get("website") or {}).get("value") or hotel.get("website"):
                hints.append((website, False, True))
            if price_source and urlsplit(price_source).hostname in ("russhotels.ru", "www.russhotels.ru"):
                hints.append((price_source, True, False))
            elif price_source and not hints:
                origin = urlsplit(price_source)
                hints.append((origin._replace(path="/", query="", fragment="").geturl(), False, False))
                if origin.path not in ("", "/"):
                    hints.append((price_source, False, False))
            visited = set()
            for url, supplier, official in hints:
                await self.add_page(url, supplier, official, visited, match, hotel, fields)
            if self.search.configured and not (fields.get("image") and fields.get("website")):
                trip = self.search.destination
                locator = street_locator(hotel["address"] or "")
                street = " ".join((*locator[0], locator[1])) if locator else ""
                query = f"{hotel['name'][:42]} {trip.city[:27]} официальный сайт {street[:26]}"
                try:
                    results = await self.tools.enrich_search(query[:128])
                except SearchInterrupted:
                    continue
                candidates = {}
                for index, row in enumerate(results):
                    url = source_url(row["url"])
                    if not url or url in visited:
                        continue
                    page = urlsplit(url)
                    named = hotel_name_matches(hotel["name"], row["title"])
                    text = row["title"] + " " + row["content"][:1600]
                    at_address = address_on_page(hotel["address"], text)
                    if not (named or at_address and hotel_name_matches(hotel["name"], text)):
                        continue
                    aggregator = any(page.hostname == domain or page.hostname.endswith("." + domain)
                                     for domain in AGGREGATORS)
                    origin = page._replace(path="/", query="", fragment="").geturl()
                    preferred = url if aggregator else origin
                    priority = (aggregator, not at_address, not named, index)
                    if preferred not in candidates or priority < candidates[preferred]:
                        candidates[preferred] = priority
                for url in sorted(candidates, key=candidates.get)[:2]:
                    await self.add_page(url, False, False, visited, match, hotel, fields)
                    if fields.get("image") and fields.get("website"):
                        break

    async def add_page(self, url, supplier, official, visited, match, hotel, fields):
        url = source_url(url)
        if not url or url in visited:
            return
        visited.add(url)
        try:
            page = await self.load(url)
        except SearchInterrupted:
            return
        if page:
            official = official or bool(OFFICIAL.search(page["title"]))
            rate_url = (match["price"].get("rate") or {}).get("sourceUrl")
            own_origin = (not supplier and rate_url and urlsplit(rate_url).hostname == urlsplit(page["url"]).hostname)
            found = collect_fields(page, hotel, self.search.destination, supplier=supplier and page["url"] == url,
                                   official=official, direct_site=bool(own_origin))
            if found:
                match["metadata"] = self.catalog.save_enrichment(
                    self.search.destination.countryCode, match["item"]["objectId"], {**fields, **found})
                fields.update(match["metadata"])
                if fields.get("image"):
                    match["item"]["imageUrl"] = fields["image"]["value"]
                if fields.get("address"):
                    match["item"]["address"] = fields["address"]["value"]

import hashlib
import json
import math
import re
import time
from uuid import uuid4

from .hotel_evidence import normalized, provider_identity
from .preferences import encode


class HotelCatalog:
    def __init__(self, db):
        self.db = db
        db.execute("CREATE TABLE IF NOT EXISTS hotel_country_locks (country TEXT PRIMARY KEY)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS hotel_destinations (
                id TEXT PRIMARY KEY, country TEXT NOT NULL, city TEXT NOT NULL,
                latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS hotel_destinations_country ON hotel_destinations(country)")
        db.execute("""CREATE TABLE IF NOT EXISTS hotel_geography (
            city_id TEXT PRIMARY KEY, saved_at BIGINT NOT NULL, data TEXT NOT NULL
        )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS hotel_catalog (
                city_id TEXT NOT NULL, object_id TEXT NOT NULL PRIMARY KEY, data TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS hotel_catalog_city ON hotel_catalog(city_id)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS hotel_aliases (
                city_id TEXT NOT NULL, url TEXT NOT NULL, object_id TEXT NOT NULL,
                PRIMARY KEY (city_id, url)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS hotel_diagnostics (
                client_id TEXT NOT NULL, task_id TEXT NOT NULL, initial_catalog TEXT NOT NULL, outcome TEXT,
                PRIMARY KEY (client_id, task_id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS hotel_checks (
                client_id TEXT NOT NULL, task_id TEXT NOT NULL, object_id TEXT NOT NULL, checks TEXT NOT NULL,
                PRIMARY KEY (client_id, task_id, object_id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS hotel_focus (
                client_id TEXT NOT NULL, fingerprint TEXT NOT NULL, task_id TEXT NOT NULL, object_id TEXT NOT NULL,
                gap TEXT NOT NULL, checked INTEGER NOT NULL,
                PRIMARY KEY (client_id, fingerprint, task_id, object_id, gap)
            )
        """)

    def lock(self, country):
        self.db.execute("INSERT INTO hotel_country_locks (country) VALUES (?) ON CONFLICT DO NOTHING", (country,))
        self.db.execute("UPDATE hotel_country_locks SET country = country WHERE country = ?", (country,))

    def city(self, destination):
        name, country = normalized(destination.city), destination.countryCode
        lat, lon = destination.latitude, destination.longitude
        with self.db.transaction():
            self.lock(country)
            rows = self.db.execute("""
                SELECT id, city, latitude, longitude FROM hotel_destinations
                WHERE country = ? AND latitude BETWEEN ? AND ?
            """, (country, lat - 0.2, lat + 0.2)).fetchall()
            nearby = []
            for city_id, city, latitude, longitude in rows:
                distance = proximity(lat, lon, latitude, longitude)
                if distance <= (10 if city == name else 0.75):
                    nearby.append((city != name, distance, city_id))
            if nearby:
                return min(nearby)[2]
            city_id = uuid4().hex
            self.db.execute("INSERT INTO hotel_destinations VALUES (?, ?, ?, ?, ?)", (city_id, country, name, lat, lon))
            return city_id

    @staticmethod
    def hint_key(destination):
        return hashlib.sha256(encode([destination.countryCode, normalized(destination.city),
                                      destination.latitude, destination.longitude]).encode()).hexdigest()

    def remember_place(self, destination, region, place_id):
        if region or place_id:
            self.save_geography(self.hint_key(destination), {"region": region, "placeId": place_id})

    def geography(self, city_id):
        row = self.db.execute("SELECT data FROM hotel_geography WHERE city_id = ? AND saved_at > ?",
                              (city_id, int(time.time()) - 7 * 86400)).fetchone()
        return json.loads(row[0]) if row else None

    def save_geography(self, city_id, data):
        self.db.execute("""INSERT INTO hotel_geography VALUES (?, ?, ?)
            ON CONFLICT(city_id) DO UPDATE SET saved_at = excluded.saved_at, data = excluded.data
        """, (city_id, int(time.time()), encode(data)))

    def properties(self, city_id):
        rows = self.db.execute("SELECT object_id, data FROM hotel_catalog WHERE city_id = ? ORDER BY object_id",
                               (city_id,)).fetchall()
        raw = {object_id: json.loads(data) for object_id, data in rows}
        canonical, aliases = {}, {}
        for object_id, hotel in raw.items():
            matches = [key for key in canonical if same_hotel(hotel, raw[key])]
            canonical_id = matches[0] if len(matches) == 1 else object_id
            aliases[object_id] = canonical_id
            if canonical_id == object_id:
                canonical[object_id] = json.loads(encode(hotel))
            else:
                merge_hotel(canonical[canonical_id], hotel)
        return raw, canonical, aliases

    def snapshot(self, city_id, excluded):
        _, canonical, aliases = self.properties(city_id)
        excluded = {aliases.get(key, key) for key in excluded}
        return {key: hotel for key, hotel in canonical.items() if key not in excluded}

    def canonical_id(self, city_id, object_id):
        return self.properties(city_id)[2].get(object_id, object_id)

    def ambiguous_city(self, city_id, destination):
        return self.db.execute("""
            SELECT 1 FROM hotel_destinations WHERE country = ? AND city = ? AND id <> ? LIMIT 1
        """, (destination.countryCode, normalized(destination.city), city_id)).fetchone() is not None

    def store(self, country, city_id, candidate):
        url = candidate["identity"]["sourceUrl"]
        with self.db.transaction():
            self.lock(country)
            known = self.db.execute("SELECT object_id FROM hotel_aliases WHERE city_id = ? AND url = ?",
                                    (city_id, url)).fetchone()
            raw, current, aliases = self.properties(city_id)
            matched = [object_id for object_id, hotel in current.items() if same_hotel(candidate, hotel)]
            if known:
                object_id = aliases[known[0]]
                hotel = raw[known[0]]
                if (matched and object_id not in matched or
                        (not same_name(candidate, hotel) and not same_address(candidate, hotel)) or
                        (conflicting_location(candidate, hotel) and not same_hotel(candidate, hotel))):
                    return None
            elif len(matched) == 1:
                object_id = matched[0]
            elif matched or any(
                same_name(candidate, hotel) and not conflicting_location(candidate, hotel)
                for hotel in current.values()
            ):
                return None
            else:
                object_id = "hotel-" + uuid4().hex

            hotel = current.get(object_id)
            if hotel is None:
                hotel = {**candidate, "names": sorted(set(candidate.get("names", ())) | {normalized(candidate["name"])})}
            else:
                merge_hotel(hotel, candidate)
            self.db.execute("""
                INSERT INTO hotel_catalog (city_id, object_id, data) VALUES (?, ?, ?)
                ON CONFLICT(object_id) DO UPDATE SET data = excluded.data
            """, (city_id, object_id, encode(hotel)))
            for alias in set(candidate.get("sources", ())) | {url}:
                self.db.execute("INSERT INTO hotel_aliases VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                                (city_id, alias, object_id))
            return object_id, hotel

    def save_enrichment(self, country, object_id, fields, *, attempted=False):
        with self.db.transaction():
            self.lock(country)
            row = self.db.execute("SELECT data FROM hotel_catalog WHERE object_id = ?", (object_id,)).fetchone()
            if row is None:
                return fields
            hotel = json.loads(row[0])
            metadata = hotel.setdefault("metadata", {})
            if metadata.get("website") and not metadata["website"].get("verified"):
                old_site = metadata.pop("website")
                if metadata.get("image", {}).get("sourceUrl") == old_site["sourceUrl"]:
                    metadata.pop("image")
            for key, proof in fields.items():
                metadata.setdefault(key, proof)
            if attempted:
                hotel["enrichedAt"] = int(time.time())
            self.db.execute("UPDATE hotel_catalog SET data = ? WHERE object_id = ?", (encode(hotel), object_id))
            return metadata

    def begin(self, identity, snapshot):
        self.db.execute("""
            INSERT INTO hotel_diagnostics (client_id, task_id, initial_catalog) VALUES (?, ?, ?)
            ON CONFLICT DO NOTHING
        """, (*identity, encode(snapshot)))
        row = self.db.execute("SELECT initial_catalog FROM hotel_diagnostics WHERE client_id = ? AND task_id = ?",
                              identity).fetchone()
        return json.loads(row[0])

    def mark_rate_search(self, country, object_id, dates):
        with self.db.transaction():
            self.lock(country)
            row = self.db.execute("SELECT data FROM hotel_catalog WHERE object_id = ?", (object_id,)).fetchone()
            if row is not None:
                data = json.loads(row[0])
                data["rateSearchDates"] = sorted(set(data.get("rateSearchDates", ())) | {dates})
                self.db.execute("UPDATE hotel_catalog SET data = ? WHERE object_id = ?", (encode(data), object_id))

    def focus_counts(self, work):
        return {(object_id, gap): count for object_id, gap, count in self.db.execute("""
            SELECT object_id, gap, COUNT(*) FROM hotel_focus WHERE client_id = ? AND fingerprint = ?
            GROUP BY object_id, gap
        """, work).fetchall()}

    def record_focus(self, work, task_id, object_id, gap, checked):
        self.db.execute("""
            INSERT INTO hotel_focus VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id, fingerprint, task_id, object_id, gap) DO UPDATE SET checked = excluded.checked
        """, (*work, task_id, object_id, gap, int(checked)))

    def checks(self, identity, object_id):
        rows = self.db.execute("""
            SELECT h.checks FROM hotel_checks h JOIN tasks t ON t.client_id = h.client_id AND t.task_id = h.task_id
            WHERE h.client_id = ? AND h.object_id = ? AND (t.result IS NOT NULL OR h.task_id = ?)
            ORDER BY CASE WHEN h.task_id = ? THEN 0 ELSE 1 END, t.created_at DESC LIMIT 12
        """, (identity[0], object_id, identity[1], identity[1])).fetchall()
        return [check for row in rows for check in json.loads(row[0])]

    def save_checks(self, identity, object_id, checks):
        row = self.db.execute("SELECT checks FROM hotel_checks WHERE client_id = ? AND task_id = ? AND object_id = ?",
                              (*identity, object_id)).fetchone()
        prior = json.loads(row[0]) if row else []
        merged = list({encode(check): check for check in prior + checks}.values())
        self.db.execute("""
            INSERT INTO hotel_checks (client_id, task_id, object_id, checks) VALUES (?, ?, ?, ?)
            ON CONFLICT(client_id, task_id, object_id) DO UPDATE SET checks = excluded.checks
        """, (*identity, object_id, encode(merged)))

    def details(self, identity):
        row = self.db.execute("SELECT outcome FROM hotel_diagnostics WHERE client_id = ? AND task_id = ?",
                              identity).fetchone()
        attempts = self.db.records("""
            SELECT attempt, kind, step, duration_ms, request_bytes, output_reserved, usage, error, billable, finish_reason
            FROM hotel_attempts WHERE client_id = ? AND task_id = ? ORDER BY attempt
        """, identity)
        if row is None and not attempts:
            return None
        seen = set()
        for attempt in attempts:
            step = attempt.pop("step")
            attempt["retry"] = step in seen
            seen.add(step)
            attempt["usage"] = json.loads(attempt["usage"]) if attempt["usage"] else None
            if attempt["duration_ms"] is None:
                attempt["error"] = "interrupted"
        counts = {kind: sum(attempt["kind"] == kind for attempt in attempts) for kind in ("search", "fetch", "flash", "fx")}
        usage = {}
        for field in ("inputTokens", "outputTokens", "totalTokens"):
            observed = [item["usage"][field] for item in attempts if field in (item["usage"] or {})]
            usage[field] = sum(observed) if observed or not counts["flash"] else None
        return {**(json.loads(row[0]) if row and row[0] else {}),
                "attempts": attempts, "calls": counts, "usage": usage,
                "enrichmentCalls": {kind: sum(item["kind"] == "enrich_" + kind for item in attempts)
                                    for kind in ("search", "fetch")},
                "sourceCalls": {kind: sum(item["kind"] == kind for item in attempts)
                                for kind in ("geocode", "places", "russhotels")},
                "usageIncomplete": any(item["kind"] == "flash" and not all(
                    name in (item["usage"] or {}) for name in usage) for item in attempts),
                "retries": sum(item["retry"] for item in attempts)}


def merge_hotel(hotel, candidate):
    hotel["names"] = sorted(set(hotel["names"]) | set(candidate.get("names", ())) | {normalized(candidate["name"])})
    for key in ("address", "district", "stars", "coordinates", "imageUrl"):
        if hotel[key] is None:
            hotel[key] = candidate[key]
    hotel["locationAliases"] = sorted(set(hotel.get("locationAliases", ())) | set(candidate.get("locationAliases", ())))
    hotel["rates"].update(candidate["rates"])
    if candidate.get("sources"):
        hotel["sources"] = sorted(set(hotel.get("sources", ())) | set(candidate["sources"]))
    if candidate.get("metadata"):
        hotel["metadata"] = {**candidate["metadata"], **hotel.get("metadata", {})}
    if candidate.get("enrichedAt"):
        hotel["enrichedAt"] = max(hotel.get("enrichedAt", 0), candidate["enrichedAt"])
    hotel["discovery"] = sorted(set(hotel.get("discovery", ())) | set(candidate.get("discovery", ())))
    hotel["providerIds"] = {**hotel.get("providerIds", {}), **candidate.get("providerIds", {})}
    for key in ("publicUrl", "website", "lodgingType"):
        if not hotel.get(key) and candidate.get(key):
            hotel[key] = candidate[key]
    for key in ("facts", "availability"):
        hotel[key] = list({encode(item): item for item in [*hotel.get(key, ()), *candidate.get(key, ())]}.values())
    hotel["rateSearchDates"] = sorted(set(hotel.get("rateSearchDates", ())) | set(candidate.get("rateSearchDates", ())))


def proximity(lat, lon, other_lat, other_lon):
    delta_lon = (lon - other_lon + 180) % 360 - 180
    return 111 * math.hypot(lat - other_lat, delta_lon * math.cos(math.radians((lat + other_lat) / 2)))


def same_address(first, second):
    left, right = first["address"], second["address"]
    return bool(left and right and (address_key(left) == address_key(right) or
                ((left_key := street_address_key(left)) is not None and left_key == street_address_key(right))))


def street_address_key(value):
    # Russian suppliers place the street type on either side of its name.
    if re.search(r"\d\s*[/–-]\s*\d", value):
        return None
    street = r"(?:ул(?:ица)?|проспект|пер(?:еулок)?|наб(?:ережная)?)"
    parts = [normalized(s) for s in value.split(",")]
    for index, part in enumerate(parts):
        if not re.search(rf"\b{street}\b", part):
            continue
        text = " ".join(parts[index:index + 2])
        match = re.search(rf"(?:\b{street}\s+([^\d]+?)|([^\d]+?)\s+{street})\s+(?:дом\s+|д\s+)?"
                          r"(\d+[а-яa-z]?(?:\s+(?:корпус|корп|строение|стр)\s+\w+)?)\b", text)
        if match:
            return (match[1] or match[2]).strip(), match[3]
    return None


def address_key(value):
    words = {"ул": "улица", "пр": "проезд", "корп": "корпус", "стр": "строение", "st": "street", "rd": "road"}
    address = normalized(value)
    if re.search(r"\b(?:kazan|казань)\b", address):
        address = re.sub(r"\b(?:republic of tatarstan|republic tatarstan|республика татарстан|россия|russia)\b", "", address)
        address = re.sub(r"\b[0-9]{6}\b", "", address)
        address = re.sub(r"\b(?:peterburgskaia|peterburgskaya|peterburg|петербургская)\b", "peterburgskaya", address)
        address = re.sub(r"\bказань\b", "kazan", address)
        address = re.sub(r"\bулица\b", "street", address)
    address = " ".join(words.get(word, word) for word in address.split())
    # An address can list the city and street in a different order. Preserve the
    # qualifier on a building number so adjacent branches do not merge.
    address = re.sub(r"\b(дом|д|корпус|строение)\s+(\w+)",
                     lambda match: match[2] if match[1] in ("дом", "д") else match[1] + ":" + match[2], address)
    return sorted(address.split())


def same_name(first, second):
    left = {name_tokens(name) for name in (*first.get("names", ()), normalized(first["name"]))}
    right = {name_tokens(name) for name in (*second.get("names", ()), normalized(second["name"]))}
    return bool((left & right) - {frozenset()})


def name_tokens(name):
    return frozenset(re.sub(r"\b(?:hotel|hôtel|отель|гостиница|хостел|hostel|гостевой дом|guest house)\b", "", name).split())


def conflicting_location(first, second):
    if first["address"] and second["address"] and not same_address(first, second):
        return True
    return conflicting_coordinates(first, second)


def property_provider_ids(hotel):
    ids = dict(hotel.get("providerIds", {}))
    identity = provider_identity(hotel["identity"]["sourceUrl"]) if hotel.get("identity") else None
    if identity:
        ids.setdefault(*identity)
    return ids


def conflicting_coordinates(first, second):
    left, right = first["coordinates"], second["coordinates"]
    return bool(left and right and proximity(left["latitude"], left["longitude"], right["latitude"], right["longitude"]) > 0.2)


def same_hotel(first, second):
    ids = property_provider_ids(first)
    other = property_provider_ids(second)
    if ids.keys() & other.keys():
        if any(ids[key] != other[key] for key in ids.keys() & other.keys()):
            return False
        # Provider localization can change the full address. Coordinates and
        # recognizable conflicting street/house components still veto a merge.
        left, right = first.get("address"), second.get("address")
        a, b = street_address_key(left) if left else None, street_address_key(right) if right else None
        return not (a and b and a != b or conflicting_coordinates(first, second))
    if not same_name(first, second) or conflicting_location(first, second):
        return False
    left, right = first["coordinates"], second["coordinates"]
    return same_address(first, second) or bool(left and right and
        proximity(left["latitude"], left["longitude"], right["latitude"], right["longitude"]) < 0.05)

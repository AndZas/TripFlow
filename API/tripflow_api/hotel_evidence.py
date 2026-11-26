import ipaddress
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from babel import Locale
from babel.numbers import get_currency_precision, list_currencies
from pydantic import Field, StringConstraints, TypeAdapter, ValidationError

from .hotel_tools import FX_URL, SearchInterrupted
from .preference_model import StrictModel
from .preferences import encode
from .schemas import HttpsUrl


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Quote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=950)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
CLOCK = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.][0-5]\d(?!\d)")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_WORDS = re.compile(r"weekends?|weekdays?|понедель|вторник|сред[ау]|четверг|пятниц|суббот|воскрес|будн|выходн|[月火水木金土日]曜", re.I)
OCCUPANCY = re.compile(r"\bsingle[- ](?:bedroom|use|occupancy|room)\b|\|\s*single\s*\||(?:1|one) (?:adult|guest|person)\b|"
                       r"одномест|один взросл|одного гост|вместимость\s*[—–:-]?\s*1\s*место|"
                       r"1\s*(?:гост(?:ь|я)|человек[а]?|взросл\w*|名|人)|シングル|一人|"
                       r"einzelzimmer|chambre individuelle|habitación (?:[\w-]+\s+){0,3}individual|camera singola|"
                       r"tek kişilik|phòng đơn|1\s*người lớn", re.I)
SINGLE_TITLE = re.compile(r"^[#*| \t]*(?:single(?: room)?|einzelzimmer|individuelle|individual)[*| \t]*$", re.I | re.M)
PRIVATE_ROOM = re.compile(r"\b(?:private|double|twin|superior|deluxe|standard|family)\s+(?:double\s+|twin\s+)?room\b|"
                          r"\b(?:private|superior|deluxe|family)\s+suite\b|\b(?:doppelzimmer|chambre double|habitación doble|camera doppia|özel oda|"
                          r"çift kişilik oda|phòng đôi)\b|(?:отдельн|двухместн|стандартн)\w*\s+номер|"
                          r"за\s+(?:весь\s+)?номер|per room(?:\b|\s)", re.I)
MULTIPLE = re.compile(r"\b[2-9]\s*(?:adults?|guests?|persons?|people)\b|double occupancy|"
                      r"двухмест|[2-9]\s*(?:гост[яей]|взросл|名|人)", re.I)
ROOM_UNIT = re.compile(r"\b(?:room|suite)\b|номер|zimmer|chambre|habitación|camera|oda\b|phòng|客室|個室|房间", re.I)
SHARED_BED = re.compile(r"койк|кровать в (?:общ|многомест)|bed in (?:an? )?(?:\w+[- ]?){0,4}dorm|"
                        r"\b\d+\s*[- ]\s*bed\s+dorm(?:itory)?\b|per bed|за (?:одно )?место|"
                        r"(?:shared|dormitory) room", re.I)
SHARED_ROOM_HEADING = re.compile(r"^(?:[-*#\s]*)(?:(?:\d+\s*)?bed in\b|(?:\d+[- ]bed )?dorm(?:itory)?\b|"
                                 r"shared room\b|койк\w*|кровать в (?:общ|многомест))", re.I)
NIGHT = re.compile(r"per (?:room per )?night|nightly|[/／]\s*night|(?:\bза\s*|\bв\s+|/)\s*(?:(?:одну|1)\s*)?(?:ноч[ьи]|сутки|сут\.(?!\w))|"
                   r"1\s*泊|一泊|每晚|每夜|(?:pro|je) nacht|par nuit|por noche|a notte|gecelik|gece başına|mỗi đêm", re.I)
STAY = re.compile(r"per stay|total|whole stay|за (?:весь )?период|за проживание|итого|泊分|合計|合计|gesamt", re.I)
HOTEL_WORD = re.compile(r"hotel|hôtel|hosped|inn\b|ryokan|lodge|resort|отел|гостиниц|hostel|guest[ -]?house|хостел|гостев\w+\s+дом|общежити|motel|ホテル|旅館|酒店|宾馆|โรงแรม", re.I)
TRACKING = {"gclid", "yclid", "fbclid", "msclkid"}
PRICE_FORMAT = re.compile(r"\d+(?:[ ,.  ]\d{3})*(?:[.,]\d{1,2})?")
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
DATE_LITERAL = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2}\s+(?:" +
                          "|".join(MONTHS) + r")\s+\d{4})\b", re.I)
OBSERVATION = re.compile(r"(?:выгодн\w*|минимальн\w*|лучш\w*)\s+цена\s+на|price (?:observed|found) (?:on|for)", re.I)
OFFER_PERIOD = re.compile(r"выбранн\w* (?:период|дат)|цены? на дат|даты заезда|selected dates|stay dates|"
                          r"your dates|check.in date|対象期間|宿泊日", re.I)
SEASON_PERIOD = re.compile(r"(?:тариф|прайс|цены).{0,45}(?:действу|период|сезон)|"
                           r"(?:tariff|rates?).{0,45}(?:valid|season)|valid from|有効期間", re.I)
RATE_DATES = (("checkin", "checkout"), ("check_in", "check_out"), ("checkin_date", "checkout_date"),
              ("arrival", "departure"), ("arrival_date", "departure_date"),
              ("public_filter_checkin_date", "public_filter_checkout_date"))
NO_MEALS = re.compile(r"без (?:питания|завтрака)|(?:питание|завтрак) не включ[её]н\w*|"
                      r"(?:breakfast|meals?) (?:not included|excluded)|room only|素泊まり", re.I)
NONREFUNDABLE = re.compile(r"невозврат\w*|не возвраща\w*|не подлежит возврату|non[ -]?refundable|返金不可", re.I)
INCLUDED_BREAKFAST = re.compile(r"(?:включ[её]н\w*\s+завтрак|завтрак (?:включ[её]н\w*|в стоимости)|breakfast included)", re.I)
FREE_CANCELLATION = re.compile(r"бесплатн\w* отмен\w*|free cancellation", re.I)
OPTIONAL_BREAKFAST = re.compile(r"(?:завтрак(?: доступен)? за доплату|breakfast (?:is )?available for an? (?:extra )?fee)", re.I)
PACKAGE = re.compile(r"авиаперел[её]т|тур\s+с\s+перел[её]том|airfare|flight included", re.I)
POLICIES = (("no_meals", NO_MEALS), ("nonrefundable", NONREFUNDABLE), ("breakfast_included", INCLUDED_BREAKFAST),
            ("free_cancellation", FREE_CANCELLATION), ("breakfast_extra", OPTIONAL_BREAKFAST))
PAID_RESTRICTION = re.compile(r"доплат|обязательн\w* сбор|только для|членств|участник\w* программ|"
                              r"members?\b|residents? only|surcharge|fees? (?:apply|required|excluded)|"
                              r"(?:tax(?:es)?|НДС) (?:not included|не включ)|payable separately", re.I)
LIMITED = re.compile(r"\b(?:minimum|maximum|only|weekdays?|weekends?)\b|только|будн|выходн|限定|平日|休日", re.I)
ROOM_HEADING = re.compile(r"^(?:#{1,6}\s+|\*{2})|^(?:(?:\w+\s+){0,2}(?:одноместн|двухместн)\w*\s+номер)|"
                          r"^(?:номер\b|одноместн|двухместн|апартамент|сингл\b|"
                          r"(?:single|double|twin|triple|deluxe|standard|superior|family|private)\b)", re.I)
CURRENCY_CODES = frozenset(list_currencies())
CURRENCY_SIGNS = {
    "BYN": r"\bбел(?:\.|\b)\s*руб(?:\.|л\w*)?|\bбелорусск\w*\s+рубл\w*",
    "RUB": r"₽|(?<!бел\. )(?<!бел )\bруб(?:\.|л\w*)?",
    "EUR": "€", "GBP": "£", "JPY": "円", "CNY": "元", "UAH": r"₴|грн\.?", "AED": r"د\.إ",
    "USD": r"\bUS\s*\$", "CAD": r"\bCA\s*\$", "AUD": r"\bAU\s*\$",
}
CURRENCY_MARK = (r"(?<![A-Za-z])(?-i:" + "|".join(sorted(CURRENCY_CODES)) + r")(?![A-Za-z])|"
                 + "|".join(CURRENCY_SIGNS.values()) + r"|[$¥￥]|dirhams?")
PRICE_MARK = re.compile(rf"\d\s*(?:{CURRENCY_MARK})|(?:{CURRENCY_MARK})\s*\d", re.I)
FROM_PRICE = re.compile(r"\b(?:from|desde|à partir de|ab|da)\s*(?:(?:US|CA|AU)?[€£¥$]|[A-Z]{3}\s*)?\d|от\s*\d|から|起", re.I)
PRICE_HEADER = re.compile(r"цен[аы]|стоимость|тариф|прайс|currency|price|rates?", re.I)
VARIABLE_PRICE = re.compile(
    r"(?:цена|стоимость|тариф\w*)\s+(?:может\s+(?:измен\w*|меняться)|меняется|зависит)"
    r"(?:\s+от\s+(?:загрузки(?:\s+гостиницы)?|дат[ы]?\s+(?:заезда|бронирования)|сезона))?"
    r"(?:\s*,?\s*и\s+может\s+(?:измен\w*|меняться)(?:\s+в\s+зависимости\s+от\s+дат[ы]?\s+бронирования)?)?"
    r"|(?:prices?|rates?)\s+(?:may\s+vary|subject\s+to\s+change)", re.I)

PUBLIC_URL = TypeAdapter(HttpsUrl)
IMAGE_EXCLUDED = re.compile(r"logo|logotype|favicon|sprite|placeholder|badge|логотип|эмблем", re.I)
MULTI_ADDRESS = re.compile(r"\bквартиры\b|\b(?:multiple|several) apartments\b", re.I)
FACT_TOPICS = {"breakfast", "check-in", "checkout", "transport", "parking", "accessibility", "room", "amenities", "policy"}


class Citation(StrictModel):
    source: Annotated[int, Field(gt=0)]
    quote: Quote


class Rate(Citation):
    amount: Annotated[str, StringConstraints(pattern=r"^\d{1,12}(\.\d{1,4})?$")]
    currency: Currency
    basis: Literal["room_night", "room_stay", "group_night", "group_stay"]
    kind: Literal["published", "from", "range"]
    upper: Annotated[str, StringConstraints(pattern=r"^\d{1,12}(\.\d{1,4})?$")] | None = None
    start: str | None = None
    end: str | None = None
    rooms: Annotated[int, Field(gt=0)] = 1
    tariff: Text | None = None
    minNights: Annotated[int, Field(gt=0)] | None = None
    maxNights: Annotated[int, Field(gt=0)] | None = None
    weekdays: Annotated[list[Annotated[int, Field(ge=0, le=6)]], Field(max_length=7)] | None = None
    caveat: Text | None = None
    block: int | None = None
    roomQuote: Quote | None = None
    roomType: Literal["single", "private", "shared"] | None = None
    support: Annotated[list[Quote], Field(max_length=5)] = Field(default_factory=list)


class Fact(Citation):
    label: Text
    value: Text
    rate: Annotated[int, Field(ge=0)] | None = None


class ConditionCheck(Citation):
    condition: Annotated[int, Field(ge=0)]
    verdict: Literal["confirmed", "refuted"]
    rate: Annotated[int, Field(ge=0)] | None = None
    weekdays: Annotated[list[Annotated[int, Field(ge=0, le=6)]], Field(max_length=7)] | None = None
    dayBasis: Literal["arrival", "stay"] | None = None
    start: str | None = None
    end: str | None = None
    contingent: bool = False


class Availability(Citation):
    start: str | None = None
    end: str | None = None


class Candidate(StrictModel):
    name: Text
    identity: Citation
    city: Citation | None = None
    address: Citation | None = None
    district: Citation | None = None
    stars: Citation | None = None
    coordinates: Citation | None = None
    image: Citation | None = None
    availability: Annotated[list[Availability], Field(max_length=8)] = Field(default_factory=list)
    rates: Annotated[list[Rate | None], Field(max_length=8)] = Field(default_factory=list)
    facts: Annotated[list[Fact], Field(max_length=12)] = Field(default_factory=list)
    checks: Annotated[list[ConditionCheck], Field(max_length=24)] = Field(default_factory=list)


def normalized(value):
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def contains(value, text):
    phrase = normalized(value)
    return bool(phrase and f" {phrase} " in f" {normalized(text)} ")


def name_matches(name, text):
    if contains(name, text):
        return True
    # East Asian names can appear without whitespace or punctuation after the property name.
    if any("\u3040" <= char <= "\u9fff" for char in name):
        return normalized(name) in normalized(text)
    return False


PROPERTY_WORDS = re.compile(r"\b(?:отел(?:ь|я|ю|ем|е)|гостиниц[аыиеу]|hotel|hôtel)\b")
CITY_VARIANTS = ({"казань", "казани", "kazan"}, {"київ", "киев", "києві", "киеве", "kyiv", "kiev"})


def hotel_name_matches(name, text):
    if name_matches(name, text):
        return True
    own = normalized(PROPERTY_WORDS.sub(" ", normalized(name)))
    return bool(own) and own not in ("grand", "central", "hotel", "inn", "отель") and contains(own, text)


def city_aliases(destination, aliases=()):
    selected = normalized(destination.city)
    return (destination.city, *aliases, *(name for group in CITY_VARIANTS if selected in group for name in sorted(group)))


def source_url(raw):
    try:
        url = urlsplit(raw)
        host = url.hostname or ""
        if (url.scheme != "https" or "." not in host or url.username is not None or url.password is not None or
                url.port not in (None, 443) or host.endswith((".local", ".internal", ".localhost"))):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        query = sorted((key, value) for key, value in parse_qsl(url.query, keep_blank_values=True)
                       if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING)
        canonical = urlunsplit(("https", url.netloc.casefold(), url.path or "/", urlencode(query), ""))
        canonical_host = PUBLIC_URL.validate_python(canonical).host
        if canonical_host != host:
            try:
                if not ipaddress.ip_address(canonical_host).is_global:
                    return None
            except ValueError:
                pass
        return canonical
    except (ValueError, TypeError, UnicodeError):
        return None


def provider_identity(url):
    """IDs are comparable only inside the same provider's property namespace."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    queries = parse_qsl(parsed.query)
    if host == "trip.com" or host.endswith(".trip.com"):
        path_id = re.search(r"(?:^|-)hotel-detail-(\d+)(?:/|$)", parsed.path, re.I)
        fields = {value for key, value in queries if key.casefold() == "hotelid"}
        ids = fields | ({path_id[1]} if path_id else set())
        if len(ids) == 1:
            value = next(iter(ids))
            if re.fullmatch(r"\d{3,16}", value) and (path_id or parsed.path.rstrip("/") == "/hotels/detail"):
                return "trip.com", value
    if host == "booking.com" or host.endswith(".booking.com"):
        match = re.fullmatch(r"/hotel/([a-z]{2})/([\w%-]+)(?:\.[\w-]+)?\.html", parsed.path, re.I)
        if match:
            return "booking.com", "/".join(match.groups()).casefold()
    return None


def provider_city(url):
    identity = provider_identity(url)
    if not identity or identity[0] != "trip.com":
        return ""
    parts = urlsplit(url)
    cities = {normalized(value) for key, value in parse_qsl(parts.query) if key.casefold() == "cityenname"}
    path = re.search(r"/hotels/([^/]+)-hotel-detail-\d+(?:/|$)", parts.path, re.I)
    if path:
        cities.add(normalized(path[1]))
    return next(iter(cities)) if len(cities) == 1 else ""


ROOM_ROUTES = {"rooms", "habitaciones", "zimmer", "chambres", "camere", "odalar", "nomera", "accommodation"}


def room_site(url):
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").casefold().split("/")
    if parts[-1] not in ROOM_ROUTES:
        return None
    prefix = parts[:-1]
    if prefix and re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", prefix[0]):
        prefix = prefix[1:]
    return (parsed.hostname or "").removeprefix("www."), tuple(prefix)


def excerpt(text, terms, maximum=2600):
    if len(text) <= maximum:
        return text
    lines = text.splitlines()
    # Keep contiguous blocks including the heading and neighboring tariff rows.
    blocks = ["\n".join(lines[i:i + 8]) for i in range(0, len(lines), 6)]
    ranked = sorted(enumerate(blocks), key=lambda row: (
        row[0] != 0,
        -sum(term in row[1].casefold() for term in terms),
        row[0],
    ))
    used, chosen = 0, []
    for index, block in ranked:
        block = block[:maximum] if index == 0 else block
        if used + len(block) + 6 <= maximum + (6 if not used else 0):
            chosen.append((index, block))
            used += len(block) + 6
    return "\n[…]\n".join(block for _, block in sorted(chosen))


def verified(citation, sources, name):
    if citation is None:
        return None
    page = sources.get(citation.source)
    if not page or not hotel_name_matches(name, page["heading"]):
        return None
    # Use the exact text sent to the model. A quote cannot span omitted passages.
    quote = " ".join(citation.quote.split())
    blocks = [*page["text"].split("\n[…]\n"), *page.get("visibleOffers", ())]
    if not any(quote in " ".join(block.split()) for block in blocks):
        return None
    return {"sourceUrl": page["url"], "quote": citation.quote}


def currency_pattern(currency, country):
    symbols = dict(CURRENCY_SIGNS)
    if country == "AE":
        symbols["AED"] += r"|\bdirhams?\b"
    if country in ("JP", "CN"):
        symbols["JPY" if country == "JP" else "CNY"] += "|[¥￥]"
    dollar = {"US": "USD", "CA": "CAD", "AU": "AUD", "NZ": "NZD", "SG": "SGD"}.get(country)
    if dollar:
        symbols[dollar] = "|".join(filter(None, (symbols.get(dollar), r"(?<![\w$])\$")))
    code = rf"(?<![A-Za-z])(?-i:{currency})(?![A-Za-z])"
    return rf"(?:{code}|{symbols[currency]})" if currency in symbols else code


PRICE_NUMBER = r"[0-9](?:[0-9., \u00a0\u202f]*[0-9])?"


def source_decimal(literal, currency):
    """Parse a written amount without letting the extracted value select its interpretation."""
    text = re.sub(r"[\u00a0\u202f]", " ", literal)
    precision = get_currency_precision(currency)
    interpretations = set()
    for mark in ("", ".", ","):
        integer, fractional = text, ""
        if mark:
            if text.count(mark) != 1:
                continue
            integer, fractional = text.split(mark)
            if not fractional.isascii() or not fractional.isdigit() or len(fractional) > precision:
                continue
        if not re.fullmatch(r"[0-9]+|[1-9][0-9]{0,2}([ .,])[0-9]{3}(?:\1[0-9]{3})*", integer):
            continue
        interpretations.add(Decimal(re.sub(r"[ .,]", "", integer) + ("." + fractional if fractional else "")))
    return next(iter(interpretations)) if len(interpretations) == 1 else None


def written_currencies(text, country):
    tokens = set(re.findall(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])", text)) & CURRENCY_CODES
    for currency in {*CURRENCY_SIGNS, "NZD", "SGD"}:
        if re.search(currency_pattern(currency, country), text, re.I):
            tokens.add(currency)
    if "BYN" in tokens and not re.search(r"₽|\bRUB\b", text):
        tokens.discard("RUB")
    return tokens


def quoted_amounts(currency, quote, country, header=""):
    if currency not in CURRENCY_CODES:
        return []
    currencies = written_currencies(quote, country)
    if currencies - {currency}:
        return []
    if not currencies and written_currencies(header, country) == {currency}:
        literals = re.fullmatch(r"\s*\|?\s*[$¥￥]?\s*(" + PRICE_NUMBER + r")(?:\s*[-–—]\s*("
                                + PRICE_NUMBER + r"))?\s*[$¥￥]?\s*(?:\|?\s*(.*?))?\s*\|?\s*", quote, re.I)
        if literals and (not literals[3] or NIGHT.search(literals[3]) or STAY.search(literals[3])):
            return [(source_decimal(value, currency), value) for value in literals.groups()[:2] if value]
    unit, number = currency_pattern(currency, country), PRICE_NUMBER
    edge = rf"(?<![\d.,]){number}(?![\d.,])"
    pair = rf"({edge})\s*[-–—~〜]\s*({edge})"
    for pattern in (rf"{unit}\s*{pair}", rf"{pair}\s*{unit}", rf"{unit}\s*({edge})\s*[-–—~〜]\s*{unit}\s*({edge})",
                    rf"({edge})\s*{unit}\s*[-–—~〜]\s*({edge})\s*{unit}"):
        matches = list(re.finditer(pattern, quote, re.I))
        if matches:
            return [(source_decimal(value, currency), value) for value in matches[0].groups()] if len(matches) == 1 else []
    written = list(dict.fromkeys(match[1] for pattern in (rf"{unit}\s*({edge})", rf"({edge})\s*{unit}")
                                for match in re.finditer(pattern, quote, re.I)))
    return [(source_decimal(value, currency), value) for value in written]


def iso_day(value):
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise ValueError
    return day


def day_in(value, quote):
    day = iso_day(value)
    forms = [value, day.strftime("%d.%m.%Y"), day.strftime("%d/%m/%Y"), day.strftime("%m/%d/%Y"),
             f"{day.year}年{day.month}月{day.day}日", day.strftime("%B %d, %Y").replace(" 0", " ")]
    forms.append(f"{day.day} {MONTHS[day.month - 1]} {day.year}")
    return any(form.casefold() in quote.casefold() for form in forms)


@lru_cache(maxsize=1)
def country_names():
    names = {"usa": "US", "u s a": "US", "uk": "GB", "рф": "RU", "российская федерация": "RU"}
    codes = set()
    for language in ("en", "ru", "fr", "de", "es", "pt", "it", "ja", "zh", "ko", "tr", "ar", "uk"):
        for code, label in Locale.parse(language).territories.items():
            if len(code) == 2 and code not in {"EU", "UN", "ZZ", "QO", "EZ"}:
                codes.add(code)
                if len(normalized(label)) > 2:
                    names.setdefault(normalized(label), code)
    return names, codes


AMBIGUOUS = {
    "paris", "париж", "springfield", "спрингфилд", "london", "лондон", "cambridge", "кембридж",
    "saint petersburg", "st petersburg", "сент питерсберг", "portland", "портленд", "vancouver", "ванкувер",
    "richmond", "ричмонд", "manchester", "манчестер", "birmingham", "бирмингем", "sydney", "сидней",
    "melbourne", "мельбурн", "moscow", "rome", "рим", "athens", "афины", "florence", "флоренция",
}
US_REGIONS = frozenset(("texas", "florida", "illinois", "missouri", "massachusetts", "ohio", "virginia",
                        "kentucky", "pennsylvania", "tennessee", "arkansas", "idaho", "oregon", "alabama",
                        "техас", "флорида", "иллинойс", "миссури", "массачусетс"))


def location_issue(city_evidence, address, coordinates, destination, aliases=(), *, same_country_ambiguity=False):
    city_names = city_aliases(destination, aliases)
    if not any(name_matches(name, city_evidence) for name in city_names):
        return "city_mismatch"
    branch_address = bool(address and (re.search(r"\d|\b(?:street|road|avenue|rue|avenida|straße|улица|проспект)\b",
                                                address, re.I)))
    evidence = [city_evidence, *([address] if branch_address else [])]
    names, codes = country_names()
    found = set()
    city_keys = {normalized(name) for name in city_names}
    for line in evidence:
        for segment in re.split(r"[,;|\n]", line):
            value = segment.strip(" .–—")
            key = normalized(value)
            if key in city_keys:
                continue
            if key in US_REGIONS:
                found.add("US")
            if key in names:
                found.add(names[key])
            elif value in codes:
                found.add(value)
            else:
                # Many formats put the country after the town without a comma.
                for name in city_names:
                    city = normalized(name)
                    if city and f" {city} " in f" {key} ":
                        tail = key.rsplit(city, 1)[1].strip()
                        if tail in names:
                            found.add(names[tail])
    if found - {destination.countryCode}:
        return "country_mismatch"
    if coordinates:
        lat, lon = coordinates["latitude"], coordinates["longitude"]
        if abs(lat - destination.latitude) > 0.35 or abs((lon - destination.longitude + 180) % 360 - 180) > 0.45:
            return "location_mismatch"
        return None
    # For two known locations with the same name inside a country, country alone is insufficient.
    if same_country_ambiguity or (normalized(destination.city) in AMBIGUOUS and not (found and branch_address)):
        return "location_unconfirmed"
    return None


def offer_blocks(text):
    """Keep the room heading, price row and its nearby notes together."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blocks, heading, notes, currency_header = [], None, [], None
    common_notes = [line for line in lines[:70] if VARIABLE_PRICE.search(line)
                    and not PAID_RESTRICTION.search(line)][:1]
    def room_heading(line):
        return ROOM_HEADING.search(line) or SHARED_ROOM_HEADING.match(line)

    consumed = -1
    for index, line in enumerate(lines):
        if index <= consumed:
            continue
        is_price = PRICE_MARK.search(line) or (currency_header and (
            NIGHT.search(line) or re.fullmatch(r"\|?\s*[$¥￥]?\s*" + PRICE_NUMBER + r"\s*\|?", line))
            and re.search(r"\d", line))
        if PRICE_HEADER.search(line) and not is_price and written_currencies(line, ""):
            currency_header = line
        if line == "[…]":
            currency_header = None
        if line == "[…]" or (room_heading(line) and not is_price):
            heading, notes = (None if line == "[…]" else line), []
            continue
        if not is_price:
            notes.append(line)
            continue
        following = []
        for offset, neighbor in enumerate(lines[index + 1:index + 4], 1):
            if neighbor == "[…]" or room_heading(neighbor) or PRICE_MARK.search(neighbor):
                break
            if len(neighbor) <= 240 and (
                re.match(r"^(?:за\s|per\s|[/／]|итого)", neighbor, re.I) and (NIGHT.search(neighbor) or STAY.search(neighbor))
                or re.match(r"^(?:\*|\[?\d+\]|примечани|note:|условия тарифа:)", neighbor, re.I)
                or PACKAGE.search(neighbor) or INSTALLMENT.search(neighbor) or SHARED_BED.search(neighbor)
                or OBSERVATION.search(neighbor) or VARIABLE_PRICE.search(neighbor)
                or PAID_RESTRICTION.search(OPTIONAL_BREAKFAST.sub("", neighbor))
            ):
                following.append(neighbor)
                consumed = index + offset
                continue
            break
        before = [note for note in notes if len(note) <= 240 and (OCCUPANCY.search(note) or MULTIPLE.search(note) or
                  DATE_LITERAL.search(note) or NIGHT.search(note) or PAID_RESTRICTION.search(note)
                  or INSTALLMENT.search(note) or SHARED_BED.search(note) or
                  re.search(r"\b1\s+(?:max|single bed)\b", note, re.I) or
                  any(pattern.search(note) for _, pattern in POLICIES))]
        blocks.append("\n".join([*( [currency_header] if currency_header and currency_header != heading else []),
                                 *([heading] if heading else []), *before, line, *following, *common_notes])[:1500])
        # An occupancy note from one priced row cannot be reused for the next row.
        notes = []
        if room_heading(line):
            heading = None
    return blocks


def normalized_day(raw):
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return iso_day(raw).isoformat()
    if words := raw.casefold().split():
        if len(words) == 3 and words[1] in MONTHS:
            return date(int(words[2]), MONTHS.index(words[1]) + 1, int(words[0])).isoformat()
    day, month, year = map(int, re.split(r"[./]", raw))
    return date(year, month, day).isoformat()


def date_pair(values):
    try:
        if len(values) != 2:
            raise ValueError
        start, end = map(normalized_day, values)
        if start >= end:
            raise ValueError
        return start, end
    except (TypeError, ValueError):
        raise RateRejected("unverified_period") from None


def booking_periods(source_url):
    params = {}
    for key, value in parse_qsl(urlsplit(source_url).query, keep_blank_values=True):
        params.setdefault(re.sub(r"[_-]", "", key.casefold()), []).append(value)
    periods = set()
    for start, end in RATE_DATES:
        start, end = start.replace("_", ""), end.replace("_", "")
        if start in params or end in params:
            periods.add(date_pair(params.get(start, []) + params.get(end, [])))
    return periods


def rate_period(rate, evidence, context):
    url_periods = booking_periods(evidence["sourceUrl"])
    fixed, seasonal = set(url_periods), set()
    lines = context.splitlines()
    for index, line in enumerate(lines):
        field = fixed if OFFER_PERIOD.search(line) else seasonal if SEASON_PERIOD.search(line) else None
        if field is None:
            continue
        values = DATE_LITERAL.findall(line)
        # Booking controls for picking future dates are not a displayed dated price.
        if not values and not re.search(r"price|цен|тариф|valid|rates?", line, re.I):
            continue
        if len(values) < 2 and index + 1 < len(lines):
            values += DATE_LITERAL.findall(lines[index + 1])
        if values:
            field.add(date_pair(values))
        elif not url_periods:
            raise RateRejected("unverified_period")
    if len(fixed) > 1 or len(seasonal) > 1:
        raise RateRejected("conflicting_period")
    declared = None
    if rate.start or rate.end:
        declared = date_pair([rate.start, rate.end])
        if not all(day_in(value, context) for value in declared) and declared not in fixed:
            raise RateRejected("unverified_period")
    if fixed:
        period = next(iter(fixed))
        if declared and declared != period or seasonal and not (
                next(iter(seasonal))[0] <= period[0] < period[1] <= next(iter(seasonal))[1]):
            raise RateRejected("conflicting_period")
        return "offer", period
    if rate.basis not in ("room_night", "group_night"):
        if not declared:
            raise RateRejected("unverified_period")
        return "offer", declared
    if seasonal:
        period = next(iter(seasonal))
        if declared and declared != period:
            raise RateRejected("conflicting_period")
        return "seasonal", period
    if declared:
        # An unnamed dated range is safe only for the same dates.
        return "offer", declared
    if DATE_LITERAL.search(evidence["quote"]) and not OBSERVATION.search(evidence["quote"]):
        raise RateRejected("unverified_period")
    return "general", (None, None)


class RateRejected(ValueError):
    pass


def checked_rate(rate, evidence, country, *, offer=None, context=None, rejected=None):
    try:
        return validate_rate(rate, evidence, country, offer, context)
    except RateRejected as error:
        if rejected is not None:
            rejected.append({"reason": str(error), "sourceUrl": evidence["sourceUrl"] if evidence else None})
        return None


ROOM_COUNT = re.compile(
    r"(?<!\d)(\d+|two|three|два|две|двух|три|тр[её]х)\s*(?:(?:отдельн\w+|одноместн\w+|separate|single(?:[- ]occupancy)?)\s+){0,2}(?:номер\w*|rooms?\b|室)", re.I)
PRIVATE_GROUP = re.compile(r"single(?:[- ]occupancy)? rooms|одноместн\w+\s+номер|отдельн\w+\s+номер", re.I)
INSTALLMENT = re.compile(r"installments?|payments? of|per payment|рассроч|плат[её]ж\w*|опла\w+ частями", re.I)


def room_counts(quote):
    words = {"two": 2, "three": 3, "два": 2, "две": 2, "двух": 2, "три": 3, "трех": 3, "трёх": 3}
    return {int(raw) if raw.isdigit() else words[raw] for raw in ROOM_COUNT.findall(quote.casefold())}


def unit_problem(basis, rooms, quote, price_line, *, private=False, overnight=False):
    if PACKAGE.search(quote) or INSTALLMENT.search(quote) or SHARED_BED.search(quote):
        return "unverified_unit"
    counts = room_counts(quote)
    group = basis in ("group_night", "group_stay")
    if group:
        if counts != {rooms} or rooms < 2 or not PRIVATE_GROUP.search(quote):
            return "unverified_occupancy"
    elif rooms != 1 or counts - {1}:
        return "unverified_unit"
    if not (private or OCCUPANCY.search(quote) or SINGLE_TITLE.search(quote) or group and PRIVATE_GROUP.search(quote)):
        return "unverified_occupancy"
    if not (group or private) and MULTIPLE.search(quote):
        return "unverified_occupancy"
    if basis in ("room_night", "group_night"):
        # A one-night query supplies the duration. The offer still has to show a room.
        if overnight and not (ROOM_UNIT.search(quote) or SINGLE_TITLE.search(quote) or PRIVATE_ROOM.search(quote)):
            return "unverified_occupancy"
        stay = STAY.search(quote if basis == "room_night" else re.sub(r"\b(?:total|итого)\b", "", quote, flags=re.I))
        if (not (overnight or NIGHT.search(quote)) or stay or
                re.search(r"per (?:person|guest)|за (?:одного )?(?:человека|гостя)", price_line, re.I)):
            return "unverified_unit"
    elif not STAY.search(quote):
        return "unverified_unit"
    return None


def channel_overnight(url):
    if not provider_identity(url) or provider_identity(url)[0] != "trip.com":
        return False
    try:
        periods = booking_periods(url)
        if len(periods) != 1:
            return False
        start, end = next(iter(periods))
        return (date.fromisoformat(end) - date.fromisoformat(start)).days == 1 and {
            value for key, value in parse_qsl(urlsplit(url).query) if key.casefold() in ("crn", "rooms")
        } == {"1"}
    except RateRejected:
        return False


def rate_header(quote, url):
    header = "\n".join(line for line in quote.splitlines() if PRICE_HEADER.search(line) and not PRICE_MARK.search(line))
    if channel_overnight(url):
        currencies = {value for key, value in parse_qsl(urlsplit(url).query) if key.casefold() in ("curr", "currency")}
        if len(currencies) == 1:
            header += "\n" + currencies.pop()
    return header


def validate_rate(rate, evidence, country, offer, context):
    if not evidence:
        raise RateRejected("missing_rate_quote")
    if rate.support and not offer:
        raise RateRejected("unlinked_rate_quotes")
    quote = offer or rate.quote
    amount = Decimal(rate.amount)
    from_text = FROM_PRICE.search(rate.quote)
    if rate.currency not in CURRENCY_CODES:
        raise RateRejected("unknown_currency")
    url = evidence["sourceUrl"]
    written = quoted_amounts(rate.currency, rate.quote, country, rate_header(quote, url))
    if amount <= 0 or len(written) != (2 if rate.kind == "range" else 1):
        raise RateRejected("unverified_amount")
    if written[0][0] != amount:
        # Resolve only a separator transcription of the same digits in a verified quote.
        canonical, printed = written[0]
        digits = lambda value: re.sub(r"\D", "", value)
        if canonical is None or digits(printed) != digits(rate.amount):
            raise RateRejected("unverified_amount")
        amount = canonical
    if rate.roomType == "shared":
        raise RateRejected("unverified_occupancy")
    if rate.roomQuote and not contains(rate.roomQuote, quote):
        raise RateRejected("unlinked_rate_quotes")
    overnight = channel_overnight(url)
    issue = unit_problem(rate.basis, rate.rooms, quote, rate.quote, overnight=overnight)
    room_context = rate.roomQuote if rate.roomType in ("private", "single") else None
    # A semantic claim still needs a literal category or an offer for a separate room.
    # A generic source title or an unscoped price is insufficient.
    private = bool(issue == "unverified_occupancy" and rate.basis == "room_night" and (
        PRIVATE_ROOM.search(quote) or room_context and room_context in quote.splitlines()
        and len(room_context.split()) >= 2 and quote.splitlines()[0] == room_context
        and not re.search(r"^\s*#|\bbed\b|кроват|lit\b|cama\b|bett\b", room_context, re.I)))
    if private:
        issue = unit_problem(rate.basis, rate.rooms, quote, rate.quote, private=True, overnight=overnight)
    if issue:
        raise RateRejected(issue)
    if from_text and rate.kind == "published":
        raise RateRejected("unverified_amount")
    upper = Decimal(rate.upper) if rate.upper else None
    if rate.kind == "range":
        if upper != written[1][0] and rate.upper and re.sub(r"\D", "", rate.upper) == re.sub(r"\D", "", written[1][1]):
            upper = written[1][0]
        if upper is None or upper < amount or written[1][0] != upper:
            raise RateRejected("unverified_amount")
    if (rate.tariff and not contains(rate.tariff, quote)) or (rate.kind != "range" and rate.upper):
        raise RateRejected("unlinked_rate_quotes")
    for quantity, lower in ((rate.minNights, True), (rate.maxNights, False)):
        if quantity:
            bound = r"minimum|min\.?|at least|от|не менее" if lower else r"maximum|max\.?|at most|до|не более"
            if not re.search(rf"(?:{bound})\s+{quantity}\s*(?:nights?|ноч|сут)", quote, re.I):
                raise RateRejected("rate_restriction")
    weekdays = quoted_weekdays(quote)
    if weekdays is not None and weekdays != set(rate.weekdays or ()):
        raise RateRejected("rate_restriction")
    policies = [label for label, pattern in POLICIES if pattern.search(quote)]
    if {"no_meals", "breakfast_included"}.issubset(policies) or {"nonrefundable", "free_cancellation"}.issubset(policies):
        raise RateRejected("unlinked_rate_quotes")
    remaining = quote
    for _, pattern in POLICIES:
        remaining = pattern.sub("", remaining)
    if (PAID_RESTRICTION.search(remaining) or
            LIMITED.search(remaining) and not any((rate.weekdays, rate.minNights, rate.maxNights))):
        raise RateRejected("rate_restriction")
    variable = next((line for line in quote.splitlines() if VARIABLE_PRICE.search(line)), None)
    if rate.caveat:
        cleaned = VARIABLE_PRICE.sub("", rate.caveat) if variable and contains(rate.caveat, quote) else rate.caveat
        for label, pattern in POLICIES:
            if label in policies:
                cleaned = pattern.sub("", cleaned)
        if re.search(r"\w", re.sub(r"\b(?:и|and|оплата|тариф|ставка)\b", "", cleaned, flags=re.I)) or not (policies or variable):
            raise RateRejected("rate_restriction")
    scope, (start, end) = rate_period(rate, evidence, context or quote)
    try:
        observations = [(normalized_day(day), line) for line in quote.splitlines() if OBSERVATION.search(line)
                        for day in DATE_LITERAL.findall(line)]
    except ValueError:
        raise RateRejected("unverified_period") from None
    if len({day for day, _ in observations}) > 1:
        raise RateRejected("conflicting_period")
    support = rate.support if rate.support else ([offer] if offer and offer != rate.quote else [])
    return {**rate.model_dump(exclude={"source", "support", "block"}), **evidence, "scope": scope,
            "amount": format(amount, "f"), "upper": format(upper, "f") if upper is not None else None,
            "start": start, "end": end, "policies": policies, "support": support,
            "printedAmount": [literal for _, literal in written], "unitQuote": quote,
            "priceLevel": "room_reference" if private else "offer",
            "originalOccupancy": (rate.roomQuote or next((line for line in quote.splitlines()
                                                         if PRIVATE_ROOM.search(line)), None)) if private else None,
            "variableQuote": variable, "roomCategory": rate.tariff or next((
                line.strip("#* |")[:160] for line in quote.splitlines() if OCCUPANCY.search(line)
                and not PRICE_MARK.search(line) and ROOM_HEADING.search(line)), None),
            "observedOn": observations[0][0] if observations else None,
            "periodQuote": observations[0][1] if observations else None}


def quoted_weekdays(quote):
    lower = quote.casefold()
    if re.search(r"weekends?|выходн|土日|休日", lower):
        return {5, 6}
    if re.search(r"weekdays?|будн|平日", lower):
        return set(range(5))
    prefixes = ("понедель", "вторник", "сред", "четверг", "пятниц", "суббот", "воскрес")
    days = {i for i, (en, ru, ja) in enumerate(zip(WEEKDAYS, prefixes, "月火水木金土日"))
            if re.search(rf"\b{en}s?\b|\b{ru}\w*|{ja}曜", lower)}
    return days or (set() if DAY_WORDS.search(lower) else None)


def days_match(days, start, nights):
    return all((start.weekday() + offset) % 7 in days for offset in range(min(nights, 7)))


NO_VACANCY = re.compile(r"no (?:single )?rooms (?:are )?available|sold out|нет свободных (?:одноместных )?номеров|"
                        r"мест нет|все номера заняты|одноместных номеров нет", re.I)
UNCERTAIN_SOLD_OUT = re.compile(r"\b(?:not|never|(?:may|might|could) be)\s+sold out\b", re.I)
VACANCY = re.compile(r"(\d+)\s+(?:separate\s+)?single[- ](?:occupancy\s+)?rooms?\s+(?:are\s+)?available|"
                     r"(?:доступн\w*|свободн\w*|остал\w*)\s+(\d+)\s+одноместн\w+\s+номер\w*|"
                     r"(\d+)\s+(?:свободн\w*|доступн\w*)\s+одноместн\w+\s+номер\w*", re.I)


def availability_proof(row, proof):
    if not proof:
        return None
    quote = proof["quote"]
    try:
        detected = booking_periods(proof["sourceUrl"])
        quoted_dates = DATE_LITERAL.findall(quote)
        if quoted_dates:
            detected.add(date_pair(quoted_dates))
        if len(detected) != 1:
            return None
        start, end = next(iter(detected))
        if row.start and row.start != start or row.end and row.end != end:
            return None
    except RateRejected:
        return None
    unavailable = NO_VACANCY.search(quote) and not UNCERTAIN_SOLD_OUT.search(quote)
    match = VACANCY.search(quote)
    if unavailable and not match:
        return {**proof, "state": "unavailable", "start": start, "end": end, "rooms": None}
    if match and not unavailable:
        rooms = int(next(value for value in match.groups() if value is not None))
        if rooms > 0:
            return {**proof, "state": "available", "start": start, "end": end, "rooms": rooms}
    return None


def availability_for(hotel, trip):
    dates = trip.startDate.isoformat(), trip.endDate.isoformat()
    matches = [item for item in hotel.get("availability", ()) if (item["start"], item["end"]) == dates
               and (item["state"] == "unavailable" or item["rooms"] >= trip.travelers)]
    states = {item["state"] for item in matches}
    if len(states) == 1:
        return matches[0]
    return {"state": "unknown", "start": dates[0], "end": dates[1]}


def rate_quality(rate, trip, nights):
    start, end = trip.startDate.isoformat(), trip.endDate.isoformat()
    if rate.get("scope") not in ("general", "seasonal", "offer"):
        return None
    if rate.get("provider") == "russhotels":
        label = rate.get("providerRoom", "")
        if room_counts(label) - {1} or SHARED_BED.search(label) or INSTALLMENT.search(label):
            return None
    proof = rate.get("unitQuote") or "\n".join([rate["quote"], *rate.get("support", ())])
    if unit_problem(rate["basis"], rate["rooms"], proof, rate["quote"],
                    private=rate.get("priceLevel") == "room_reference", overnight=channel_overnight(rate["sourceUrl"])):
        return None
    if rate["basis"] in ("group_night", "group_stay") and rate["rooms"] != trip.travelers:
        return None
    if "printedAmount" not in rate:
        country = getattr(getattr(trip, "destination", None), "countryCode", "RU")
        amounts = [value for value, _ in quoted_amounts(rate["currency"], rate["quote"], country)]
        expected = [Decimal(rate["amount"])]
        if rate.get("upper"):
            expected.append(Decimal(rate["upper"]))
        if amounts != expected:
            return None
    try:
        dated = booking_periods(rate["sourceUrl"])
    except RateRejected:
        return None
    if dated and (rate["scope"] != "offer" or dated != {(rate["start"], rate["end"])}):
        return None
    if rate["minNights"] and nights < rate["minNights"] or rate["maxNights"] and nights > rate["maxNights"]:
        return None
    if rate["weekdays"] is not None and not days_match(rate["weekdays"], trip.startDate, nights):
        return None
    if rate["scope"] == "offer":
        if (rate["start"], rate["end"]) == (start, end):
            return "dated" if rate["basis"] != "group_stay" or rate["rooms"] == trip.travelers else None
        return "other_period" if rate["basis"] in ("room_night", "group_night") else None
    if rate.get("observedOn"):
        return "other_period"
    if rate["scope"] == "seasonal" and not (rate["start"] <= start and end <= rate["end"]):
        return "other_period" if rate["basis"] in ("room_night", "group_night") else None
    return "published"


def rate_applies(rate, trip, nights):
    return rate_quality(rate, trip, nights) is not None


def rate_context(page, rate, *, details=False):
    pieces = [rate.quote, *rate.support]
    offers = page.get("offers", ())
    # The index is a pointer, not proof. Recheck every safely separated block.
    matches = [offer for offer in offers if all(" ".join(piece.split()) in " ".join(offer.split()) for piece in pieces)]
    if details:
        return len(set(matches))
    if len(set(matches)) > 1:
        # One abbreviated price row can occur under several room headings.
        return None, None
    offer = matches[0] if matches else None
    if not offer and offers:
        return None, None
    context = "\n".join(filter(None, (page.get("priceHeader"), offer or rate.quote)))
    return offer, context


def candidate_fields(row, sources, rejected):
    if not isinstance(row, dict):
        return None
    clean = {key: row.get(key) for key in ("name", "identity")}

    def field(model, item, name):
        if item is None:
            return None
        try:
            return model.model_validate(item)
        except ValidationError:
            if rejected is not None:
                source = item.get("source") if isinstance(item, dict) else None
                page = sources.get(source, {}) if isinstance(source, int) else {}
                rejected.append({"reason": "invalid_rate" if model is Rate else "invalid_optional_field",
                                 "field": name, "sourceUrl": page.get("url"), "name": row.get("name")})
            return None

    for key in ("city", "address", "district", "stars", "coordinates", "image"):
        clean[key] = field(Citation, row.get(key), key)
    for key, model, maximum in (("rates", Rate, 8), ("availability", Availability, 8),
                                ("facts", Fact, 12), ("checks", ConditionCheck, 24)):
        items = row.get(key)
        parsed = [field(model, item, key) for item in items[:maximum]] if isinstance(items, list) else []
        clean[key] = parsed if key == "rates" else [item for item in parsed if item is not None]
    try:
        return Candidate.model_validate(clean)
    except ValidationError:
        return None


def explicit_nightly_rates(source, page, country):
    """Recover a literal room price omitted by extraction from an already linked page."""
    url = page["url"]
    if page.get("stored") or PACKAGE.search(page["heading"]):
        return
    for block in page["offers"][:6]:
        if not (OCCUPANCY.search(block) or SINGLE_TITLE.search(block) or PRIVATE_ROOM.search(block)):
            continue
        if not (NIGHT.search(block) or channel_overnight(url)):
            continue
        header = rate_header(block, url)
        prices = [(line, currency, amounts[0][0])
                  for line in block.splitlines() if PRICE_MARK.search(line) and len(line) <= 950
                  for currency in written_currencies(line, country) or written_currencies(header, country)
                  if len(amounts := quoted_amounts(currency, line, country, header)) == 1 and amounts[0][0]]
        if len(prices) != 1:
            continue
        quote, currency, amount = prices[0]
        if not re.fullmatch(r"\d{1,12}(\.\d{1,4})?", printed := format(amount, "f")):
            continue
        rate = Rate(source=source, quote=quote, amount=printed, currency=currency, basis="room_night",
                    kind="from" if FROM_PRICE.search(quote) else "published")
        offer, context = rate_context(page, rate)
        if context is not None and offer == block:
            yield rate, offer, context


def checked_candidate(row, sources, destination, conditions, *, aliases=(), rejected=None, same_country_ambiguity=False,
                      region_matches=None, region_rejected=None, known_property=None, same_address=None):
    data = candidate_fields(row, sources, rejected)
    if not data:
        return None
    identity = verified(data.identity, sources, data.name)
    heading = sources.get(data.identity.source, {}).get("heading", "")
    if (not identity or not hotel_name_matches(data.name, data.identity.quote) or
            not HOTEL_WORD.search(heading + " " + (data.city.quote if data.city else ""))):
        return None
    # A single ambiguous phrase from a directory is not an object page.
    if re.search(r"\b(?:top \d+|\d+ best|best hotels|hotels near|list of hotels)\b|лучшие отели|список отелей|"
                 r"гостиницы города|гостиниц Москвы", heading, re.I):
        return None

    primary = sources[data.identity.source]
    primary_id = provider_identity(identity["sourceUrl"])
    primary_site = room_site(identity["sourceUrl"])
    cities = city_aliases(destination, aliases)
    address = verified(data.address, sources, data.name)
    own_city = {"sourceUrl": identity["sourceUrl"], "quote": heading}
    raw_city = verified(data.city, sources, data.name)
    known = known_property(data.name, identity["sourceUrl"]) if known_property else None

    def in_city(text):
        return any(name_matches(name, text) for name in cities)

    def local_evidence(text, street=None):
        pair = " ".join(filter(None, (text, street)))
        if region_rejected and region_rejected(pair):
            return "region_mismatch"
        # City presence is evaluated separately. This check catches an explicit conflict.
        issue = location_issue(text, street, None, destination, aliases)
        return issue if issue == "country_mismatch" else None

    def linked(source):
        if source == data.identity.source:
            return True
        page = sources.get(source)
        if not page or not hotel_name_matches(data.name, page["heading"]):
            return False
        url, text = page["url"], page["text"]
        if region_rejected and region_rejected(page["heading"] + " " + url):
            return False
        street = address["quote"] if address and data.address.source == source else None
        if local_evidence(page["heading"], street) or (street and in_city(street) and local_evidence(street)):
            return False
        other_id = provider_identity(url)
        if primary_id and other_id and primary_id[0] == other_id[0]:
            from_city, to_city = provider_city(identity["sourceUrl"]), provider_city(url)
            city_keys = {normalized(name) for name in cities}
            return primary_id == other_id and (
                not (from_city and to_city) or from_city == to_city or {from_city, to_city} <= city_keys)
        if primary_site and primary_site == room_site(url) and in_city(heading) and in_city(page["heading"]):
            return True
        if address and re.search(r"\d", address["quote"]):
            anchor = primary["text"] if data.address.source == source else text
            same_street = contains(address["quote"], anchor) or same_address and any(
                len(line) < 240 and re.search(r"\d", line) and
                same_address({"address": address["quote"]}, {"address": line}) for line in anchor.splitlines())
            if same_street and (in_city(text) or in_city(address["quote"])):
                return True
        if known and (other := known_property(data.name, url)):
            return known["identity"]["sourceUrl"] == other["identity"]["sourceUrl"]
        return False

    def property_evidence(citation):
        if citation and linked(citation.source):
            return verified(citation, sources, data.name)
        return None

    city = None
    if raw_city and data.city and linked(data.city.source):
        city = raw_city
    if address and data.address and not linked(data.address.source):
        address = None
    if not city or not in_city(city["quote"]):
        if address and in_city(address["quote"]):
            city = address
        elif in_city(heading):
            city = own_city
        elif known:
            city = known["cityEvidence"]
    if not city:
        if rejected is not None:
            rejected.append({"reason": "city_unconfirmed", "sourceUrl": identity["sourceUrl"], "name": data.name})
        return None
    district = property_evidence(data.district)
    stars = property_evidence(data.stars)
    star_rating = None
    if stars:
        star_match = re.search(r"(?<!\d)([0-5])\s*[- ]?(?:star|зв[её]зд|つ星|星|★)", stars["quote"], re.I)
        if star_match:
            star_rating = int(star_match[1])
        elif re.search(r"без зв[её]зд|unrated|no star rating", stars["quote"], re.I):
            star_rating = 0
    coordinate_proof = property_evidence(data.coordinates)
    coordinates = None
    if coordinate_proof:
        pair = re.search(r"(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})", coordinate_proof["quote"])
        if pair:
            lat, lon = map(float, pair.groups())
            if abs(lat) <= 90 and abs(lon) <= 180:
                if abs(lat - destination.latitude) > 0.5 or abs((lon - destination.longitude + 180) % 360 - 180) > 0.7:
                    return None
                coordinates = {"latitude": lat, "longitude": lon}
    location = city["quote"]
    if not any(name_matches(name, location) for name in city_aliases(destination, aliases)):
        if address and any(name_matches(name, address["quote"]) for name in city_aliases(destination, aliases)):
            city = address
        elif (not address or not re.search(r"\b(?:г\.|город\s|city of\s)\s*\w+", address["quote"], re.I)) and any(
            name_matches(name, heading) for name in city_aliases(destination, aliases)
        ):
            city = {"sourceUrl": identity["sourceUrl"], "quote": heading}
    regional_text = " ".join((city["quote"], address["quote"] if address else "", identity["sourceUrl"]))
    if region_rejected and region_rejected(regional_text):
        if rejected is not None:
            rejected.append({"reason": "region_mismatch", "sourceUrl": identity["sourceUrl"], "name": data.name})
        return None
    if known and not coordinates:
        coordinates = known["coordinates"]
    regional_proof = region_matches and region_matches(" ".join((city["quote"], address["quote"] if address else "")))
    issue = location_issue(city["quote"], address["quote"] if address else None, coordinates, destination,
                           aliases, same_country_ambiguity=same_country_ambiguity and not regional_proof)
    if issue:
        if rejected is not None:
            rejected.append({"reason": issue, "sourceUrl": identity["sourceUrl"], "name": data.name})
        return None
    image_proof = property_evidence(data.image)
    image_url = None
    if image_proof:
        picture = re.search(r"!\[([^\]]+)\]\(([^\s)]+)", image_proof["quote"])
        if picture and name_matches(data.name, picture[1]) and not IMAGE_EXCLUDED.search(image_proof["quote"]):
            image_url = source_url(picture[2])
    rates, rate_keys = {}, {}
    rate_offers = {}

    def save_rate(rate, evidence, offer, context, original=None):
        checked = checked_rate(rate, evidence, destination.countryCode, offer=offer, context=context, rejected=rejected)
        if not checked:
            return None
        if original and original != rate.quote:
            checked["originalQuote"] = original
        checked["evidenceVersion"] = 2
        checked["pageId"] = rate.source
        checked["blockId"] = next((i for i, block in enumerate(sources[rate.source].get("offers", ()), 1)
                                   if block == offer), None)
        key = encode({name: value for name, value in checked.items() if name not in ("pageId", "blockId")})
        rates[key] = checked
        return key

    def rate_citation(rate):
        proof = verified(rate, sources, data.name)
        if proof and "\n" not in rate.quote:
            return rate, proof
        # A model can join the heading and the price across a short run of text.
        page = sources.get(rate.source, {})
        lines = [line.strip() for line in rate.quote.splitlines() if line.strip()]
        header = rate_header("\n".join(page.get("offers", ())), page.get("url", ""))
        amounts = [line for line in lines if quoted_amounts(rate.currency, line, destination.countryCode, header)]
        if len(lines) > 1 and len(amounts) == 1:
            support = dict.fromkeys([*rate.support, *(line for line in lines if line != amounts[0])])
            rate = rate.model_copy(update={"quote": amounts[0], "support": list(support)})
            return rate, verified(rate, sources, data.name)
        return rate, proof

    for index, rate in enumerate(data.rates):
        if rate is None:
            continue
        original = rate
        rate, literal = rate_citation(rate)
        if not literal:
            alternatives = []
            for source in sources:
                if source != original.source and linked(source):
                    candidate_rate, proof = rate_citation(original.model_copy(update={"source": source}))
                    if proof and rate_context(sources[source], candidate_rate)[1] is not None:
                        alternatives.append((candidate_rate, proof))
            if len(alternatives) == 1:
                rate, literal = alternatives[0]
        page = sources.get(rate.source, {})
        if not literal or not linked(rate.source):
            if rejected is not None:
                rejected.append({"reason": "unlinked_property" if literal else "missing_rate_quote",
                                 "sourceUrl": page.get("url"), "name": data.name, "quoteFound": bool(literal)})
            continue
        evidence = literal
        if page.get("stored"):
            # The catalog already contains the verified scope and full proof of these rates.
            existing = next(((key, saved) for key, saved in page["rates"].items()
                             if saved.get("scope") and saved["quote"] == rate.quote), None)
            if existing:
                rate_keys[index] = existing[0]
                rate_offers[index] = "\n".join([existing[1]["quote"], *existing[1].get("support", ())])
            continue
        offer, context = rate_context(page, rate)
        if PACKAGE.search(page.get("heading", "")):
            if rejected is not None:
                rejected.append({"reason": "unverified_unit", "sourceUrl": page.get("url")})
            continue
        if context is None:
            if rejected is not None:
                rejected.append({"reason": "ambiguous_rate_block" if rate_context(page, rate, details=True) > 1
                                 else "unlinked_rate_quotes", "sourceUrl": page.get("url"), "name": data.name,
                                 "quoteFound": True})
            continue
        if key := save_rate(rate, evidence, offer, context, original.quote):
            rate_keys[index] = key
            rate_offers[index] = offer or rate.quote
    if not any(data.rates):
        for source, page in sources.items():
            if linked(source):
                for rate, offer, context in explicit_nightly_rates(source, page, destination.countryCode):
                    proof = verified(rate, sources, data.name)
                    if proof:
                        save_rate(rate, proof, offer, context)
    facts = []
    for fact in data.facts:
        proof = property_evidence(fact)
        if proof and (fact.rate is None or fact.rate in rate_keys):
            label = fact.label.casefold()
            facts.append({**proof, "label": label if label in FACT_TOPICS else "policy",
                          "value": fact.value if contains(fact.value, fact.quote) else fact.quote,
                          "rateKey": rate_keys.get(fact.rate)})
    checks = []
    for check in data.checks:
        proof = property_evidence(check)
        if not proof or check.condition >= len(conditions) or (check.rate is not None and check.rate not in rate_keys):
            continue
        if check.contingent or re.search(r"subject to|on request|on availability|по запросу|при наличии|要予約", check.quote, re.I):
            continue
        tariff_policy = any(pattern.search(check.quote) for _, pattern in POLICIES)
        if (check.rate is not None and tariff_policy and
                " ".join(check.quote.split()) not in " ".join(rate_offers[check.rate].split())):
            continue
        if (check.rate is None and tariff_policy and
                not re.search(r"all (?:rates|rooms|guests)|все(?:х)? (?:тариф|номер|гост)", check.quote, re.I)):
            continue
        weekdays = quoted_weekdays(check.quote)
        if weekdays is not None and (weekdays != set(check.weekdays or ()) or not check.dayBasis):
            continue
        try:
            if any(value and not day_in(value, check.quote) for value in (check.start, check.end)):
                continue
        except ValueError:
            continue
        condition = conditions[check.condition]
        existing = check.model_dump(exclude={"source", "quote", "condition", "rate"})
        checks.append({**proof, **existing, "conditionKey": condition_key(condition),
                       "rateKey": rate_keys.get(check.rate)})
    if address and MULTI_ADDRESS.search(data.name):
        for checked in rates.values():
            if contains(address["quote"], checked["unitQuote"]):
                checked["offerAddress"] = {"value": address["quote"], "sourceUrl": address["sourceUrl"]}
        address = None
    return {
        "name": data.name, "identity": identity, "cityEvidence": city,
        "providerIds": dict([primary_id]) if primary_id else {},
        "sources": sorted({page["url"] for source, page in sources.items() if linked(source)}),
        "metadata": {key: proof for key, proof in (
            ("address", {"value": address["quote"], "sourceUrl": address["sourceUrl"]} if address else None),
            ("image", {"value": image_url, "sourceUrl": image_proof["sourceUrl"]} if image_url else None),
        ) if proof},
        "locationAliases": list(aliases), "discovery": ["web"],
        "lodgingType": ("hostel" if re.search(r"hostel|хостел", heading, re.I) else
                        "guest_house" if re.search(r"guest[ -]?house|гостев\w+\s+дом", heading, re.I) else "hotel"),
        "address": address["quote"] if address else None, "district": district["quote"] if district else None,
        "stars": star_rating, "coordinates": coordinates, "imageUrl": image_url,
        "rates": rates, "facts": facts,
        "availability": [item for row in data.availability if (item := availability_proof(row, property_evidence(row)))],
    }, checks


def condition_key(condition):
    # Used only inside account-scoped task checkpoints.
    return encode([condition["role"], condition["meaning"]])


class Exchange:
    def __init__(self, tools):
        self.tools = tools
        self.document = None
        self.error = None

    def reason(self, currency):
        if currency not in CURRENCY_CODES:
            return "unknown_currency"
        if self.error:
            return "fx_unavailable"
        if self.document and currency not in self.document.get("rates", {}):
            return "fx_currency_missing"
        return "fx_invalid_rate"

    async def quote(self, currency, *, refresh):
        if currency not in CURRENCY_CODES:
            return None
        if currency == "RUB":
            return {"currency": currency, "nominal": 1, "valueRub": "1", "date": None, "sourceUrl": None}
        if self.document is None and self.error is None and refresh:
            try:
                self.document = await self.tools.rates()
            except SearchInterrupted as error:
                self.error = error
        if not self.document:
            return None
        try:
            nominal, value = self.document["rates"][currency]
            nominal = int(nominal)
            published = self.document["date"]
            day, month, year = published.split(".")
            published = date(int(year), int(month), int(day)).isoformat()
            value = Decimal(value.replace(",", "."))
            if nominal <= 0 or not value.is_finite() or value <= 0:
                return None
        except (KeyError, ValueError, TypeError, AttributeError, InvalidOperation):
            return None
        return {"currency": currency, "nominal": nominal, "valueRub": str(value),
                "date": published, "sourceUrl": FX_URL}


def room_night_value(rate, fx):
    return Decimal(rate["amount"]) * Decimal(fx["valueRub"]) / fx["nominal"]


def group_price(rate, fx, rooms, nights):
    factor = {"room_night": rooms * nights, "room_stay": rooms, "group_night": nights, "group_stay": 1}[rate["basis"]]
    return int((room_night_value(rate, fx) * factor).to_integral_value(rounding=ROUND_CEILING))

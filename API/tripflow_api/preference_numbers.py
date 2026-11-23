"""Compare quantities in explicit forms that can be checked without interpreting prose."""

import re
from decimal import Decimal
from typing import NamedTuple


class Quantity(NamedTuple):
    kind: str
    value: int | Decimal
    bound: str
    basis: tuple[str, ...] = ()


class ClockConstraint(NamedTuple):
    times: set[Quantity]
    allows_removing_condition: bool = False


UPPER = ("не более", "не больше", "не дороже", "не выше", "не позднее", "не позже", "в пределах", "максимум",
         "до", "не дальше", "at most", "no later than", "up to", "before", "by", "within")
LOWER = ("не менее", "не меньше", "не ниже", "не раньше", "не ранее", "начиная с", "минимум", "от", "после",
         "at least", "no earlier than", "after", "from")
BOUNDARIES = {**dict.fromkeys(UPPER, "upper"), **dict.fromkeys(LOWER, "lower"), "к": "upper"}
BOUNDARY_PATTERN = "|".join(r"\s+".join(part.split()) for part in BOUNDARIES)
BOUND = rf"(?<![\w.,])(?:(?P<bound>{BOUNDARY_PATTERN})\s+)?"
NUMBER = r"(?P<number>\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"

CLOCK = re.compile(
    BOUND + r"(?:(?P<hour>\d{1,2})(?::(?P<minute>[0-5]\d)(?:\s*(?P<period>утра|вечера|дня|ночи|[ap]\.?m\.?))?"
    r"|\s+(?P<short_period>утра|вечера|[ap]\.?m\.?))|(?P<named>полуночи|полночь|полдня|полдень|midnight|noon))(?![\w:])",
    re.IGNORECASE,
)
MEASURE = re.compile(
    BOUND + NUMBER + r"\s*(?P<unit>километр(?:ов|а)?|метр(?:ов|а)?|килограмм(?:ов|а)?|грамм(?:ов|а)?|км|кг|м|г)(?!\w)",
    re.IGNORECASE,
)
RUBLES = re.compile(BOUND + NUMBER + r"\s*(?:₽|руб(?:\.|л(?:ей|я|ь))?|RUB)(?!\w)", re.IGNORECASE)

PRICE_BASIS = {
    "person": r"(?:с|на|за)\s+(?:одного\s+)?человека|на\s+одного|(?:с|на|за)\s+(?:одного\s+)?(?:гостя|туриста)",
    "group": r"(?:на|за)\s+(?:всю\s+)?группу|(?:на|за)\s+всех(?:\s+путешественников)?",
    "day": r"(?:в|за|на)\s+(?:один\s+)?(?:день|сутки)|ежедневно",
    "night": r"(?:в|за|на)\s+(?:одну\s+)?ночь|за\s+ночёвку",
    "stay": r"(?:на|за)\s+(?:всю\s+поездку|все\s+ночи|вс[её]\s+проживание)",
    "room": r"(?:на|за)\s+(?:один\s+)?номер",
    "visit": r"(?:на|за)\s+(?:одно\s+)?посещение",
}
BASIS = r"\b(?:" + "|".join(f"(?P<{name}>{pattern})" for name, pattern in PRICE_BASIS.items()) + r")\b"
BASIS_TERM = re.compile(BASIS, re.IGNORECASE)
BASIS_TEXT = r"\b(?:" + "|".join(PRICE_BASIS.values()) + r")\b"
HORIZONTAL_SPACE = r"[^\S\r\n]+"
PRICE_PREDICATE = (rf"(?:обычно{HORIZONTAL_SPACE})?"
                   rf"(?:(?:долж(?:ен|на|но|ны)|может|могут|будет|будут){HORIZONTAL_SPACE}(?:стоить|обойтись|составлять)"
                   r"|стоит|стоят|обойд[её]тся|обойдутся|составляет|составит)")
BASIS_PREFIX = rf"(?P<basis>(?:{BASIS_TEXT}{HORIZONTAL_SPACE}){{1,3}})"
BASIS_BEFORE = re.compile(rf"{BASIS_PREFIX}(?:{PRICE_PREDICATE}{HORIZONTAL_SPACE})?\Z", re.IGNORECASE)
# A basis at the start of a clause may precede a single subject: «На всю группу трансфер стоит …».
BASIS_BEFORE_SUBJECT = re.compile(
    rf"(?:^|[,.!?;:\r\n])[^\S\r\n]*{BASIS_PREFIX}[а-яё-]+{HORIZONTAL_SPACE}{PRICE_PREDICATE}{HORIZONTAL_SPACE}\Z",
    re.IGNORECASE,
)
BASIS_AFTER = re.compile(rf"(?:{HORIZONTAL_SPACE}{BASIS_TEXT}){{1,3}}", re.IGNORECASE)

TIME_CHANGE = re.compile(
    r"\b(?:время|по\s+времени)(?:\s+(?P<topic>[а-яё-]+))??\s+(?:(?:пока|теперь|больше|уже|вс[её])\s+)*"
    r"(?:(?P<keep>не\s+меняем|(?:(?:оставляем|оставим|оставьте|сохраняем|сохраним|оста[её]тся|останется)\s+)?"
    r"(?:прежн(?:ее|им)|(?:таким|такое)\s+же|как\s+(?:раньше|было)|без\s+изменений))"
    r"|(?P<release>не\s+(?:важно|принципиально)))\b",
    re.IGNORECASE,
)
ANY_TIME = re.compile(r"\b(?P<topic>[а-яё-]+)\s+(?:подойд[её]т|подходит|устроит)\s+в\s+любое\s+время\b", re.IGNORECASE)
CANCEL_CONDITION = re.compile(
    r"\b(?P<topic>[а-яё-]+)\s+(?:(?:вообще|больше|теперь)\s+)*не\s+(?:нуж(?:ен|на|но|ны)|требуется)\b", re.IGNORECASE,
)
CONTEXT_WORDS = {"время", "обяза", "раньш", "позже", "после", "тольк", "нужен", "требу", "новое", "важно", "прежн",
                 "отель", "отеля", "отеле", "номер", "гости"}
TIME_PREFIX = re.compile(r"(?:(?:теперь|вместо\s+этого|лучше|время)\s+)*", re.IGNORECASE)


def bound(match: re.Match) -> str:
    return BOUNDARIES.get(" ".join((match["bound"] or "").lower().split()), "exact")


def clock_minutes(match: re.Match) -> int | None:
    if named := match["named"]:
        return 12 * 60 if named.lower() in ("полдня", "полдень", "noon") else 0
    hour, minute = int(match["hour"]), int(match["minute"] or "0")
    period = (match["period"] or match["short_period"] or "").lower().replace(".", "")
    if period and 1 <= hour <= 12:
        if period in ("pm", "вечера", "дня"):
            hour = hour % 12 + 12
        elif period in ("am", "ночи"):
            hour %= 12
    if hour < 24 or (hour == 24 and minute == 0):
        return 60 * hour + minute
    return None


def price_basis(text: str, match: re.Match) -> tuple[str, ...]:
    prefix = text[:match.start()]
    before = BASIS_BEFORE.search(prefix) or BASIS_BEFORE_SUBJECT.search(prefix)
    after = BASIS_AFTER.match(text, match.end())
    terms = (before["basis"] if before else "") + (after.group() if after else "")
    return tuple(sorted({item.lastgroup for item in BASIS_TERM.finditer(terms)}))


def quantities(text: str) -> set[Quantity]:
    result = set()
    for match in CLOCK.finditer(text):
        if (minutes := clock_minutes(match)) is not None:
            result.add(Quantity("clock", minutes, bound(match)))
    for match in MEASURE.finditer(text):
        unit = match["unit"].lower()
        mass = unit in ("кг", "г") or "грамм" in unit
        thousands = unit in ("км", "кг") or unit.startswith("кило")
        value = Decimal("".join(match["number"].split()).replace(",", "."))
        result.add(Quantity("mass" if mass else "distance", value * (1000 if thousands else 1), bound(match)))
    for match in RUBLES.finditer(text):
        value = Decimal("".join(match["number"].split()).replace(",", "."))
        result.add(Quantity("rubles", value, bound(match), price_basis(text, match)))
    return result


def topic_terms(text: str) -> set[str]:
    # A short shared stem tolerates ordinary Russian case endings in explicit references.
    return {word[:5] for word in re.findall(r"\b[а-яё]{5,}\b", text.lower())} - CONTEXT_WORDS


def clock_constraint(refinement: str, previous_quote: str, evidence: tuple[str, ...],
                     other_timed_quotes: list[str], *, single_timed_change: bool) -> ClockConstraint | None:
    """Return the latest explicit time instruction supported for this change, if recognized."""
    previous = {item for item in quantities(previous_quote) if item.kind == "clock"}
    if not previous:
        return None
    own_terms = topic_terms(previous_quote)
    other_terms = set().union(*(topic_terms(text) for text in other_timed_quotes))
    quotes = [" ".join(quote.lower().split()) for quote in evidence]
    current = None
    sentences = re.split(r"(?<=\.)\s+|(?<=[!?;])\s*|[\r\n]+", refinement)
    fragments = ((sentence, clause) for sentence in sentences for clause in re.split(r",(?!\d)", sentence) if clause.strip())
    for sentence, clause in fragments:
        normalized = " ".join(clause.lower().split())
        terms = topic_terms(clause)
        names_own = bool(terms & (own_terms - other_terms))
        names_other = bool(terms & (other_terms - own_terms))
        linked = any(quote in normalized for quote in quotes)
        sentence_text = " ".join(sentence.lower().split())
        linked_sentence = (any(quote in sentence_text for quote in quotes)
                           and not topic_terms(sentence) & (other_terms - own_terms))

        events = []
        for match in TIME_CHANGE.finditer(clause):
            topic = match["topic"]
            applies = (topic.lower()[:5] in own_terms if topic else
                       not names_other and (names_own or linked_sentence or single_timed_change))
            if applies:
                events.append((match.start(), None if match["keep"] else ClockConstraint(set())))
        for pattern, directive in ((ANY_TIME, ClockConstraint(set())), (CANCEL_CONDITION, ClockConstraint(set(), True))):
            events.extend((match.start(), directive) for match in pattern.finditer(clause)
                          if match["topic"].lower()[:5] in own_terms)
        if not names_other:
            times = [(match.start(), Quantity("clock", minutes, bound(match))) for match in CLOCK.finditer(clause)
                     if (minutes := clock_minutes(match)) is not None
                     and (names_own or (linked and TIME_PREFIX.fullmatch(clause[:match.start()].lstrip())))]
            if times:
                events.append((times[-1][0], ClockConstraint({item for _, item in times})))
        for _, value in sorted(events, key=lambda event: event[0]):
            if value is not None:
                current = value
            elif current is None or current.allows_removing_condition:
                current = ClockConstraint(previous)
    return current

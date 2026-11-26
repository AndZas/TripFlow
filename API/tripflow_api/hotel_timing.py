import re

from .preference_numbers import CLOCK, bound, clock_minutes, quantities


SERVICES = {
    "breakfast": re.compile(r"breakfast|завтрак|朝食|petit.déjeuner|desayuno|frühstück", re.I),
    "arrival": re.compile(r"check[\s-]?in|arrival|arriv(?:er|ée)|заезд|засел|チェックイン", re.I),
    "departure": re.compile(r"check[\s-]?out|departure|выезд|チェックアウト", re.I),
}
RECEPTION = re.compile(r"reception|front desk|стойк[аи] регистрации|ресепш", re.I)
NEGATIVE = re.compile(r"невозможн|недоступ|запрещ|не\s+(?:работа|пода[юе]|сервиру|допуска|предостав|возмож)|"
                      r"\bunavailable\b|\bnot\s+(?:possible|available|served|permitted|allowed)\b|\bcannot\b", re.I)
CONTINUOUS = re.compile(r"\b24\s*(?:[- ]?hours?|/7|час\w*)|круглосуточ|24時間", re.I)
CLOCK_RANGE = re.compile(r"^\s*(?:[-–—〜~]|to\b|until\b|до\b|по\b)", re.I)
INCLUDED = re.compile(r"включ[её]н|входит в|included|в стоимост|free breakfast", re.I)
CANCELLATION = re.compile(r"бесплатн\w* отмен|отмен\w* без штраф|возврат оплат|free cancellation|refundable", re.I)


def policy_verdict(condition, policies):
    meaning = condition["meaning"] + " " + condition["quote"]
    if ("no_meals" in policies and SERVICES["breakfast"].search(meaning)
            and INCLUDED.search(meaning)) or ("nonrefundable" in policies and CANCELLATION.search(meaning)):
        return "confirmed" if condition["role"] == "excluded" else "refuted"
    return None


def timing_verdict(condition, check):
    # A quotation about a different service proves neither side of the requirement.
    requested = condition["meaning"] + " " + condition["quote"]
    targets = {value for value in quantities(requested) if value.kind == "clock"}
    if not targets:
        return check["verdict"]
    topics = [name for name, pattern in SERVICES.items() if pattern.search(requested)]
    if len(topics) != 1:
        return "unknown"
    topic, quote = topics[0], check["quote"]
    source_pattern = SERVICES[topic]
    midnight = topic == "arrival" and bool(re.search(r"after midnight|после полуночи", requested, re.I))
    contradicted = False
    clauses = re.split(r"[,;]|\n|(?<=[.!?])\s+|\s+(?:а|но|but|whereas)\s+", quote)
    related = []
    for clause in clauses:
        service = source_pattern.search(clause)
        other_service = any(pattern.search(clause) for key, pattern in SERVICES.items() if key != topic)
        reception = RECEPTION.search(clause)
        if other_service or (reception and service):
            continue
        if service and NEGATIVE.search(clause):
            mentioned = {value.value for value in quantities(clause) if value.kind == "clock"}
            if not mentioned or any(target.value in mentioned for target in targets):
                return "refuted"
            continue
        related.append(clause)
    for clause in related:
        service = source_pattern.search(clause)
        reception = topic == "arrival" and RECEPTION.search(clause)
        if not service and not reception:
            continue
        if service and CONTINUOUS.search(clause) and not (reception and topic == "arrival" and
                re.search(r"(?:24\s*[- ]?hours?|круглосуточ\w*)\s+(?:front desk|reception|стойк|ресепш)", clause, re.I)):
            return "confirmed"
        if service and midnight and re.search(r"after midnight|после полуночи|深夜", clause, re.I):
            return "confirmed"

        clocks = []
        for match in CLOCK.finditer(clause):
            minutes = clock_minutes(match)
            if minutes is not None:
                clocks.append((match, minutes))
        if not clocks:
            continue
        start = clocks[0][1]
        end = None
        if len(clocks) == 2:
            second = clocks[1][0]
            # CLOCK can itself consume the word «до» or «until».
            if CLOCK_RANGE.match(clause[clocks[0][0].end():second.end()]):
                end = clocks[1][1]
        elif len(clocks) > 2:
            continue

        if midnight:
            overlap = start < 360 and start > 0 or end is not None and (end < start and end > 0 or start == 0 and end > 0)
            if overlap and service:
                return "confirmed"
            if end is not None and end >= start and start >= 360:
                contradicted = True
            continue
        satisfied = all(clock_satisfies(target, start, end) for target in targets)
        if satisfied and service:
            return "confirmed"
        first_clock = clocks[0][0]
        opening = bound(first_clock) == "lower" or bool(re.search(
            r"\b(?:с|from|starting at|opens? at)\s*$", clause[:first_clock.start()], re.I))
        if not satisfied and (end is not None or topic == "breakfast" and opening):
            contradicted = True
    return "refuted" if contradicted else "unknown"


def clock_satisfies(target, start, end):
    minute = target.value
    if target.bound == "exact":
        if end is None:
            return start == minute
        return start <= minute <= end if end >= start else minute >= start or minute <= end
    earliest = 0 if end is not None and end < start else start
    latest = (1440 if end < start else end) if end is not None else start
    return earliest < minute if target.bound == "upper" else latest > minute

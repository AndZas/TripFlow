from .schemas import BudgetRequest, RecommendationTarget, RecommendationsRequest, TripContext


MOCK_DESTINATION = "ru-moscow"
# Room-night prices for double rooms.
HOTELS = (
    ("hotel-boulevard", "Бульварный дом", 5400, 3),
    ("hotel-metro", "Отель у метро", 4400, 3),
    ("hotel-garden", "Садовый отель", 6700, 4),
)
ATTRACTIONS = (
    ("place-museum", "Городской музей", "Музей", 900, "person_admission"),
    ("place-park", "Городской парк", "Парк", 0, "person_admission"),
    ("place-tour", "Экскурсия по старому городу", "Экскурсия", 2400, "group_admission"),
    ("place-gallery", "Галерея на бульваре", "Галерея", None, "person_admission"),
)


def candidate(object_id: str, name: str) -> dict:
    return {
        "objectId": object_id,
        "name": name,
        "address": None,
        "coordinates": None,
        "imageUrl": None,
        "sourceUrl": f"https://example.org/tripflow-mock/{object_id}",
    }


def within_limit(price: int | None, limit: int | None) -> bool:
    return limit is None or (price is not None and price <= limit)


def mock_hotels(trip: TripContext, target: RecommendationTarget) -> list[dict]:
    nights = (trip.endDate - trip.startDate).days
    if nights == 0:
        return []
    rooms = (trip.travelers + 1) // 2
    excluded = set(target.excludedObjectIds)
    items = []
    for object_id, name, nightly_rate, stars in HOTELS:
        price = nightly_rate * nights * rooms
        if object_id not in excluded and within_limit(price, target.maxTotalRub):
            items.append({
                **candidate(object_id, name),
                "price": price,
                "stars": stars,
                "tariff": {"name": "Без питания", "includedServices": []},
            })
    return items


def mock_attractions(trip: TripContext, target: RecommendationTarget) -> list[dict]:
    excluded = set(target.excludedObjectIds)
    items = []
    for object_id, name, category, amount, basis in ATTRACTIONS:
        price = None
        total = None
        if amount is not None:
            total = amount * trip.travelers if basis == "person_admission" else amount
            price = {"amountRub": amount, "basis": basis, "kind": "source" if amount == 0 else "estimate"}
        if object_id not in excluded and within_limit(total, target.maxTotalRub):
            items.append({**candidate(object_id, name), "category": category, "price": price})
    return items


def recommendations(request: RecommendationsRequest) -> dict:
    builders = {"hotels": mock_hotels, "attractions": mock_attractions}
    results = {}
    for kind, target in request.targets.items():
        items = builders[kind](request.trip, target) if request.trip.destinationId == MOCK_DESTINATION else []
        results[kind] = {
            "status": "succeeded",
            "items": items[:target.count],
            "hasMore": len(items) > target.count,
        }
    return {"taskId": request.taskId, "event": "recommendations.finished", "results": results}


def included_breakfast_days(request: BudgetRequest) -> int:
    if request.selectedHotel is None:
        return 0
    trip = request.trip
    full_stay = False
    dates = set()
    for service in request.selectedHotel.tariff.includedServices:
        if service.service != "breakfast" or service.status != "confirmed":
            continue
        if service.dates is None:
            full_stay = True
        else:
            dates.update(day for day in service.dates if trip.startDate <= day <= trip.endDate)
    if full_stay:
        return (trip.endDate - trip.startDate).days + (trip.startDate in dates)
    return len(dates)


def budget(request: BudgetRequest) -> dict:
    trip = request.trip
    days = (trip.endDate - trip.startDate).days + 1
    breakfast_days = included_breakfast_days(request)
    return {
        "taskId": request.taskId,
        "event": "budget.finished",
        "status": "succeeded",
        "expenses": {
            "foodTotalRub": (1400 * days - 240 * breakfast_days) * trip.travelers,
            "localTransportTotalRub": 400 * days * trip.travelers,
            "otherExpensesTotalRub": 0,
            "reserveTotalRub": (trip.budgetRub + 9) // 10,
        },
    }

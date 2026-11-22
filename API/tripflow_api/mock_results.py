from collections.abc import Collection

from .schemas import BudgetRequest, RecommendationsRequest, TripContext


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


def mock_hotels(trip: TripContext, limit: int | None, excluded: Collection[str]) -> list[dict]:
    nights = (trip.endDate - trip.startDate).days
    if nights == 0:
        return []
    rooms = (trip.travelers + 1) // 2
    items = []
    for object_id, name, nightly_rate, stars in HOTELS:
        price = nightly_rate * nights * rooms
        if object_id not in excluded and within_limit(price, limit):
            items.append({
                **candidate(object_id, name),
                "price": price,
                "stars": stars,
            })
    return items


def mock_attractions(trip: TripContext, limit: int | None, excluded: Collection[str]) -> list[dict]:
    items = []
    for object_id, name, category, amount, basis in ATTRACTIONS:
        price = None
        total = None
        if amount is not None:
            total = amount * trip.travelers if basis == "person_admission" else amount
            price = {"amountRub": amount, "basis": basis, "kind": "source" if amount == 0 else "estimate"}
        if object_id not in excluded and within_limit(total, limit):
            items.append({**candidate(object_id, name), "category": category, "price": price})
    return items


def recommendations(request: RecommendationsRequest) -> dict:
    builders = {"hotels": mock_hotels, "attractions": mock_attractions}
    items = []
    if request.trip.destinationId == MOCK_DESTINATION:
        excluded = set(request.excludedObjectIds or ())
        items = builders[request.targets](request.trip, request.maxTotalRub, excluded)
    return {
        "status": "succeeded",
        "items": items[:request.count],
        "hasMore": len(items) > request.count,
    }


def budget(request: BudgetRequest) -> dict:
    trip = request.trip
    days = (trip.endDate - trip.startDate).days + 1
    return {
        "taskId": request.taskId,
        "event": "budget.finished",
        "status": "succeeded",
        "expenses": {
            "foodTotalRub": 1400 * days * trip.travelers,
            "localTransportTotalRub": 400 * days * trip.travelers,
            "otherExpensesTotalRub": 0,
            "reserveTotalRub": (trip.budgetRub + 9) // 10,
        },
    }

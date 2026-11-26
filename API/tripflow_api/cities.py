import httpx
from pydantic import ValidationError

from .schemas import Destination


AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
LIMIT = 7


async def city_suggestions(client, key, query, remember=None):
    if not query:
        return {"status": "empty", "items": []}
    if not key:
        return {"status": "unconfigured", "items": []}
    try:
        response = await client.get(AUTOCOMPLETE_URL, params={
            "text": query, "type": "city", "lang": "ru", "limit": LIMIT, "format": "json", "apiKey": key,
        }, timeout=5)
        response.raise_for_status()
        rows = response.json()["results"]
        if not isinstance(rows, list):
            raise ValueError
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return {"status": "unavailable", "items": []}
    items = []
    for row in rows[:LIMIT]:
        if not isinstance(row, dict) or row.get("result_type") not in ("city", None):
            continue
        try:
            city = Destination(city=row.get("city"), countryCode=row.get("country_code"),
                               latitude=row.get("lat"), longitude=row.get("lon"))
        except ValidationError:
            continue
        parts = [city.city, row.get("state"), row.get("country") or city.countryCode]
        label = ", ".join(dict.fromkeys(part.strip() for part in parts if isinstance(part, str) and part.strip()))
        items.append({"label": label, **city.model_dump()})
        if remember:
            region = row.get("state")
            place_id = row.get("place_id")
            remember(city, region[:100].strip() if isinstance(region, str) else "",
                     place_id[:240].strip() if isinstance(place_id, str) else "")
    return {"status": "ok", "items": items}

# Фактический запуск

Run: `20261014T230633743995Z`. UTC: 2026-10-14T23:06:33.743985+00:00.
Offline: True; без ключей: True.

Результат `ok` подтверждает только этот ответ. `skipped` не означает неисправность API.
Доли заполнения относятся к первым N объектам запроса, не ко всему городу. 0/0 = нет измерения.
Поле address может быть частичным; image_url означает ссылку, не проверенную лицензию изображения.
Категория normalizer — группа запроса; исходные теги/категории находятся в примере JSON.

```json
{
  "city": "Paris",
  "country": "France",
  "country_code": "FR",
  "run_date_moscow": "2026-10-15",
  "stay": {
    "check_in": "2026-11-14",
    "check_out": "2026-11-16",
    "adults": 2,
    "rooms": 1,
    "nights": 2
  },
  "radius_metres": 3000,
  "coordinates": null,
  "coordinate_source": null
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | city_search | skipped | None | None | None | Offline or not selected |
| overpass | museums | skipped | None | None | None | Offline or not selected |
| overpass | historic | skipped | None | None | None | Offline or not selected |
| overpass | nature | skipped | None | None | None | Offline or not selected |
| overpass | restaurants | skipped | None | None | None | Offline or not selected |
| overpass | hotels | skipped | None | None | None | Offline or not selected |
| geoapify | museums | skipped | None | None | None | Offline or not selected |
| geoapify | historic | skipped | None | None | None | Offline or not selected |
| geoapify | nature | skipped | None | None | None | Offline or not selected |
| geoapify | restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | hotels | skipped | None | None | None | Offline or not selected |
| opentripmap | museums | skipped | None | None | None | Offline or not selected |
| opentripmap | historic | skipped | None | None | None | Offline or not selected |
| opentripmap | nature | skipped | None | None | None | Offline or not selected |
| opentripmap | restaurants | skipped | None | None | None | Offline or not selected |
| geonames | city_search | skipped | None | None | None | Offline or not selected |
| geonames | country_info | skipped | None | None | None | Offline or not selected |
| geonames | timezone | skipped | None | None | None | Offline or not selected |
| frankfurter | eur_rub_v2 | skipped | None | None | None | Offline or not selected |
| frankfurter | eur_rub_v1 | skipped | None | None | None | Offline or not selected |
| six | france_currency | skipped | None | None | None | Offline or not selected |
| cldr | france_currency | skipped | None | None | None | Offline or not selected |
| amadeus | documentation | skipped | None | None | None | Official portal confirms Self-Service decommissioned July 17, 2026; Enterprise only. No token request. |
| foursquare | documentation | skipped | None | None | None | New API and paid overage; documentation only, no confirmed free account quota. |
| google | documentation | skipped | None | None | None | Billing account and SKU-dependent charges; documentation only. |
| tripadvisor | documentation | skipped | None | None | None | Legacy Content API sunset; Terra has separate paid packages/rights. Documentation only. |
| yelp | documentation | skipped | None | None | None | Evaluation trial and storage restrictions; documentation only. |
| booking | documentation | skipped | None | None | None | Managed affiliate contract, token and affiliate ID required; documentation only. |
| expedia | documentation | skipped | None | None | None | Partner access and agreed terms required; documentation only. |
| sherpa | documentation | skipped | None | None | None | Sandbox requires partner key; schema/documentation only; no passport profile sent. |
| visafar | documentation | skipped | None | None | None | Manually issued key, current API price not confirmed; documentation only; no passport profile sent. |
| timezonefinder | documentation | skipped | None | None | None | Local polygon lookup assessed in documentation; not installed or benchmarked. |
| government | documentation | skipped | None | None | None | Official entry-information pages assessed manually; no website parsing or automated visa decision. |

## open_meteo / city_search

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Paris",
  "countryCode": "FR",
  "language": "en",
  "count": 10
}
```

Фактические поля: не измерены.

## overpass / museums

Evidence: `not_called`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,<latitude>,<longitude>)[\"tourism\"=\"museum\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / historic

Evidence: `not_called`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,<latitude>,<longitude>)[\"historic\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / nature

Evidence: `not_called`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,<latitude>,<longitude>)[\"leisure\"=\"park\"];nwr(around:3000,<latitude>,<longitude>)[\"tourism\"=\"viewpoint\"];nwr(around:3000,<latitude>,<longitude>)[\"natural\"=\"wood\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / restaurants

Evidence: `not_called`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,<latitude>,<longitude>)[\"amenity\"~\"^(restaurant|cafe)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / hotels

Evidence: `not_called`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,<latitude>,<longitude>)[\"tourism\"~\"^(hotel|hostel|guest_house)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## geoapify / museums

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:None,None,3000",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / historic

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:None,None,3000",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / nature

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:None,None,3000",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / restaurants

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:None,None,3000",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / hotels

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:None,None,3000",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## opentripmap / museums

Evidence: `not_called`; endpoint: `https://api.opentripmap.com/0.1/en/places/radius`.

Параметры / фильтры:
```json
{
  "lat": null,
  "lon": null,
  "radius": 3000,
  "kinds": "museums",
  "limit": 10,
  "format": "json",
  "apikey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## opentripmap / historic

Evidence: `not_called`; endpoint: `https://api.opentripmap.com/0.1/en/places/radius`.

Параметры / фильтры:
```json
{
  "lat": null,
  "lon": null,
  "radius": 3000,
  "kinds": "historic,cultural",
  "limit": 10,
  "format": "json",
  "apikey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## opentripmap / nature

Evidence: `not_called`; endpoint: `https://api.opentripmap.com/0.1/en/places/radius`.

Параметры / фильтры:
```json
{
  "lat": null,
  "lon": null,
  "radius": 3000,
  "kinds": "natural,gardens_and_parks",
  "limit": 10,
  "format": "json",
  "apikey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## opentripmap / restaurants

Evidence: `not_called`; endpoint: `https://api.opentripmap.com/0.1/en/places/radius`.

Параметры / фильтры:
```json
{
  "lat": null,
  "lon": null,
  "radius": 3000,
  "kinds": "restaurants,cafes",
  "limit": 10,
  "format": "json",
  "apikey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geonames / city_search

Evidence: `not_called`; endpoint: `https://secure.geonames.org/searchJSON`.

Параметры / фильтры:
```json
{
  "name_equals": "Paris",
  "country": "FR",
  "featureCode": "PPLC",
  "maxRows": 10,
  "style": "FULL",
  "username": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geonames / country_info

Evidence: `not_called`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "FR",
  "username": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geonames / timezone

Evidence: `not_called`; endpoint: `https://secure.geonames.org/timezoneJSON`.

Параметры / фильтры:
```json
{
  "lat": null,
  "lng": null,
  "username": "[REDACTED]"
}
```

Фактические поля: не измерены.

## frankfurter / eur_rub_v2

Evidence: `not_called`; endpoint: `https://api.frankfurter.dev/v2/rate/EUR/RUB`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## frankfurter / eur_rub_v1

Evidence: `not_called`; endpoint: `https://api.frankfurter.dev/v1/latest`.

Параметры / фильтры:
```json
{
  "base": "EUR",
  "symbols": "RUB"
}
```

Фактические поля: не измерены.

## six / france_currency

Evidence: `not_called`; endpoint: `https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## cldr / france_currency

Evidence: `not_called`; endpoint: `https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/cldr-core/supplemental/currencyData.json`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## amadeus / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## foursquare / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## google / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## tripadvisor / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## yelp / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## booking / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## expedia / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## sherpa / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## visafar / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## timezonefinder / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## government / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

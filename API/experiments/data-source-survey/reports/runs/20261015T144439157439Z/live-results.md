# Фактический запуск

Run: `20261015T144439157439Z`. UTC: 2026-10-15T14:44:39.157431+00:00.
Offline: True; без ключей: True.

Результат `ok` подтверждает только этот ответ. `skipped` не означает неисправность API.
Доли заполнения относятся к первым N объектам запроса, не ко всему городу. 0/0 = нет измерения.
Поле address может быть частичным; image_url означает ссылку, не проверенную лицензию изображения.
Категория normalizer — группа запроса; исходные теги/категории находятся в примере JSON.

```json
{
  "scenario": "extended_v2",
  "cities": [
    "paris",
    "moscow",
    "istanbul",
    "suzdal"
  ],
  "radius_metres": 3000,
  "limit": 5,
  "core_only": false,
  "request_cap": 40,
  "planned_max_requests": 40,
  "details_only": false,
  "coordinates": {},
  "no_hotel_offer_queries": true,
  "attempted_requests": 0
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | paris_city | skipped | None | None | None | Offline or not selected |
| geonames | paris_city | skipped | None | None | None | Offline or not selected |
| geonames | FR_country | skipped | None | None | None | Offline or not selected |
| geoapify | paris_museums | skipped | None | None | None | Offline or not selected |
| geoapify | paris_historic | skipped | None | None | None | Offline or not selected |
| geoapify | paris_nature | skipped | None | None | None | Offline or not selected |
| geoapify | paris_restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | paris_hotels | skipped | None | None | None | Offline or not selected |
| open_meteo | moscow_city | skipped | None | None | None | Offline or not selected |
| geonames | moscow_city | skipped | None | None | None | Offline or not selected |
| geonames | RU_country | skipped | None | None | None | Offline or not selected |
| geoapify | moscow_museums | skipped | None | None | None | Offline or not selected |
| geoapify | moscow_historic | skipped | None | None | None | Offline or not selected |
| geoapify | moscow_nature | skipped | None | None | None | Offline or not selected |
| geoapify | moscow_restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | moscow_hotels | skipped | None | None | None | Offline or not selected |
| open_meteo | istanbul_city | skipped | None | None | None | Offline or not selected |
| geonames | istanbul_city | skipped | None | None | None | Offline or not selected |
| geonames | TR_country | skipped | None | None | None | Offline or not selected |
| geoapify | istanbul_museums | skipped | None | None | None | Offline or not selected |
| geoapify | istanbul_historic | skipped | None | None | None | Offline or not selected |
| geoapify | istanbul_nature | skipped | None | None | None | Offline or not selected |
| geoapify | istanbul_restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | istanbul_hotels | skipped | None | None | None | Offline or not selected |
| open_meteo | suzdal_city | skipped | None | None | None | Offline or not selected |
| geonames | suzdal_city | skipped | None | None | None | Offline or not selected |
| geoapify | suzdal_museums | skipped | None | None | None | Offline or not selected |
| geoapify | suzdal_historic | skipped | None | None | None | Offline or not selected |
| geoapify | suzdal_nature | skipped | None | None | None | Offline or not selected |
| geoapify | suzdal_restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | suzdal_hotels | skipped | None | None | None | Offline or not selected |
| open_meteo | russian_name | skipped | None | None | None | Offline or not selected |
| geonames | russian_name | skipped | None | None | None | Offline or not selected |
| open_meteo | ambiguous_name | skipped | None | None | None | Offline or not selected |
| open_meteo | country_filter | skipped | None | None | None | Offline or not selected |
| open_meteo | unknown_city | skipped | None | None | None | Offline or not selected |
| geoapify | empty_place_name | skipped | None | None | None | Offline or not selected |
| geoapify | vegetarian_restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | hotels_details | skipped | None | None | None | Offline or not selected |
| geoapify | restaurants_details | skipped | None | None | None | Offline or not selected |

## open_meteo / paris_city

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Paris",
  "count": 10,
  "language": "en",
  "countryCode": "FR"
}
```

Фактические поля: не измерены.

## geonames / paris_city

Evidence: `not_called`; endpoint: `https://secure.geonames.org/searchJSON`.

Параметры / фильтры:
```json
{
  "name_equals": "Paris",
  "maxRows": 10,
  "featureClass": "P",
  "style": "FULL",
  "lang": "en",
  "username": "[REDACTED]",
  "country": "FR"
}
```

Фактические поля: не измерены.

## geonames / FR_country

Evidence: `not_called`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "FR",
  "username": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / paris_museums

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / paris_historic

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / paris_nature

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / paris_restaurants

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / paris_hotels

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## open_meteo / moscow_city

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Moscow",
  "count": 10,
  "language": "en",
  "countryCode": "RU"
}
```

Фактические поля: не измерены.

## geonames / moscow_city

Evidence: `not_called`; endpoint: `https://secure.geonames.org/searchJSON`.

Параметры / фильтры:
```json
{
  "name_equals": "Moscow",
  "maxRows": 10,
  "featureClass": "P",
  "style": "FULL",
  "lang": "en",
  "username": "[REDACTED]",
  "country": "RU"
}
```

Фактические поля: не измерены.

## geonames / RU_country

Evidence: `not_called`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "RU",
  "username": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / moscow_museums

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / moscow_historic

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / moscow_nature

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / moscow_restaurants

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / moscow_hotels

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## open_meteo / istanbul_city

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Istanbul",
  "count": 10,
  "language": "en",
  "countryCode": "TR"
}
```

Фактические поля: не измерены.

## geonames / istanbul_city

Evidence: `not_called`; endpoint: `https://secure.geonames.org/searchJSON`.

Параметры / фильтры:
```json
{
  "name_equals": "Istanbul",
  "maxRows": 10,
  "featureClass": "P",
  "style": "FULL",
  "lang": "en",
  "username": "[REDACTED]",
  "country": "TR"
}
```

Фактические поля: не измерены.

## geonames / TR_country

Evidence: `not_called`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "TR",
  "username": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / istanbul_museums

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / istanbul_historic

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / istanbul_nature

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / istanbul_restaurants

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / istanbul_hotels

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## open_meteo / suzdal_city

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Suzdal",
  "count": 10,
  "language": "en",
  "countryCode": "RU"
}
```

Фактические поля: не измерены.

## geonames / suzdal_city

Evidence: `not_called`; endpoint: `https://secure.geonames.org/searchJSON`.

Параметры / фильтры:
```json
{
  "name_equals": "Suzdal",
  "maxRows": 10,
  "featureClass": "P",
  "style": "FULL",
  "lang": "en",
  "username": "[REDACTED]",
  "country": "RU"
}
```

Фактические поля: не измерены.

## geoapify / suzdal_museums

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / suzdal_historic

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / suzdal_nature

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / suzdal_restaurants

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / suzdal_hotels

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## open_meteo / russian_name

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Москва",
  "count": 10,
  "language": "ru",
  "countryCode": "RU"
}
```

Фактические поля: не измерены.

## geonames / russian_name

Evidence: `not_called`; endpoint: `https://secure.geonames.org/searchJSON`.

Параметры / фильтры:
```json
{
  "name_equals": "Москва",
  "maxRows": 10,
  "featureClass": "P",
  "style": "FULL",
  "lang": "ru",
  "username": "[REDACTED]",
  "country": "RU"
}
```

Фактические поля: не измерены.

## open_meteo / ambiguous_name

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Springfield",
  "count": 10,
  "language": "en"
}
```

Фактические поля: не измерены.

## open_meteo / country_filter

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Springfield",
  "count": 10,
  "language": "en",
  "countryCode": "US"
}
```

Фактические поля: не измерены.

## open_meteo / unknown_city

Evidence: `not_called`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "TripFlowNoSuchCity9f71b2",
  "count": 10,
  "language": "en"
}
```

Фактические поля: не измерены.

## geoapify / empty_place_name

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]",
  "name": "TripFlowNoSuchMuseum9f71b2"
}
```

Фактические поля: не измерены.

## geoapify / vegetarian_restaurants

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:None,None,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]",
  "conditions": "vegetarian"
}
```

Фактические поля: не измерены.

## geoapify / hotels_details

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/place-details`.

Параметры / фильтры:
```json
{
  "id": null,
  "features": "details",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

## geoapify / restaurants_details

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/place-details`.

Параметры / фильтры:
```json
{
  "id": null,
  "features": "details",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: не измерены.

# Фактический запуск

Run: `20261014T230458162620Z`. UTC: 2026-10-14T23:04:58.162609+00:00.
Offline: False; без ключей: True.

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
  "radius_metres": 1500,
  "coordinates": {
    "latitude": 48.85341,
    "longitude": 2.3488
  },
  "coordinate_source": "open_meteo/city_search id=2988507"
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | city_search | ok | 200 | 555.1 | 10 |  |
| overpass | nature | ok | 200 | 3720.5 | 10 |  |
| overpass | restaurants | ok | 200 | 9670.4 | 10 |  |
| overpass | hotels | network_error | None | 25344.9 | None | TimeoutError |
| geoapify | nature | skipped | None | None | None | Offline or not selected |
| geoapify | restaurants | skipped | None | None | None | Offline or not selected |
| geoapify | hotels | skipped | None | None | None | Offline or not selected |
| geonames | city_search | skipped | None | None | None | Offline or not selected |
| geonames | country_info | skipped | None | None | None | Offline or not selected |
| geonames | timezone | skipped | None | None | None | Offline or not selected |
| frankfurter | eur_rub_v2 | skipped | None | None | None | Offline or not selected |
| frankfurter | eur_rub_v1 | skipped | None | None | None | Offline or not selected |
| six | france_currency | skipped | None | None | None | Offline or not selected |
| cldr | france_currency | ok | 200 | 547.7 | 1 |  |
| amadeus | documentation | skipped | None | None | None | Official portal confirms Self-Service decommissioned July 17, 2026; Enterprise only. No token request. |
| opentripmap | documentation | skipped | None | None | None | Current free quota and key issuance not confirmed at official dev.opentripmap.org. No calls even if an old key exists. |
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

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Paris",
  "countryCode": "FR",
  "language": "en",
  "count": 10
}
```

Фактические поля: `admin1`, `admin1_id`, `admin2`, `admin2_id`, `admin3`, `admin3_id`, `admin4`, `admin4_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `postcodes`, `timezone`.

Пример: [data/samples/20261014T230458162620Z/open_meteo_city_search.json](../../../data/samples/20261014T230458162620Z/open_meteo_city_search.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 0/10 | 0% |
| description | 0/10 | 0% |
| website_url | 0/10 | 0% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 10/10 | 100% |
| timezone | 10/10 | 100% |
| cuisine | 0/10 | 0% |
| opening_hours | 0/10 | 0% |
| entrance_fee | 0/10 | 0% |

## overpass / nature

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:1500,48.85341,2.3488)[\"leisure\"=\"park\"];nwr(around:1500,48.85341,2.3488)[\"tourism\"=\"viewpoint\"];nwr(around:1500,48.85341,2.3488)[\"natural\"=\"wood\"];);out center 10;"
}
```

Фактические поля: `center`, `center.lat`, `center.lon`, `id`, `lat`, `lon`, `nodes`, `tags`, `tags.bicycle`, `tags.check_date`, `tags.contact:mastodon`, `tags.description`, `tags.description:en`, `tags.email`, `tags.fax`, `tags.fee`, `tags.heritage`, `tags.heritage:operator`, `tags.indoor`, `tags.leisure`, `tags.level`, `tags.mapillary`, `tags.mhs:inscription_date`, `tags.name`, `tags.name:ar`, `tags.name:en`, `tags.name:fi`, `tags.name:fr`, `tags.name:ru`, `tags.name:zh`, `tags.opening_hours`, `tags.operator`, `tags.outdoor`, `tags.phone`, `tags.ref:FR:FANTOIR`, `tags.ref:mhs`, `tags.source`, `tags.source:heritage`, `tags.surface`, `tags.tourism`, `tags.tourism:visitors`, `tags.website`, `tags.wheelchair`, `tags.wikidata`, `tags.wikipedia`, `type`.

Пример: [data/samples/20261014T230458162620Z/overpass_nature.json](../../../data/samples/20261014T230458162620Z/overpass_nature.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 6/10 | 60% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 0/10 | 0% |
| description | 1/10 | 10% |
| website_url | 1/10 | 10% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 0/10 | 0% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 2/10 | 20% |
| entrance_fee | 2/10 | 20% |

Метаданные источника: `{"timestamp_osm_base": "2026-10-14T23:03:50Z", "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."}`.

## overpass / restaurants

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:1500,48.85341,2.3488)[\"amenity\"~\"^(restaurant|cafe)$\"];);out center 10;"
}
```

Фактические поля: `id`, `lat`, `lon`, `tags`, `tags.addr:city`, `tags.addr:housenumber`, `tags.addr:postcode`, `tags.addr:street`, `tags.air_conditioning`, `tags.amenity`, `tags.check_date`, `tags.check_date:opening_hours`, `tags.contact:city`, `tags.contact:housenumber`, `tags.contact:phone`, `tags.contact:postcode`, `tags.contact:street`, `tags.contact:tripadvisor`, `tags.contact:yelp`, `tags.cuisine`, `tags.diet:vegan`, `tags.diet:vegetarian`, `tags.indoor_seating`, `tags.internet_access`, `tags.layer`, `tags.level`, `tags.name`, `tags.name:fr`, `tags.name:ru`, `tags.opening_hours`, `tags.outdoor_seating`, `tags.payment:cash`, `tags.payment:credit_cards`, `tags.payment:debit_cards`, `tags.phone`, `tags.ref:FR:SIRET`, `tags.reservation`, `tags.smoking`, `tags.source`, `tags.toilets`, `tags.toilets:wheelchair`, `tags.website`, `tags.wheelchair`, `tags.wheelchair:description`, `tags.wikidata`, `type`.

Пример: [data/samples/20261014T230458162620Z/overpass_restaurants.json](../../../data/samples/20261014T230458162620Z/overpass_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 6/10 | 60% |
| description | 0/10 | 0% |
| website_url | 4/10 | 40% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 0/10 | 0% |
| timezone | 0/10 | 0% |
| cuisine | 7/10 | 70% |
| opening_hours | 6/10 | 60% |
| entrance_fee | 0/10 | 0% |

Метаданные источника: `{"timestamp_osm_base": "2026-10-14T23:03:50Z", "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."}`.

## overpass / hotels

Evidence: `network_attempt`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:1500,48.85341,2.3488)[\"tourism\"~\"^(hotel|hostel|guest_house)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## geoapify / nature

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.sights.viewpoint",
  "filter": "circle:2.3488,48.85341,1500",
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
  "filter": "circle:2.3488,48.85341,1500",
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
  "filter": "circle:2.3488,48.85341,1500",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
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
  "lat": 48.85341,
  "lng": 2.3488,
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

Evidence: `live_http`; endpoint: `https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/cldr-core/supplemental/currencyData.json`.

Параметры / фильтры:
```json
{}
```

Фактические поля: `country_code`, `currency_code`, `validity`, `validity._from`, `version`, `version._cldrVersion`, `version._unicodeVersion`.

Пример: [data/samples/20261014T230458162620Z/cldr_france_currency.json](../../../data/samples/20261014T230458162620Z/cldr_france_currency.json).

## amadeus / documentation

Evidence: `not_called`; endpoint: `None`.

Параметры / фильтры:
```json
{}
```

Фактические поля: не измерены.

## opentripmap / documentation

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

# Фактический запуск

Run: `20261014T230158009158Z`. UTC: 2026-10-14T23:01:58.009150+00:00.
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
  "coordinates": {
    "latitude": 48.85341,
    "longitude": 2.3488
  },
  "coordinate_source": "open_meteo/city_search id=2988507"
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | city_search | ok | 200 | 464.6 | 10 |  |
| overpass | museums | ok | 200 | 18808.8 | 10 |  |
| overpass | historic | ok | 200 | 4009.4 | 10 |  |
| overpass | nature | network_error | None | 20276.6 | None | TimeoutError |
| overpass | restaurants | network_error | None | 20314.8 | None | TimeoutError |
| overpass | hotels | network_error | None | 20442.5 | None | TimeoutError |
| geoapify | museums | skipped | None | None | None | Missing GEOAPIFY_API_KEY |
| geoapify | historic | skipped | None | None | None | Missing GEOAPIFY_API_KEY |
| geoapify | nature | skipped | None | None | None | Missing GEOAPIFY_API_KEY |
| geoapify | restaurants | skipped | None | None | None | Missing GEOAPIFY_API_KEY |
| geoapify | hotels | skipped | None | None | None | Missing GEOAPIFY_API_KEY |
| geonames | city_search | skipped | None | None | None | Missing GEONAMES_USERNAME |
| geonames | country_info | skipped | None | None | None | Missing GEONAMES_USERNAME |
| geonames | timezone | skipped | None | None | None | Missing GEONAMES_USERNAME |
| frankfurter | eur_rub_v2 | ok | 200 | 572.0 | 1 |  |
| frankfurter | eur_rub_v1 | http_error | 404 | 404.9 | None | Not found |
| six | france_currency | network_error | None | 494.4 | None | SSLCertVerificationError |
| amadeus | documentation | skipped | None | None | None | Self-Service access is unavailable/being retired; current free quota unverified. See comparison.md. No token request. |
| opentripmap | documentation | skipped | None | None | None | Current free quota and key issuance not confirmed at official dev.opentripmap.org. No calls even if an old key exists. |
| foursquare | documentation | skipped | None | None | None | New API and paid overage; documentation only, no confirmed free account quota. |
| google | documentation | skipped | None | None | None | Billing account and SKU-dependent charges; documentation only. |
| tripadvisor | documentation | skipped | None | None | None | Legacy Content API sunset; Terra has separate paid packages/rights. Documentation only. |
| yelp | documentation | skipped | None | None | None | Evaluation trial and storage restrictions; documentation only. |
| booking | documentation | skipped | None | None | None | Managed affiliate contract, token and affiliate ID required; documentation only. |
| expedia | documentation | skipped | None | None | None | Partner access and agreed terms required; documentation only. |
| sherpa | documentation | skipped | None | None | None | Sandbox requires partner key; schema/documentation only; no passport profile sent. |
| visafar | documentation | skipped | None | None | None | Manually issued paid key; documentation only; no passport profile sent. |
| timezonefinder | documentation | skipped | None | None | None | Local polygon lookup assessed in documentation; not installed or benchmarked. |
| cldr | documentation | skipped | None | None | None | Local territory/currency reference assessed in documentation; SIX is queried in this run. |
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

Пример: [data/samples/20261014T230158009158Z/open_meteo_city_search.json](../../../data/samples/20261014T230158009158Z/open_meteo_city_search.json).

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

## overpass / museums

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"tourism\"=\"museum\"];);out center 10;"
}
```

Фактические поля: `id`, `lat`, `lon`, `tags`, `tags.addr:city`, `tags.addr:housenumber`, `tags.addr:postcode`, `tags.addr:street`, `tags.alt_name`, `tags.amenity`, `tags.changing_table`, `tags.charge`, `tags.check_date`, `tags.check_date:opening_hours`, `tags.description:opening_hours`, `tags.email`, `tags.fax`, `tags.fee`, `tags.fee:conditional`, `tags.heritage`, `tags.heritage:operator`, `tags.historic`, `tags.internet_access`, `tags.internet_access:fee`, `tags.internet_access:operator`, `tags.level`, `tags.mhs:inscription_date`, `tags.museum`, `tags.name`, `tags.name:de`, `tags.name:el`, `tags.name:en`, `tags.name:fi`, `tags.name:fr`, `tags.name:he`, `tags.name:it`, `tags.name:ja`, `tags.name:ko`, `tags.name:ru`, `tags.name:uk`, `tags.name:zh`, `tags.official_name`, `tags.opening_hours`, `tags.operator`, `tags.operator:type`, `tags.operator:wikidata`, `tags.payment:mastercard`, `tags.payment:visa`, `tags.phone`, `tags.ref:FR:museofile`, `tags.ref:mhs`, `tags.reservation`, `tags.short_name`, `tags.source`, `tags.source:heritage`, `tags.source:internet_access`, `tags.toilets`, `tags.toilets:wheelchair`, `tags.tourism`, `tags.website`, `tags.website:map`, `tags.wheelchair`, `tags.wheelchair:description:de`, `tags.wikidata`, `tags.wikimedia_commons`, `tags.wikipedia`, `type`.

Пример: [data/samples/20261014T230158009158Z/overpass_museums.json](../../../data/samples/20261014T230158009158Z/overpass_museums.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 10/10 | 100% |
| description | 0/10 | 0% |
| website_url | 10/10 | 100% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 0/10 | 0% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 8/10 | 80% |
| entrance_fee | 8/10 | 80% |

Метаданные источника: `{"timestamp_osm_base": "2026-10-14T23:00:51Z", "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."}`.

## overpass / historic

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"historic\"];);out center 10;"
}
```

Фактические поля: `id`, `lat`, `lon`, `tags`, `tags.access`, `tags.amenity`, `tags.artist_name`, `tags.bottle`, `tags.contact:city`, `tags.contact:housenumber`, `tags.contact:postcode`, `tags.contact:street`, `tags.covered`, `tags.description`, `tags.direction`, `tags.drinking_water`, `tags.fee`, `tags.fountain`, `tags.historic`, `tags.indoor`, `tags.latitude`, `tags.lit`, `tags.longitude`, `tags.man_made`, `tags.mapillary`, `tags.material`, `tags.memorial`, `tags.name`, `tags.name:el`, `tags.name:en`, `tags.name:es`, `tags.name:fr`, `tags.name:sk`, `tags.name:zh`, `tags.panoramax`, `tags.seasonal`, `tags.source`, `tags.start_date`, `tags.subject:wikidata`, `tags.survey_point:structure`, `tags.tourism`, `tags.wheelchair`, `tags.wikidata`, `tags.wikimedia_commons`, `tags.wikipedia`, `type`.

Пример: [data/samples/20261014T230158009158Z/overpass_historic.json](../../../data/samples/20261014T230158009158Z/overpass_historic.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 6/10 | 60% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 0/10 | 0% |
| description | 5/10 | 50% |
| website_url | 0/10 | 0% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 0/10 | 0% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 0/10 | 0% |
| entrance_fee | 2/10 | 20% |

Метаданные источника: `{"timestamp_osm_base": "2026-10-14T23:00:51Z", "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."}`.

## overpass / nature

Evidence: `network_attempt`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"leisure\"=\"park\"];nwr(around:3000,48.85341,2.3488)[\"tourism\"=\"viewpoint\"];nwr(around:3000,48.85341,2.3488)[\"natural\"=\"wood\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / restaurants

Evidence: `network_attempt`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"amenity\"~\"^(restaurant|cafe)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / hotels

Evidence: `network_attempt`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"tourism\"~\"^(hotel|hostel|guest_house)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## geoapify / museums

Evidence: `not_called`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:2.3488,48.85341,3000",
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
  "filter": "circle:2.3488,48.85341,3000",
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
  "categories": "leisure.park,natural,tourism.sights.viewpoint",
  "filter": "circle:2.3488,48.85341,3000",
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
  "filter": "circle:2.3488,48.85341,3000",
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
  "filter": "circle:2.3488,48.85341,3000",
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

Evidence: `live_http`; endpoint: `https://api.frankfurter.dev/v2/rate/EUR/RUB`.

Параметры / фильтры:
```json
{}
```

Фактические поля: `base`, `date`, `quote`, `rate`.

Пример: [data/samples/20261014T230158009158Z/frankfurter_eur_rub_v2.json](../../../data/samples/20261014T230158009158Z/frankfurter_eur_rub_v2.json).

## frankfurter / eur_rub_v1

Evidence: `live_http`; endpoint: `https://api.frankfurter.dev/v1/latest`.

Параметры / фильтры:
```json
{
  "base": "EUR",
  "symbols": "RUB"
}
```

Фактические поля: не измерены.

## six / france_currency

Evidence: `network_attempt`; endpoint: `https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml`.

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

## cldr / documentation

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

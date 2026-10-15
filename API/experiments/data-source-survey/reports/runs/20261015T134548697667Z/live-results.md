# Фактический запуск

Run: `20261015T134548697667Z`. UTC: 2026-10-15T13:45:48.697659+00:00.
Offline: False; без ключей: False.

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
  "coordinates": {
    "latitude": 48.85341,
    "longitude": 2.3488
  },
  "coordinate_source": "open_meteo/city_search id=2988507"
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | city_search | ok | 200 | 502.0 | 10 |  |
| overpass | museums | http_error | 502 | 384.6 | None | HTTP error; no retry |
| overpass | historic | http_error | 502 | 286.8 | None | HTTP error; no retry |
| overpass | nature | network_error | None | 20300.1 | None | TimeoutError |
| overpass | restaurants | http_error | 502 | 3787.2 | None | HTTP error; no retry |
| overpass | hotels | http_error | 502 | 562.0 | None | HTTP error; no retry |
| geoapify | museums | ok | 200 | 903.4 | 10 |  |
| geoapify | historic | ok | 200 | 895.3 | 10 |  |
| geoapify | nature | ok | 200 | 928.3 | 10 |  |
| geoapify | restaurants | ok | 200 | 825.2 | 10 |  |
| geoapify | hotels | ok | 200 | 734.3 | 10 |  |
| geoapify | details_1 | ok | 200 | 1114.9 | 1 |  |
| geoapify | details_2 | ok | 200 | 1432.3 | 1 |  |
| opentripmap | museums | skipped | None | None | None | Missing OPENTRIPMAP_API_KEY |
| opentripmap | historic | skipped | None | None | None | Missing OPENTRIPMAP_API_KEY |
| opentripmap | nature | skipped | None | None | None | Missing OPENTRIPMAP_API_KEY |
| opentripmap | restaurants | skipped | None | None | None | Missing OPENTRIPMAP_API_KEY |
| geonames | city_search | skipped | None | None | None | Missing GEONAMES_USERNAME |
| geonames | country_info | skipped | None | None | None | Missing GEONAMES_USERNAME |
| geonames | timezone | skipped | None | None | None | Missing GEONAMES_USERNAME |
| frankfurter | eur_rub_v2 | ok | 200 | 473.2 | 1 |  |
| frankfurter | eur_rub_v1 | http_error | 404 | 382.2 | None | Not found |
| six | france_currency | network_error | None | 442.5 | None | SSLCertVerificationError |
| cldr | france_currency | ok | 200 | 640.2 | 1 |  |
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

Пример: [data/samples/20261015T134548697667Z/open_meteo_city_search.json](../../../data/samples/20261015T134548697667Z/open_meteo_city_search.json).

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

Фактические поля: не измерены.

## overpass / historic

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"historic\"];);out center 10;"
}
```

Фактические поля: не измерены.

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

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"amenity\"~\"^(restaurant|cafe)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## overpass / hotels

Evidence: `live_http`; endpoint: `https://overpass-api.de/api/interpreter`.

Параметры / фильтры:
```json
{
  "data": "[out:json][timeout:15];(nwr(around:3000,48.85341,2.3488)[\"tourism\"~\"^(hotel|hostel|guest_house)$\"];);out center 10;"
}
```

Фактические поля: не измерены.

## geoapify / museums

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

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

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.height`, `properties.building.levels`, `properties.building.roof`, `properties.building.roof.shape`, `properties.building.start_date`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.email`, `properties.contact.fax`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.alt_name`, `properties.datasource.raw.alt_name:es`, `properties.datasource.raw.archaeological_site`, `properties.datasource.raw.architect`, `properties.datasource.raw.architect:wikidata`, `properties.datasource.raw.architect:wikipedia`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.building:start_date`, `properties.datasource.raw.check_date`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:email`, `properties.datasource.raw.contact:instagram`, `properties.datasource.raw.contact:phone`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.email`, `properties.datasource.raw.fare`, `properties.datasource.raw.fax`, `properties.datasource.raw.fee`, `properties.datasource.raw.height`, `properties.datasource.raw.heritage`, `properties.datasource.raw.historic`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.image`, `properties.datasource.raw.lat`, `properties.datasource.raw.location`, `properties.datasource.raw.lon`, `properties.datasource.raw.museum`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ar`, `properties.datasource.raw.name:br`, `properties.datasource.raw.name:de`, `properties.datasource.raw.name:en`, `properties.datasource.raw.name:etymology:wikidata`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:ko`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.official_name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.operator`, `properties.datasource.raw.operator_type`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ramp:wheelchair`, `properties.datasource.raw.roof:material`, `properties.datasource.raw.roof:shape`, `properties.datasource.raw.start_date`, `properties.datasource.raw.street`, `properties.datasource.raw.toilets`, `properties.datasource.raw.toilets:access`, `properties.datasource.raw.toilets:disposal`, `properties.datasource.raw.toilets:position`, `properties.datasource.raw.toilets:wheelchair`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.website:en`, `properties.datasource.raw.wheelchair`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.toilets`, `properties.facilities.wheelchair`, `properties.facilities.wheelchair_details`, `properties.facilities.wheelchair_details.condition`, `properties.formatted`, `properties.historic`, `properties.historic.type`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.ar`, `properties.name_international.br`, `properties.name_international.de`, `properties.name_international.en`, `properties.name_international.fr`, `properties.name_international.ko`, `properties.name_international.ru`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.alt_name`, `properties.name_other.official_name`, `properties.opening_hours`, `properties.operator`, `properties.operator_details`, `properties.operator_details.type`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `properties.website_international`, `properties.website_international.en`, `properties.wiki_and_media`, `properties.wiki_and_media.image`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_museums.json](../../../data/samples/20261015T134548697667Z/geoapify_museums.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 10/10 | 100% |
| description | 0/10 | 0% |
| website_url | 9/10 | 90% |
| image_url | 1/10 | 10% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 10/10 | 100% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 8/10 | 80% |
| entrance_fee | 8/10 | 80% |

## geoapify / historic

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

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

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.area`, `properties.datasource.raw.check_date`, `properties.datasource.raw.commemoration_date`, `properties.datasource.raw.date`, `properties.datasource.raw.direction`, `properties.datasource.raw.highway`, `properties.datasource.raw.historic`, `properties.datasource.raw.image`, `properties.datasource.raw.inscription`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.material`, `properties.datasource.raw.memorial`, `properties.datasource.raw.name`, `properties.datasource.raw.name:de`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.panoramax`, `properties.datasource.raw.place`, `properties.datasource.raw.ref:FR:MemorialGenWeb`, `properties.datasource.raw.ref:FR:Paris:plaque`, `properties.datasource.raw.short_name`, `properties.datasource.raw.subject:wikidata`, `properties.datasource.raw.surface`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikimedia_commons`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.wheelchair`, `properties.formatted`, `properties.historic`, `properties.historic.inscription`, `properties.historic.memorial`, `properties.historic.type`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.de`, `properties.name_international.fr`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.short_name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.way`, `properties.way.surface`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.image`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikimedia_commons`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_historic.json](../../../data/samples/20261015T134548697667Z/geoapify_historic.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 10/10 | 100% |
| description | 0/10 | 0% |
| website_url | 1/10 | 10% |
| image_url | 2/10 | 20% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 10/10 | 100% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 0/10 | 0% |
| entrance_fee | 0/10 | 0% |

## geoapify / nature

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 10,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.levels`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.alt_name`, `properties.datasource.raw.barrier`, `properties.datasource.raw.bridge`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.dog`, `properties.datasource.raw.lat`, `properties.datasource.raw.layer`, `properties.datasource.raw.leisure`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:etymology:wikidata`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.old_name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.operator`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:FANTOIR`, `properties.datasource.raw.smoking`, `properties.datasource.raw.start_date`, `properties.datasource.raw.website`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikimedia_commons`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.dogs`, `properties.facilities.smoking`, `properties.formatted`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.fr`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.alt_name`, `properties.name_other.old_name`, `properties.old_name`, `properties.opening_hours`, `properties.operator`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.suburb`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikimedia_commons`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_nature.json](../../../data/samples/20261015T134548697667Z/geoapify_nature.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 9/10 | 90% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 10/10 | 100% |
| description | 0/10 | 0% |
| website_url | 2/10 | 20% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 10/10 | 100% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 1/10 | 10% |
| entrance_fee | 0/10 | 0% |

## geoapify / restaurants

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

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

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.catering`, `properties.catering.cuisine`, `properties.catering.diet`, `properties.catering.diet.vegetarian`, `properties.catering.stars`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.amenity`, `properties.datasource.raw.check_date`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:email`, `properties.datasource.raw.cuisine`, `properties.datasource.raw.diet:vegetarian`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.indoor_seating`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.mobile`, `properties.datasource.raw.name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.opening_hours:signed`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.outdoor_seating`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:SIRET`, `properties.datasource.raw.stars`, `properties.datasource.raw.street`, `properties.datasource.raw.takeaway`, `properties.datasource.raw.website`, `properties.datasource.raw.website:menu`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.outdoor_seating`, `properties.facilities.takeaway`, `properties.facilities.wheelchair`, `properties.facilities.wheelchair_details`, `properties.facilities.wheelchair_details.condition`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_restaurants.json](../../../data/samples/20261015T134548697667Z/geoapify_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 10/10 | 100% |
| description | 0/10 | 0% |
| website_url | 7/10 | 70% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 10/10 | 100% |
| timezone | 0/10 | 0% |
| cuisine | 8/10 | 80% |
| opening_hours | 3/10 | 30% |
| entrance_fee | 0/10 | 0% |

## geoapify / hotels

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

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

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.accommodation`, `properties.accommodation.stars`, `properties.address_line1`, `properties.address_line2`, `properties.brand`, `properties.brand_details`, `properties.brand_details.wikidata`, `properties.brand_details.wikipedia`, `properties.building`, `properties.building.levels`, `properties.building.roof`, `properties.building.roof.levels`, `properties.building.roof.shape`, `properties.building.type`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.alt_name`, `properties.datasource.raw.brand`, `properties.datasource.raw.brand:wikidata`, `properties.datasource.raw.brand:wikipedia`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:email`, `properties.datasource.raw.email`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.internet_access`, `properties.datasource.raw.internet_access:fee`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:SIRET`, `properties.datasource.raw.roof:levels`, `properties.datasource.raw.roof:shape`, `properties.datasource.raw.smoking`, `properties.datasource.raw.stars`, `properties.datasource.raw.street`, `properties.datasource.raw.toilets:wheelchair`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.internet_access`, `properties.facilities.smoking`, `properties.facilities.toilets`, `properties.facilities.wheelchair`, `properties.facilities.wheelchair_details`, `properties.facilities.wheelchair_details.condition`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.fr`, `properties.name_other`, `properties.name_other.alt_name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_hotels.json](../../../data/samples/20261015T134548697667Z/geoapify_hotels.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 10/10 | 100% |
| name | 10/10 | 100% |
| category | 10/10 | 100% |
| latitude | 10/10 | 100% |
| longitude | 10/10 | 100% |
| address | 10/10 | 100% |
| description | 0/10 | 0% |
| website_url | 6/10 | 60% |
| image_url | 0/10 | 0% |
| rating | 0/10 | 0% |
| price_amount | 0/10 | 0% |
| price_currency | 0/10 | 0% |
| price_period_or_total | 0/10 | 0% |
| availability | 0/10 | 0% |
| country_code | 10/10 | 100% |
| timezone | 0/10 | 0% |
| cuisine | 0/10 | 0% |
| opening_hours | 0/10 | 0% |
| entrance_fee | 0/10 | 0% |

## geoapify / details_1

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/place-details`.

Параметры / фильтры:
```json
{
  "id": "51923e6eb81cbe0240594bb8cecf706e4840f00102f90152fd2e0100000000920312426f7572736520646520436f6d6d65726365",
  "features": "details",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `bbox`, `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.height`, `properties.building.start_date`, `properties.categories`, `properties.city`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.addr:city`, `properties.datasource.raw.addr:housenumber`, `properties.datasource.raw.addr:postcode`, `properties.datasource.raw.addr:street`, `properties.datasource.raw.architect`, `properties.datasource.raw.architect:wikidata`, `properties.datasource.raw.architect:wikipedia`, `properties.datasource.raw.building`, `properties.datasource.raw.building:start_date`, `properties.datasource.raw.check_date`, `properties.datasource.raw.contact:email`, `properties.datasource.raw.contact:phone`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.fee`, `properties.datasource.raw.height`, `properties.datasource.raw.image`, `properties.datasource.raw.museum`, `properties.datasource.raw.name`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.official_name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.operator`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.ramp:wheelchair`, `properties.datasource.raw.roof:material`, `properties.datasource.raw.toilets`, `properties.datasource.raw.toilets:access`, `properties.datasource.raw.toilets:disposal`, `properties.datasource.raw.toilets:position`, `properties.datasource.raw.toilets:wheelchair`, `properties.datasource.raw.tourism`, `properties.datasource.raw.wheelchair`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.district`, `properties.facilities`, `properties.facilities.toilets`, `properties.facilities.wheelchair`, `properties.feature_type`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.official_name`, `properties.opening_hours`, `properties.operator`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.timezone`, `properties.timezone.abbreviation_DST`, `properties.timezone.abbreviation_STD`, `properties.timezone.name`, `properties.timezone.offset_DST`, `properties.timezone.offset_DST_seconds`, `properties.timezone.offset_STD`, `properties.timezone.offset_STD_seconds`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.image`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_details_1.json](../../../data/samples/20261015T134548697667Z/geoapify_details_1.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 1/1 | 100% |
| longitude | 1/1 | 100% |
| address | 1/1 | 100% |
| description | 0/1 | 0% |
| website_url | 1/1 | 100% |
| image_url | 1/1 | 100% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 1/1 | 100% |
| cuisine | 0/1 | 0% |
| opening_hours | 1/1 | 100% |
| entrance_fee | 1/1 | 100% |

## geoapify / details_2

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/place-details`.

Параметры / фильтры:
```json
{
  "id": "51e9bef79221c2024059ec432800106c4840f00103f90160901f9f0200000092030c4d7573c3a965204375726965",
  "features": "details",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `bbox`, `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.fee`, `properties.datasource.raw.name`, `properties.datasource.raw.name:etymology:wikidata`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.district`, `properties.feature_type`, `properties.formatted`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.state`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.timezone`, `properties.timezone.abbreviation_DST`, `properties.timezone.abbreviation_STD`, `properties.timezone.name`, `properties.timezone.offset_DST`, `properties.timezone.offset_DST_seconds`, `properties.timezone.offset_STD`, `properties.timezone.offset_STD_seconds`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T134548697667Z/geoapify_details_2.json](../../../data/samples/20261015T134548697667Z/geoapify_details_2.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 1/1 | 100% |
| longitude | 1/1 | 100% |
| address | 1/1 | 100% |
| description | 0/1 | 0% |
| website_url | 1/1 | 100% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 1/1 | 100% |
| cuisine | 0/1 | 0% |
| opening_hours | 1/1 | 100% |
| entrance_fee | 1/1 | 100% |

## opentripmap / museums

Evidence: `not_called`; endpoint: `https://api.opentripmap.com/0.1/en/places/radius`.

Параметры / фильтры:
```json
{
  "lat": 48.85341,
  "lon": 2.3488,
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
  "lat": 48.85341,
  "lon": 2.3488,
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
  "lat": 48.85341,
  "lon": 2.3488,
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
  "lat": 48.85341,
  "lon": 2.3488,
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

Пример: [data/samples/20261015T134548697667Z/frankfurter_eur_rub_v2.json](../../../data/samples/20261015T134548697667Z/frankfurter_eur_rub_v2.json).

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

## cldr / france_currency

Evidence: `live_http`; endpoint: `https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/cldr-core/supplemental/currencyData.json`.

Параметры / фильтры:
```json
{}
```

Фактические поля: `country_code`, `currency_code`, `validity`, `validity._from`, `version`, `version._cldrVersion`, `version._unicodeVersion`.

Пример: [data/samples/20261015T134548697667Z/cldr_france_currency.json](../../../data/samples/20261015T134548697667Z/cldr_france_currency.json).

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

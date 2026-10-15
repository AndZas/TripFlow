# Фактический запуск

Run: `20261015T150210175612Z`. UTC: 2026-10-15T15:02:10.175602+00:00.
Offline: False; без ключей: False.

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
  "coordinates": {
    "paris": {
      "latitude": 48.85341,
      "longitude": 2.3488,
      "source": "open_meteo",
      "id": 2988507
    },
    "moscow": {
      "latitude": 55.75204,
      "longitude": 37.61781,
      "source": "open_meteo",
      "id": 524901
    },
    "istanbul": {
      "latitude": 41.01384,
      "longitude": 28.94966,
      "source": "open_meteo",
      "id": 745044
    },
    "suzdal": {
      "latitude": 56.42408,
      "longitude": 40.44978,
      "source": "open_meteo",
      "id": 485824
    }
  },
  "no_hotel_offer_queries": true,
  "attempted_requests": 40
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | paris_city | ok | 200 | 3917.6 | 10 |  |
| geonames | paris_city | ok | 200 | 646.2 | 2 |  |
| geonames | FR_country | ok | 200 | 577.9 | 1 |  |
| geoapify | paris_museums | ok | 200 | 717.6 | 5 |  |
| geoapify | paris_historic | ok | 200 | 1819.1 | 5 |  |
| geoapify | paris_nature | ok | 200 | 888.5 | 5 |  |
| geoapify | paris_restaurants | ok | 200 | 2456.4 | 5 |  |
| geoapify | paris_hotels | ok | 200 | 666.1 | 5 |  |
| open_meteo | moscow_city | ok | 200 | 487.8 | 5 |  |
| geonames | moscow_city | ok | 200 | 377.3 | 1 |  |
| geonames | RU_country | ok | 200 | 1030.9 | 1 |  |
| geoapify | moscow_museums | ok | 200 | 850.9 | 5 |  |
| geoapify | moscow_historic | ok | 200 | 624.5 | 5 |  |
| geoapify | moscow_nature | ok | 200 | 566.9 | 5 |  |
| geoapify | moscow_restaurants | ok | 200 | 1775.6 | 5 |  |
| geoapify | moscow_hotels | ok | 200 | 4054.2 | 5 |  |
| open_meteo | istanbul_city | ok | 200 | 597.0 | 5 |  |
| geonames | istanbul_city | ok | 200 | 467.2 | 1 |  |
| geonames | TR_country | ok | 200 | 566.6 | 1 |  |
| geoapify | istanbul_museums | ok | 200 | 715.7 | 5 |  |
| geoapify | istanbul_historic | ok | 200 | 1530.7 | 5 |  |
| geoapify | istanbul_nature | ok | 200 | 955.5 | 5 |  |
| geoapify | istanbul_restaurants | ok | 200 | 635.2 | 5 |  |
| geoapify | istanbul_hotels | ok | 200 | 473.8 | 5 |  |
| open_meteo | suzdal_city | ok | 200 | 466.0 | 10 |  |
| geonames | suzdal_city | ok | 200 | 452.4 | 1 |  |
| geoapify | suzdal_museums | ok | 200 | 758.2 | 5 |  |
| geoapify | suzdal_historic | ok | 200 | 717.6 | 5 |  |
| geoapify | suzdal_nature | ok | 200 | 615.9 | 5 |  |
| geoapify | suzdal_restaurants | ok | 200 | 523.0 | 5 |  |
| geoapify | suzdal_hotels | ok | 200 | 647.5 | 5 |  |
| open_meteo | russian_name | ok | 200 | 482.8 | 2 |  |
| geonames | russian_name | ok | 200 | 570.3 | 7 |  |
| open_meteo | ambiguous_name | ok | 200 | 572.2 | 10 |  |
| open_meteo | country_filter | ok | 200 | 616.1 | 10 |  |
| open_meteo | unknown_city | empty | 200 | 871.0 | 0 |  |
| geoapify | empty_place_name | empty | 200 | 542.9 | 0 |  |
| geoapify | vegetarian_restaurants | ok | 200 | 647.8 | 5 |  |
| geoapify | hotels_details | ok | 200 | 1122.3 | 1 |  |
| geoapify | restaurants_details | ok | 200 | 1943.1 | 1 |  |

## open_meteo / paris_city

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Paris",
  "count": 10,
  "language": "en",
  "countryCode": "FR"
}
```

Фактические поля: `admin1`, `admin1_id`, `admin2`, `admin2_id`, `admin3`, `admin3_id`, `admin4`, `admin4_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `postcodes`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_paris_city.json](../../../data/samples/20261015T150210175612Z/open_meteo_paris_city.json).

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

## geonames / paris_city

Evidence: `live_http`; endpoint: `https://secure.geonames.org/searchJSON`.

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

Фактические поля: `adminCode1`, `adminCode2`, `adminCode3`, `adminCode4`, `adminCodes1`, `adminCodes1.ISO3166_2`, `adminCodes2`, `adminCodes2.ISO3166_2`, `adminId1`, `adminId2`, `adminId3`, `adminId4`, `adminName1`, `adminName2`, `adminName3`, `adminName4`, `adminName5`, `alternateNames`, `alternateNames[].lang`, `alternateNames[].name`, `asciiName`, `astergdem`, `bbox`, `bbox.accuracyLevel`, `bbox.east`, `bbox.north`, `bbox.south`, `bbox.west`, `continentCode`, `countryCode`, `countryId`, `countryName`, `fcl`, `fclName`, `fcode`, `fcodeName`, `geonameId`, `lat`, `lng`, `name`, `population`, `score`, `srtm3`, `timezone`, `timezone.dstOffset`, `timezone.gmtOffset`, `timezone.sunrise`, `timezone.sunset`, `timezone.time`, `timezone.timeZoneId`, `toponymName`.

Пример: [data/samples/20261015T150210175612Z/geonames_paris_city.json](../../../data/samples/20261015T150210175612Z/geonames_paris_city.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 2/2 | 100% |
| name | 2/2 | 100% |
| category | 2/2 | 100% |
| latitude | 2/2 | 100% |
| longitude | 2/2 | 100% |
| address | 0/2 | 0% |
| description | 0/2 | 0% |
| website_url | 0/2 | 0% |
| image_url | 0/2 | 0% |
| rating | 0/2 | 0% |
| price_amount | 0/2 | 0% |
| price_currency | 0/2 | 0% |
| price_period_or_total | 0/2 | 0% |
| availability | 0/2 | 0% |
| country_code | 2/2 | 100% |
| timezone | 2/2 | 100% |
| cuisine | 0/2 | 0% |
| opening_hours | 0/2 | 0% |
| entrance_fee | 0/2 | 0% |

## geonames / FR_country

Evidence: `live_http`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "FR",
  "username": "[REDACTED]"
}
```

Фактические поля: `areaInSqKm`, `capital`, `continent`, `continentName`, `countryCode`, `countryName`, `currencyCode`, `east`, `fipsCode`, `geonameId`, `isoAlpha3`, `isoNumeric`, `languages`, `north`, `population`, `postalCodeFormat`, `south`, `west`.

Пример: [data/samples/20261015T150210175612Z/geonames_FR_country.json](../../../data/samples/20261015T150210175612Z/geonames_FR_country.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 0/1 | 0% |
| longitude | 0/1 | 0% |
| address | 0/1 | 0% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 0/1 | 0% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geoapify / paris_museums

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.height`, `properties.building.levels`, `properties.building.roof`, `properties.building.roof.shape`, `properties.building.start_date`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.alt_name:es`, `properties.datasource.raw.architect`, `properties.datasource.raw.architect:wikidata`, `properties.datasource.raw.architect:wikipedia`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.building:start_date`, `properties.datasource.raw.check_date`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:email`, `properties.datasource.raw.contact:instagram`, `properties.datasource.raw.contact:phone`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.email`, `properties.datasource.raw.fee`, `properties.datasource.raw.height`, `properties.datasource.raw.heritage`, `properties.datasource.raw.historic`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.image`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.museum`, `properties.datasource.raw.name`, `properties.datasource.raw.name:br`, `properties.datasource.raw.name:de`, `properties.datasource.raw.name:etymology:wikidata`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.official_name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.operator`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ramp:wheelchair`, `properties.datasource.raw.roof:material`, `properties.datasource.raw.roof:shape`, `properties.datasource.raw.street`, `properties.datasource.raw.toilets`, `properties.datasource.raw.toilets:access`, `properties.datasource.raw.toilets:disposal`, `properties.datasource.raw.toilets:position`, `properties.datasource.raw.toilets:wheelchair`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.toilets`, `properties.facilities.wheelchair`, `properties.facilities.wheelchair_details`, `properties.facilities.wheelchair_details.condition`, `properties.formatted`, `properties.historic`, `properties.historic.type`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.br`, `properties.name_international.de`, `properties.name_international.fr`, `properties.name_international.ru`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.official_name`, `properties.opening_hours`, `properties.operator`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.image`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_paris_museums.json](../../../data/samples/20261015T150210175612Z/geoapify_paris_museums.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 4/5 | 80% |
| image_url | 1/5 | 20% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 4/5 | 80% |
| entrance_fee | 4/5 | 80% |

## geoapify / paris_historic

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.area`, `properties.datasource.raw.check_date`, `properties.datasource.raw.date`, `properties.datasource.raw.direction`, `properties.datasource.raw.highway`, `properties.datasource.raw.historic`, `properties.datasource.raw.inscription`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.material`, `properties.datasource.raw.memorial`, `properties.datasource.raw.name`, `properties.datasource.raw.name:de`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.panoramax`, `properties.datasource.raw.place`, `properties.datasource.raw.ref:FR:MemorialGenWeb`, `properties.datasource.raw.ref:FR:Paris:plaque`, `properties.datasource.raw.short_name`, `properties.datasource.raw.surface`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikimedia_commons`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.wheelchair`, `properties.formatted`, `properties.historic`, `properties.historic.inscription`, `properties.historic.memorial`, `properties.historic.type`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.de`, `properties.name_international.fr`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.short_name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.way`, `properties.way.surface`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikimedia_commons`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_paris_historic.json](../../../data/samples/20261015T150210175612Z/geoapify_paris_historic.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 1/5 | 20% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / paris_nature

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.levels`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.barrier`, `properties.datasource.raw.bridge`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.dog`, `properties.datasource.raw.lat`, `properties.datasource.raw.layer`, `properties.datasource.raw.leisure`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:etymology:wikidata`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.old_name`, `properties.datasource.raw.operator`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:FANTOIR`, `properties.datasource.raw.start_date`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.dogs`, `properties.formatted`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.fr`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.old_name`, `properties.old_name`, `properties.operator`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.suburb`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_paris_nature.json](../../../data/samples/20261015T150210175612Z/geoapify_paris_nature.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 1/5 | 20% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / paris_restaurants

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.catering`, `properties.catering.cuisine`, `properties.catering.diet`, `properties.catering.diet.vegetarian`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.amenity`, `properties.datasource.raw.check_date`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.city`, `properties.datasource.raw.cuisine`, `properties.datasource.raw.diet:vegetarian`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.mobile`, `properties.datasource.raw.name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.opening_hours:signed`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:SIRET`, `properties.datasource.raw.street`, `properties.datasource.raw.takeaway`, `properties.datasource.raw.website`, `properties.datasource.raw.website:menu`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.takeaway`, `properties.facilities.wheelchair`, `properties.facilities.wheelchair_details`, `properties.facilities.wheelchair_details.condition`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_paris_restaurants.json](../../../data/samples/20261015T150210175612Z/geoapify_paris_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 2/5 | 40% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 3/5 | 60% |
| opening_hours | 1/5 | 20% |
| entrance_fee | 0/5 | 0% |

## geoapify / paris_hotels

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.accommodation`, `properties.accommodation.stars`, `properties.address_line1`, `properties.address_line2`, `properties.brand`, `properties.brand_details`, `properties.brand_details.wikidata`, `properties.brand_details.wikipedia`, `properties.building`, `properties.building.levels`, `properties.building.roof`, `properties.building.roof.levels`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.alt_name`, `properties.datasource.raw.brand`, `properties.datasource.raw.brand:wikidata`, `properties.datasource.raw.brand:wikipedia`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.email`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:SIRET`, `properties.datasource.raw.roof:levels`, `properties.datasource.raw.stars`, `properties.datasource.raw.street`, `properties.datasource.raw.toilets:wheelchair`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.toilets`, `properties.facilities.wheelchair`, `properties.facilities.wheelchair_details`, `properties.facilities.wheelchair_details.condition`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.fr`, `properties.name_other`, `properties.name_other.alt_name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_paris_hotels.json](../../../data/samples/20261015T150210175612Z/geoapify_paris_hotels.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 2/5 | 40% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## open_meteo / moscow_city

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Moscow",
  "count": 10,
  "language": "en",
  "countryCode": "RU"
}
```

Фактические поля: `admin1`, `admin1_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_moscow_city.json](../../../data/samples/20261015T150210175612Z/open_meteo_moscow_city.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 0/5 | 0% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 5/5 | 100% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geonames / moscow_city

Evidence: `live_http`; endpoint: `https://secure.geonames.org/searchJSON`.

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

Фактические поля: `adminCode1`, `adminCodes1`, `adminCodes1.ISO3166_2`, `adminId1`, `adminName1`, `adminName2`, `adminName3`, `adminName4`, `adminName5`, `alternateNames`, `alternateNames[].isColloquial`, `alternateNames[].isHistoric`, `alternateNames[].isPreferredName`, `alternateNames[].isShortName`, `alternateNames[].lang`, `alternateNames[].name`, `asciiName`, `astergdem`, `bbox`, `bbox.accuracyLevel`, `bbox.east`, `bbox.north`, `bbox.south`, `bbox.west`, `continentCode`, `countryCode`, `countryId`, `countryName`, `fcl`, `fclName`, `fcode`, `fcodeName`, `geonameId`, `lat`, `lng`, `name`, `population`, `score`, `srtm3`, `timezone`, `timezone.dstOffset`, `timezone.gmtOffset`, `timezone.sunrise`, `timezone.sunset`, `timezone.time`, `timezone.timeZoneId`, `toponymName`.

Пример: [data/samples/20261015T150210175612Z/geonames_moscow_city.json](../../../data/samples/20261015T150210175612Z/geonames_moscow_city.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 1/1 | 100% |
| longitude | 1/1 | 100% |
| address | 0/1 | 0% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 1/1 | 100% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geonames / RU_country

Evidence: `live_http`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "RU",
  "username": "[REDACTED]"
}
```

Фактические поля: `areaInSqKm`, `capital`, `continent`, `continentName`, `countryCode`, `countryName`, `currencyCode`, `east`, `fipsCode`, `geonameId`, `isoAlpha3`, `isoNumeric`, `languages`, `north`, `population`, `postalCodeFormat`, `south`, `west`.

Пример: [data/samples/20261015T150210175612Z/geonames_RU_country.json](../../../data/samples/20261015T150210175612Z/geonames_RU_country.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 0/1 | 0% |
| longitude | 0/1 | 0% |
| address | 0/1 | 0% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 0/1 | 0% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geoapify / moscow_museums

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:37.61781,55.75204,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.architecture`, `properties.building.color`, `properties.building.levels`, `properties.building.material`, `properties.building.roof`, `properties.building.roof.color`, `properties.building.roof.shape`, `properties.building.start_date`, `properties.building.type`, `properties.categories`, `properties.city`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.addr2:housenumber`, `properties.datasource.raw.addr2:street`, `properties.datasource.raw.alt_name`, `properties.datasource.raw.building`, `properties.datasource.raw.building:architecture`, `properties.datasource.raw.building:colour`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.building:material`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:phone`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.country`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.museum`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ca`, `properties.datasource.raw.name:de`, `properties.datasource.raw.name:en`, `properties.datasource.raw.name:eo`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:he`, `properties.datasource.raw.name:hr`, `properties.datasource.raw.name:it`, `properties.datasource.raw.name:ka`, `properties.datasource.raw.name:pl`, `properties.datasource.raw.name:pt`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.name:sv`, `properties.datasource.raw.name:uk`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.official_name`, `properties.datasource.raw.official_name:ru`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.operator`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.roof:colour`, `properties.datasource.raw.roof:material`, `properties.datasource.raw.roof:shape`, `properties.datasource.raw.start_date`, `properties.datasource.raw.street`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.ca`, `properties.name_international.de`, `properties.name_international.en`, `properties.name_international.eo`, `properties.name_international.fr`, `properties.name_international.he`, `properties.name_international.hr`, `properties.name_international.it`, `properties.name_international.ka`, `properties.name_international.pl`, `properties.name_international.pt`, `properties.name_international.ru`, `properties.name_international.sv`, `properties.name_international.uk`, `properties.name_international.zh`, `properties.name_other`, `properties.name_other.alt_name`, `properties.name_other.official_name`, `properties.opening_hours`, `properties.operator`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.street`, `properties.suburb`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_moscow_museums.json](../../../data/samples/20261015T150210175612Z/geoapify_moscow_museums.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 3/5 | 60% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 2/5 | 40% |
| entrance_fee | 0/5 | 0% |

## geoapify / moscow_historic

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:37.61781,55.75204,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.historic`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.inscription`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.memorial`, `properties.datasource.raw.memorial:subject`, `properties.datasource.raw.name`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.postcode`, `properties.datasource.raw.start_date`, `properties.datasource.raw.street`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.historic`, `properties.historic.inscription`, `properties.historic.memorial`, `properties.historic.start_date`, `properties.historic.type`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.street`, `properties.suburb`, `properties.wiki_and_media`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_moscow_historic.json](../../../data/samples/20261015T150210175612Z/geoapify_moscow_historic.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / moscow_nature

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:37.61781,55.75204,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.barrier`, `properties.datasource.raw.lat`, `properties.datasource.raw.leisure`, `properties.datasource.raw.loc_name`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.natural`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.formatted`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_other`, `properties.name_other.loc_name`, `properties.place_id`, `properties.quarter`, `properties.region`, `properties.state`, `properties.suburb`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_moscow_nature.json](../../../data/samples/20261015T150210175612Z/geoapify_moscow_nature.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 4/5 | 80% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / moscow_restaurants

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:37.61781,55.75204,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.brand`, `properties.brand_details`, `properties.brand_details.wikidata`, `properties.categories`, `properties.catering`, `properties.catering.cuisine`, `properties.catering.diet`, `properties.catering.diet.vegan`, `properties.catering.diet.vegetarian`, `properties.city`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.amenity`, `properties.datasource.raw.brand`, `properties.datasource.raw.brand:en`, `properties.datasource.raw.brand:wikidata`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:email`, `properties.datasource.raw.contact:facebook`, `properties.datasource.raw.contact:instagram`, `properties.datasource.raw.contact:phone`, `properties.datasource.raw.contact:telegram`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.country`, `properties.datasource.raw.cuisine`, `properties.datasource.raw.diet:vegan`, `properties.datasource.raw.diet:vegetarian`, `properties.datasource.raw.drink:coffee`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.level`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:en`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.postcode`, `properties.datasource.raw.street`, `properties.datasource.raw.takeaway`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.facilities`, `properties.facilities.takeaway`, `properties.facilities.wheelchair`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.en`, `properties.name_international.ru`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_moscow_restaurants.json](../../../data/samples/20261015T150210175612Z/geoapify_moscow_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 3/5 | 60% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 3/5 | 60% |
| opening_hours | 2/5 | 40% |
| entrance_fee | 0/5 | 0% |

## geoapify / moscow_hotels

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:37.61781,55.75204,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.building`, `properties.building.levels`, `properties.building.material`, `properties.building.type`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.building:material`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:vk`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.level`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.operator`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.street`, `properties.datasource.raw.tourism`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.operator`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_moscow_hotels.json](../../../data/samples/20261015T150210175612Z/geoapify_moscow_hotels.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 1/5 | 20% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## open_meteo / istanbul_city

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Istanbul",
  "count": 10,
  "language": "en",
  "countryCode": "TR"
}
```

Фактические поля: `admin1`, `admin1_id`, `admin2`, `admin2_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `postcodes`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_istanbul_city.json](../../../data/samples/20261015T150210175612Z/open_meteo_istanbul_city.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 0/5 | 0% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 5/5 | 100% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geonames / istanbul_city

Evidence: `live_http`; endpoint: `https://secure.geonames.org/searchJSON`.

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

Фактические поля: `adminCode1`, `adminCodes1`, `adminCodes1.ISO3166_2`, `adminId1`, `adminName1`, `adminName2`, `adminName3`, `adminName4`, `adminName5`, `alternateNames`, `alternateNames[].isHistoric`, `alternateNames[].isPreferredName`, `alternateNames[].lang`, `alternateNames[].name`, `asciiName`, `astergdem`, `bbox`, `bbox.accuracyLevel`, `bbox.east`, `bbox.north`, `bbox.south`, `bbox.west`, `continentCode`, `countryCode`, `countryId`, `countryName`, `fcl`, `fclName`, `fcode`, `fcodeName`, `geonameId`, `lat`, `lng`, `name`, `population`, `score`, `srtm3`, `timezone`, `timezone.dstOffset`, `timezone.gmtOffset`, `timezone.sunrise`, `timezone.sunset`, `timezone.time`, `timezone.timeZoneId`, `toponymName`.

Пример: [data/samples/20261015T150210175612Z/geonames_istanbul_city.json](../../../data/samples/20261015T150210175612Z/geonames_istanbul_city.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 1/1 | 100% |
| longitude | 1/1 | 100% |
| address | 0/1 | 0% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 1/1 | 100% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geonames / TR_country

Evidence: `live_http`; endpoint: `https://secure.geonames.org/countryInfoJSON`.

Параметры / фильтры:
```json
{
  "country": "TR",
  "username": "[REDACTED]"
}
```

Фактические поля: `areaInSqKm`, `capital`, `continent`, `continentName`, `countryCode`, `countryName`, `currencyCode`, `east`, `fipsCode`, `geonameId`, `isoAlpha3`, `isoNumeric`, `languages`, `north`, `population`, `postalCodeFormat`, `south`, `west`.

Пример: [data/samples/20261015T150210175612Z/geonames_TR_country.json](../../../data/samples/20261015T150210175612Z/geonames_TR_country.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 0/1 | 0% |
| longitude | 0/1 | 0% |
| address | 0/1 | 0% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 0/1 | 0% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geoapify / istanbul_museums

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:28.94966,41.01384,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.contact`, `properties.contact.email`, `properties.contact.fax`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.building`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.description`, `properties.datasource.raw.district`, `properties.datasource.raw.email`, `properties.datasource.raw.fax`, `properties.datasource.raw.fee`, `properties.datasource.raw.image`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.museum`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ar`, `properties.datasource.raw.name:br`, `properties.datasource.raw.name:de`, `properties.datasource.raw.name:en`, `properties.datasource.raw.name:fa`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:it`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.name:tr`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.operator`, `properties.datasource.raw.operator:type`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.street`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wikidata`, `properties.datasource.raw.wikimedia_commons`, `properties.datasource.raw.wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.description`, `properties.details`, `properties.formatted`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.ar`, `properties.name_international.br`, `properties.name_international.de`, `properties.name_international.en`, `properties.name_international.fa`, `properties.name_international.fr`, `properties.name_international.it`, `properties.name_international.ru`, `properties.name_international.tr`, `properties.name_international.zh`, `properties.opening_hours`, `properties.operator`, `properties.operator_details`, `properties.operator_details.type`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.street`, `properties.suburb`, `properties.town`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.image`, `properties.wiki_and_media.wikidata`, `properties.wiki_and_media.wikimedia_commons`, `properties.wiki_and_media.wikipedia`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_istanbul_museums.json](../../../data/samples/20261015T150210175612Z/geoapify_istanbul_museums.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 2/5 | 40% |
| website_url | 3/5 | 60% |
| image_url | 1/5 | 20% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 2/5 | 40% |
| entrance_fee | 2/5 | 40% |

## geoapify / istanbul_historic

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:28.94966,41.01384,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.designation`, `properties.datasource.raw.historic`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.name:tr`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.historic`, `properties.historic.type`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.ru`, `properties.name_international.tr`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.street`, `properties.suburb`, `properties.town`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_istanbul_historic.json](../../../data/samples/20261015T150210175612Z/geoapify_istanbul_historic.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / istanbul_nature

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:28.94966,41.01384,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.lat`, `properties.datasource.raw.leisure`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.suburb`, `properties.town`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_istanbul_nature.json](../../../data/samples/20261015T150210175612Z/geoapify_istanbul_nature.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 2/5 | 40% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / istanbul_restaurants

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:28.94966,41.01384,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.amenity`, `properties.datasource.raw.city`, `properties.datasource.raw.district`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ar`, `properties.datasource.raw.name:tr`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.street`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.ar`, `properties.name_international.tr`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.street`, `properties.suburb`, `properties.town`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_istanbul_restaurants.json](../../../data/samples/20261015T150210175612Z/geoapify_istanbul_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / istanbul_hotels

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:28.94966,41.01384,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.brand`, `properties.brand_details`, `properties.brand_details.wikidata`, `properties.building`, `properties.building.levels`, `properties.building.roof`, `properties.building.roof.orientation`, `properties.building.roof.shape`, `properties.categories`, `properties.city`, `properties.contact`, `properties.contact.fax`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.bar`, `properties.datasource.raw.brand`, `properties.datasource.raw.brand:wikidata`, `properties.datasource.raw.building`, `properties.datasource.raw.building:levels`, `properties.datasource.raw.check_date`, `properties.datasource.raw.city`, `properties.datasource.raw.district`, `properties.datasource.raw.fax`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:tr`, `properties.datasource.raw.neighbourhood`, `properties.datasource.raw.official_name`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.roof:orientation`, `properties.datasource.raw.roof:shape`, `properties.datasource.raw.street`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.wheelchair`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.tr`, `properties.name_other`, `properties.name_other.official_name`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.street`, `properties.suburb`, `properties.town`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_istanbul_hotels.json](../../../data/samples/20261015T150210175612Z/geoapify_istanbul_hotels.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 2/5 | 40% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 1/5 | 20% |
| entrance_fee | 0/5 | 0% |

## open_meteo / suzdal_city

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Suzdal",
  "count": 10,
  "language": "en",
  "countryCode": "RU"
}
```

Фактические поля: `admin1`, `admin1_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_suzdal_city.json](../../../data/samples/20261015T150210175612Z/open_meteo_suzdal_city.json).

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

## geonames / suzdal_city

Evidence: `live_http`; endpoint: `https://secure.geonames.org/searchJSON`.

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

Фактические поля: `adminCode1`, `adminCodes1`, `adminCodes1.ISO3166_2`, `adminId1`, `adminName1`, `adminName2`, `adminName3`, `adminName4`, `adminName5`, `alternateNames`, `alternateNames[].isPreferredName`, `alternateNames[].lang`, `alternateNames[].name`, `asciiName`, `astergdem`, `bbox`, `bbox.accuracyLevel`, `bbox.east`, `bbox.north`, `bbox.south`, `bbox.west`, `continentCode`, `countryCode`, `countryId`, `countryName`, `fcl`, `fclName`, `fcode`, `fcodeName`, `geonameId`, `lat`, `lng`, `name`, `population`, `score`, `srtm3`, `timezone`, `timezone.dstOffset`, `timezone.gmtOffset`, `timezone.sunrise`, `timezone.sunset`, `timezone.time`, `timezone.timeZoneId`, `toponymName`.

Пример: [data/samples/20261015T150210175612Z/geonames_suzdal_city.json](../../../data/samples/20261015T150210175612Z/geonames_suzdal_city.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 1/1 | 100% |
| longitude | 1/1 | 100% |
| address | 0/1 | 0% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 1/1 | 100% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geoapify / suzdal_museums

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:40.44978,56.42408,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.fee`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.street`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.municipality`, `properties.name`, `properties.name_international`, `properties.name_international.ru`, `properties.name_international.zh`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.street`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_suzdal_museums.json](../../../data/samples/20261015T150210175612Z/geoapify_suzdal_museums.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 1/5 | 20% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 1/5 | 20% |
| entrance_fee | 2/5 | 40% |

## geoapify / suzdal_historic

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "tourism.sights",
  "filter": "circle:40.44978,56.42408,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.building`, `properties.datasource.raw.description`, `properties.datasource.raw.historic`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.memorial`, `properties.datasource.raw.memorial:subject`, `properties.datasource.raw.name`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.subject:wikidata`, `properties.datasource.raw.subject:wikipedia`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.description`, `properties.details`, `properties.formatted`, `properties.historic`, `properties.historic.memorial`, `properties.historic.type`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.municipality`, `properties.name`, `properties.name_international`, `properties.name_international.ru`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.street`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_suzdal_historic.json](../../../data/samples/20261015T150210175612Z/geoapify_suzdal_historic.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 1/5 | 20% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / suzdal_nature

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "leisure.park,natural,tourism.attraction.viewpoint",
  "filter": "circle:40.44978,56.42408,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.barrier`, `properties.datasource.raw.lat`, `properties.datasource.raw.leisure`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.natural`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.tourism`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.municipality`, `properties.name`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.street`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_suzdal_nature.json](../../../data/samples/20261015T150210175612Z/geoapify_suzdal_nature.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 1/5 | 20% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 0/5 | 0% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## geoapify / suzdal_restaurants

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:40.44978,56.42408,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.catering`, `properties.catering.capacity`, `properties.catering.cuisine`, `properties.city`, `properties.contact`, `properties.contact.email`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.alt_name`, `properties.datasource.raw.amenity`, `properties.datasource.raw.building`, `properties.datasource.raw.capacity`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:facebook`, `properties.datasource.raw.contact:instagram`, `properties.datasource.raw.contact:vk`, `properties.datasource.raw.cuisine`, `properties.datasource.raw.delivery`, `properties.datasource.raw.email`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.image`, `properties.datasource.raw.indoor_seating`, `properties.datasource.raw.int_name`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:en`, `properties.datasource.raw.name:ru`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.outdoor_seating`, `properties.datasource.raw.payment:cash`, `properties.datasource.raw.payment:credit_cards`, `properties.datasource.raw.payment:maestro`, `properties.datasource.raw.payment:mastercard`, `properties.datasource.raw.payment:visa`, `properties.datasource.raw.payment:visa_electron`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.start_date`, `properties.datasource.raw.street`, `properties.datasource.raw.website`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.facilities`, `properties.facilities.delivery`, `properties.facilities.outdoor_seating`, `properties.facilities.wheelchair`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.municipality`, `properties.name`, `properties.name_international`, `properties.name_international.en`, `properties.name_international.ru`, `properties.name_other`, `properties.name_other.alt_name`, `properties.opening_hours`, `properties.payment_options`, `properties.payment_options.cash`, `properties.payment_options.credit_cards`, `properties.payment_options.maestro`, `properties.payment_options.mastercard`, `properties.payment_options.visa`, `properties.payment_options.visa_electron`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.street`, `properties.website`, `properties.wiki_and_media`, `properties.wiki_and_media.image`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_suzdal_restaurants.json](../../../data/samples/20261015T150210175612Z/geoapify_suzdal_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 2/5 | 40% |
| image_url | 1/5 | 20% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 3/5 | 60% |
| opening_hours | 1/5 | 20% |
| entrance_fee | 0/5 | 0% |

## geoapify / suzdal_hotels

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "accommodation.hotel,accommodation.hostel,accommodation.guest_house",
  "filter": "circle:40.44978,56.42408,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.accommodation`, `properties.accommodation.stars`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.country`, `properties.country_code`, `properties.county`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw._inherited`, `properties.datasource.raw.barrier`, `properties.datasource.raw.city`, `properties.datasource.raw.contact:website`, `properties.datasource.raw.country`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.postcode`, `properties.datasource.raw.stars`, `properties.datasource.raw.street`, `properties.datasource.raw.tourism`, `properties.datasource.raw.website`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.lat`, `properties.lon`, `properties.municipality`, `properties.name`, `properties.place_id`, `properties.postcode`, `properties.region`, `properties.state`, `properties.street`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_suzdal_hotels.json](../../../data/samples/20261015T150210175612Z/geoapify_suzdal_hotels.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 4/5 | 80% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 2/5 | 40% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 0/5 | 0% |
| opening_hours | 0/5 | 0% |
| entrance_fee | 0/5 | 0% |

## open_meteo / russian_name

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Москва",
  "count": 10,
  "language": "ru",
  "countryCode": "RU"
}
```

Фактические поля: `admin1`, `admin1_id`, `admin2`, `admin2_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_russian_name.json](../../../data/samples/20261015T150210175612Z/open_meteo_russian_name.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 2/2 | 100% |
| name | 2/2 | 100% |
| category | 2/2 | 100% |
| latitude | 2/2 | 100% |
| longitude | 2/2 | 100% |
| address | 0/2 | 0% |
| description | 0/2 | 0% |
| website_url | 0/2 | 0% |
| image_url | 0/2 | 0% |
| rating | 0/2 | 0% |
| price_amount | 0/2 | 0% |
| price_currency | 0/2 | 0% |
| price_period_or_total | 0/2 | 0% |
| availability | 0/2 | 0% |
| country_code | 2/2 | 100% |
| timezone | 2/2 | 100% |
| cuisine | 0/2 | 0% |
| opening_hours | 0/2 | 0% |
| entrance_fee | 0/2 | 0% |

## geonames / russian_name

Evidence: `live_http`; endpoint: `https://secure.geonames.org/searchJSON`.

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

Фактические поля: `adminCode1`, `adminCode2`, `adminCodes1`, `adminCodes1.ISO3166_2`, `adminId1`, `adminId2`, `adminName1`, `adminName2`, `adminName3`, `adminName4`, `adminName5`, `alternateNames`, `alternateNames[].isColloquial`, `alternateNames[].isHistoric`, `alternateNames[].isPreferredName`, `alternateNames[].isShortName`, `alternateNames[].lang`, `alternateNames[].name`, `asciiName`, `astergdem`, `bbox`, `bbox.accuracyLevel`, `bbox.east`, `bbox.north`, `bbox.south`, `bbox.west`, `continentCode`, `countryCode`, `countryId`, `countryName`, `fcl`, `fclName`, `fcode`, `fcodeName`, `geonameId`, `lat`, `lng`, `name`, `population`, `score`, `srtm3`, `timezone`, `timezone.dstOffset`, `timezone.gmtOffset`, `timezone.sunrise`, `timezone.sunset`, `timezone.time`, `timezone.timeZoneId`, `toponymName`.

Пример: [data/samples/20261015T150210175612Z/geonames_russian_name.json](../../../data/samples/20261015T150210175612Z/geonames_russian_name.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 7/7 | 100% |
| name | 7/7 | 100% |
| category | 7/7 | 100% |
| latitude | 7/7 | 100% |
| longitude | 7/7 | 100% |
| address | 0/7 | 0% |
| description | 0/7 | 0% |
| website_url | 0/7 | 0% |
| image_url | 0/7 | 0% |
| rating | 0/7 | 0% |
| price_amount | 0/7 | 0% |
| price_currency | 0/7 | 0% |
| price_period_or_total | 0/7 | 0% |
| availability | 0/7 | 0% |
| country_code | 7/7 | 100% |
| timezone | 7/7 | 100% |
| cuisine | 0/7 | 0% |
| opening_hours | 0/7 | 0% |
| entrance_fee | 0/7 | 0% |

## open_meteo / ambiguous_name

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Springfield",
  "count": 10,
  "language": "en"
}
```

Фактические поля: `admin1`, `admin1_id`, `admin2`, `admin2_id`, `admin3`, `admin3_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `postcodes`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_ambiguous_name.json](../../../data/samples/20261015T150210175612Z/open_meteo_ambiguous_name.json).

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

## open_meteo / country_filter

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "Springfield",
  "count": 10,
  "language": "en",
  "countryCode": "US"
}
```

Фактические поля: `admin1`, `admin1_id`, `admin2`, `admin2_id`, `admin3`, `admin3_id`, `country`, `country_code`, `country_id`, `elevation`, `feature_code`, `id`, `latitude`, `longitude`, `name`, `population`, `postcodes`, `timezone`.

Пример: [data/samples/20261015T150210175612Z/open_meteo_country_filter.json](../../../data/samples/20261015T150210175612Z/open_meteo_country_filter.json).

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

## open_meteo / unknown_city

Evidence: `live_http`; endpoint: `https://geocoding-api.open-meteo.com/v1/search`.

Параметры / фильтры:
```json
{
  "name": "TripFlowNoSuchCity9f71b2",
  "count": 10,
  "language": "en"
}
```

Фактические поля: не измерены.

Пример: [data/samples/20261015T150210175612Z/open_meteo_unknown_city.json](../../../data/samples/20261015T150210175612Z/open_meteo_unknown_city.json).

## geoapify / empty_place_name

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "entertainment.museum",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]",
  "name": "TripFlowNoSuchMuseum9f71b2"
}
```

Фактические поля: не измерены.

Пример: [data/samples/20261015T150210175612Z/geoapify_empty_place_name.json](../../../data/samples/20261015T150210175612Z/geoapify_empty_place_name.json).

## geoapify / vegetarian_restaurants

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/places`.

Параметры / фильтры:
```json
{
  "categories": "catering.restaurant,catering.cafe",
  "filter": "circle:2.3488,48.85341,3000",
  "limit": 5,
  "lang": "en",
  "apiKey": "[REDACTED]",
  "conditions": "vegetarian"
}
```

Фактические поля: `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.catering`, `properties.catering.cuisine`, `properties.catering.diet`, `properties.catering.diet.halal`, `properties.catering.diet.vegan`, `properties.catering.diet.vegetarian`, `properties.city`, `properties.city_block`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.amenity`, `properties.datasource.raw.check_date`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.city`, `properties.datasource.raw.cuisine`, `properties.datasource.raw.diet:halal`, `properties.datasource.raw.diet:vegan`, `properties.datasource.raw.diet:vegetarian`, `properties.datasource.raw.housenumber`, `properties.datasource.raw.indoor_seating`, `properties.datasource.raw.lat`, `properties.datasource.raw.lon`, `properties.datasource.raw.name`, `properties.datasource.raw.name:fr`, `properties.datasource.raw.name:ja`, `properties.datasource.raw.name:ja-Latn`, `properties.datasource.raw.name:zh`, `properties.datasource.raw.opening_hours`, `properties.datasource.raw.opening_hours:signed`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.outdoor_seating`, `properties.datasource.raw.phone`, `properties.datasource.raw.postcode`, `properties.datasource.raw.ref:FR:SIRET`, `properties.datasource.raw.speciality`, `properties.datasource.raw.street`, `properties.datasource.raw.takeaway`, `properties.datasource.raw.website`, `properties.datasource.raw.website:menu`, `properties.datasource.raw.wheelchair`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.details`, `properties.district`, `properties.facilities`, `properties.facilities.outdoor_seating`, `properties.facilities.takeaway`, `properties.facilities.wheelchair`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.name_international`, `properties.name_international.fr`, `properties.name_international.ja`, `properties.name_international.zh`, `properties.opening_hours`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.region`, `properties.state`, `properties.state_COG`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_vegetarian_restaurants.json](../../../data/samples/20261015T150210175612Z/geoapify_vegetarian_restaurants.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 5/5 | 100% |
| name | 5/5 | 100% |
| category | 5/5 | 100% |
| latitude | 5/5 | 100% |
| longitude | 5/5 | 100% |
| address | 5/5 | 100% |
| description | 0/5 | 0% |
| website_url | 2/5 | 40% |
| image_url | 0/5 | 0% |
| rating | 0/5 | 0% |
| price_amount | 0/5 | 0% |
| price_currency | 0/5 | 0% |
| price_period_or_total | 0/5 | 0% |
| availability | 0/5 | 0% |
| country_code | 5/5 | 100% |
| timezone | 0/5 | 0% |
| cuisine | 4/5 | 80% |
| opening_hours | 4/5 | 80% |
| entrance_fee | 0/5 | 0% |

## geoapify / hotels_details

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/place-details`.

Параметры / фильтры:
```json
{
  "id": "5105a3923a011d0340592a94e068226d4840f00103f901880074a50000000092030d43656e7472616c20686f74656c",
  "features": "details",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `bbox`, `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.city`, `properties.city_block`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.check_date`, `properties.datasource.raw.name`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.tourism`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.district`, `properties.feature_type`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.place_id`, `properties.postcode`, `properties.state`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.timezone`, `properties.timezone.abbreviation_DST`, `properties.timezone.abbreviation_STD`, `properties.timezone.name`, `properties.timezone.offset_DST`, `properties.timezone.offset_DST_seconds`, `properties.timezone.offset_STD`, `properties.timezone.offset_STD_seconds`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_hotels_details.json](../../../data/samples/20261015T150210175612Z/geoapify_hotels_details.json).

| Нормализованное поле | Заполнено | Доля |
|---|---|---|
| external_id | 1/1 | 100% |
| name | 1/1 | 100% |
| category | 1/1 | 100% |
| latitude | 1/1 | 100% |
| longitude | 1/1 | 100% |
| address | 1/1 | 100% |
| description | 0/1 | 0% |
| website_url | 0/1 | 0% |
| image_url | 0/1 | 0% |
| rating | 0/1 | 0% |
| price_amount | 0/1 | 0% |
| price_currency | 0/1 | 0% |
| price_period_or_total | 0/1 | 0% |
| availability | 0/1 | 0% |
| country_code | 1/1 | 100% |
| timezone | 1/1 | 100% |
| cuisine | 0/1 | 0% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

## geoapify / restaurants_details

Evidence: `live_http`; endpoint: `https://api.geoapify.com/v2/place-details`.

Параметры / фильтры:
```json
{
  "id": "51a9786d80e30c0340598248d0a9756b4840f00103f9013edb011501000000920309436170204265726379",
  "features": "details",
  "apiKey": "[REDACTED]"
}
```

Фактические поля: `bbox`, `geometry`, `geometry.coordinates`, `geometry.type`, `properties`, `properties.address_line1`, `properties.address_line2`, `properties.categories`, `properties.catering`, `properties.catering.cuisine`, `properties.catering.diet`, `properties.catering.diet.vegetarian`, `properties.city`, `properties.contact`, `properties.contact.phone`, `properties.country`, `properties.country_code`, `properties.datasource`, `properties.datasource.attribution`, `properties.datasource.license`, `properties.datasource.raw`, `properties.datasource.raw.addr:city`, `properties.datasource.raw.addr:housenumber`, `properties.datasource.raw.addr:postcode`, `properties.datasource.raw.addr:street`, `properties.datasource.raw.amenity`, `properties.datasource.raw.check_date`, `properties.datasource.raw.check_date:opening_hours`, `properties.datasource.raw.cuisine`, `properties.datasource.raw.diet:vegetarian`, `properties.datasource.raw.name`, `properties.datasource.raw.opening_hours:signed`, `properties.datasource.raw.osm_id`, `properties.datasource.raw.osm_type`, `properties.datasource.raw.phone`, `properties.datasource.raw.ref:FR:SIRET`, `properties.datasource.raw.takeaway`, `properties.datasource.raw.website`, `properties.datasource.raw.website:menu`, `properties.datasource.sourcename`, `properties.datasource.url`, `properties.district`, `properties.facilities`, `properties.facilities.takeaway`, `properties.feature_type`, `properties.formatted`, `properties.housenumber`, `properties.iso3166_2`, `properties.iso3166_2_sublevel`, `properties.lat`, `properties.lon`, `properties.name`, `properties.place_id`, `properties.postcode`, `properties.quarter`, `properties.state`, `properties.state_code`, `properties.street`, `properties.suburb`, `properties.timezone`, `properties.timezone.abbreviation_DST`, `properties.timezone.abbreviation_STD`, `properties.timezone.name`, `properties.timezone.offset_DST`, `properties.timezone.offset_DST_seconds`, `properties.timezone.offset_STD`, `properties.timezone.offset_STD_seconds`, `properties.website`, `type`.

Пример: [data/samples/20261015T150210175612Z/geoapify_restaurants_details.json](../../../data/samples/20261015T150210175612Z/geoapify_restaurants_details.json).

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
| cuisine | 1/1 | 100% |
| opening_hours | 0/1 | 0% |
| entrance_fee | 0/1 | 0% |

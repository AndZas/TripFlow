# Фактический запуск

Run: `20261015T144430479785Z`. UTC: 2026-10-15T14:44:30.479774+00:00.
Offline: False; без ключей: False.

Результат `ok` подтверждает только этот ответ. `skipped` не означает неисправность API.
Доли заполнения относятся к первым N объектам запроса, не ко всему городу. 0/0 = нет измерения.
Поле address может быть частичным; image_url означает ссылку, не проверенную лицензию изображения.
Категория normalizer — группа запроса; исходные теги/категории находятся в примере JSON.

```json
{
  "scenario": "extended_v2",
  "cities": [
    "paris"
  ],
  "radius_metres": 3000,
  "limit": 5,
  "core_only": false,
  "request_cap": 40,
  "planned_max_requests": 5,
  "details_only": true,
  "coordinates": {
    "paris": {
      "latitude": 48.85341,
      "longitude": 2.3488,
      "source": "open_meteo",
      "id": 2988507
    }
  },
  "no_hotel_offer_queries": true,
  "attempted_requests": 5
}
```

| Провайдер | Запрос | Результат | HTTP | мс | N | Причина |
|---|---|---|---|---|---|---|
| open_meteo | paris_city | ok | 200 | 498.9 | 10 |  |
| geoapify | paris_hotels | ok | 200 | 639.4 | 5 |  |
| geoapify | paris_restaurants | ok | 200 | 646.7 | 5 |  |
| geoapify | hotels_details | ok | 200 | 1249.1 | 1 |  |
| geoapify | restaurants_details | ok | 200 | 858.2 | 1 |  |

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

Пример: [data/samples/20261015T144430479785Z/open_meteo_paris_city.json](../../../data/samples/20261015T144430479785Z/open_meteo_paris_city.json).

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

Пример: [data/samples/20261015T144430479785Z/geoapify_paris_hotels.json](../../../data/samples/20261015T144430479785Z/geoapify_paris_hotels.json).

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

Пример: [data/samples/20261015T144430479785Z/geoapify_paris_restaurants.json](../../../data/samples/20261015T144430479785Z/geoapify_paris_restaurants.json).

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

Пример: [data/samples/20261015T144430479785Z/geoapify_hotels_details.json](../../../data/samples/20261015T144430479785Z/geoapify_hotels_details.json).

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

Пример: [data/samples/20261015T144430479785Z/geoapify_restaurants_details.json](../../../data/samples/20261015T144430479785Z/geoapify_restaurants_details.json).

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

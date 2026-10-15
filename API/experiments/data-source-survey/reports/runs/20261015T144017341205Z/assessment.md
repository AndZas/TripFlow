# Расширенная проверка источников

Run `20261015T144017341205Z`. UTC 2026-10-15T14:40:17.341198+00:00.
Проверки: pass=188, warn=4, fail=2, skipped=0.
Сетевых попыток: 40; предел 40. Все последовательно.

[Полные запросы и поля](live-results.md) · [JSON результатов](results.json) · [Проверки JSON](checks.json)

HTTP 200 проверяется отдельно от полноты данных. warn = ограничение/нужна проверка, fail = ожидание не выполнено.
Пустая корректная выдача не ошибка транспорта. Повторных запросов для замены отклонённых объектов нет.

## Заполненность POI

Доли по всем объектам запроса. Сохранены только 2 примера на endpoint.

| Запрос | N | Название | Адрес | Сайт | Фото | Описание | Кухня | Часы | Цена | Наличие |
|---|---:|---|---|---|---|---|---|---|---|---|
| paris_museums | 5 | 5/5 | 5/5 | 4/5 | 1/5 | 0/5 | 0/5 | 4/5 | 0/5 | 0/5 |
| paris_historic | 5 | 5/5 | 5/5 | 1/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| paris_nature | 5 | 5/5 | 5/5 | 1/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| paris_restaurants | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 3/5 | 1/5 | 0/5 | 0/5 |
| paris_hotels | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| moscow_museums | 5 | 5/5 | 5/5 | 3/5 | 0/5 | 0/5 | 0/5 | 2/5 | 0/5 | 0/5 |
| moscow_historic | 5 | 5/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| moscow_nature | 5 | 4/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| moscow_restaurants | 5 | 5/5 | 5/5 | 3/5 | 0/5 | 0/5 | 3/5 | 2/5 | 0/5 | 0/5 |
| moscow_hotels | 5 | 5/5 | 5/5 | 1/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| istanbul_museums | 5 | 5/5 | 5/5 | 3/5 | 1/5 | 2/5 | 0/5 | 2/5 | 0/5 | 0/5 |
| istanbul_historic | 5 | 5/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| istanbul_nature | 5 | 2/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| istanbul_restaurants | 5 | 5/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| istanbul_hotels | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 0/5 | 1/5 | 0/5 | 0/5 |
| suzdal_museums | 5 | 5/5 | 5/5 | 1/5 | 0/5 | 0/5 | 0/5 | 1/5 | 0/5 | 0/5 |
| suzdal_historic | 5 | 5/5 | 5/5 | 0/5 | 0/5 | 1/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| suzdal_nature | 5 | 1/5 | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| suzdal_restaurants | 5 | 5/5 | 5/5 | 2/5 | 1/5 | 0/5 | 3/5 | 1/5 | 0/5 | 0/5 |
| suzdal_hotels | 5 | 4/5 | 5/5 | 2/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| empty_place_name | 0 | не измерено | не измерено | не измерено | не измерено | не измерено | не измерено | не измерено | не измерено | не измерено |
| vegetarian_restaurants | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 4/5 | 4/5 | 0/5 | 0/5 |
| hotels_details | 1 | 1/1 | 1/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| restaurants_details | 1 | 1/1 | 1/1 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 0/1 | 0/1 |

## Проверки

| Проверка | Результат | Подробности | Тип доказательства |
|---|---|---|---|
| open_meteo/paris_city/response | pass | HTTP 200; objects=10 | open_meteo/paris_city |
| geonames/paris_city/response | pass | HTTP 200; objects=2 | geonames/paris_city |
| paris/open_meteo/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| paris/geonames/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| paris/iana | warn | timezone=Europe/Paris; local IANA database not installed | live_http+local_zoneinfo |
| paris/provider_agreement | pass | Compare shared GeoNames ID; these geocoders are not independent datasets | live_http |
| geonames/FR_country/response | pass | HTTP 200; objects=1 | geonames/FR_country |
| FR/currency | pass | Fixture expectation FR/EUR; reference currency, not hotel offer currency | live_http |
| geoapify/paris_museums/response | pass | HTTP 200; objects=5 | geoapify/paris_museums |
| paris_museums/limit | pass | N=5, limit=5 | live_http |
| paris_museums/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_museums/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_museums/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_museums/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_museums/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/paris_historic/response | pass | HTTP 200; objects=5 | geoapify/paris_historic |
| paris_historic/limit | pass | N=5, limit=5 | live_http |
| paris_historic/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_historic/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_historic/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_historic/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_historic/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/paris_nature/response | pass | HTTP 200; objects=5 | geoapify/paris_nature |
| paris_nature/limit | pass | N=5, limit=5 | live_http |
| paris_nature/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_nature/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_nature/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_nature/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_nature/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/paris_restaurants/response | pass | HTTP 200; objects=5 | geoapify/paris_restaurants |
| paris_restaurants/limit | pass | N=5, limit=5 | live_http |
| paris_restaurants/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_restaurants/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_restaurants/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_restaurants/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_restaurants/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/paris_hotels/response | pass | HTTP 200; objects=5 | geoapify/paris_hotels |
| paris_hotels/limit | pass | N=5, limit=5 | live_http |
| paris_hotels/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_hotels/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_hotels/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_hotels/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_hotels/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| open_meteo/moscow_city/response | pass | HTTP 200; objects=5 | open_meteo/moscow_city |
| geonames/moscow_city/response | pass | HTTP 200; objects=1 | geonames/moscow_city |
| moscow/open_meteo/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| moscow/geonames/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| moscow/iana | warn | timezone=Europe/Moscow; local IANA database not installed | live_http+local_zoneinfo |
| moscow/provider_agreement | pass | Compare shared GeoNames ID; these geocoders are not independent datasets | live_http |
| geonames/RU_country/response | pass | HTTP 200; objects=1 | geonames/RU_country |
| RU/currency | pass | Fixture expectation RU/RUB; reference currency, not hotel offer currency | live_http |
| geoapify/moscow_museums/response | pass | HTTP 200; objects=5 | geoapify/moscow_museums |
| moscow_museums/limit | pass | N=5, limit=5 | live_http |
| moscow_museums/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| moscow_museums/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| moscow_museums/country | pass | Expected country RU; missing metadata requires review | live_http |
| moscow_museums/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| moscow_museums/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/moscow_historic/response | pass | HTTP 200; objects=5 | geoapify/moscow_historic |
| moscow_historic/limit | pass | N=5, limit=5 | live_http |
| moscow_historic/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| moscow_historic/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| moscow_historic/country | pass | Expected country RU; missing metadata requires review | live_http |
| moscow_historic/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| moscow_historic/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/moscow_nature/response | pass | HTTP 200; objects=5 | geoapify/moscow_nature |
| moscow_nature/limit | pass | N=5, limit=5 | live_http |
| moscow_nature/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| moscow_nature/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| moscow_nature/country | pass | Expected country RU; missing metadata requires review | live_http |
| moscow_nature/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| moscow_nature/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/moscow_restaurants/response | pass | HTTP 200; objects=5 | geoapify/moscow_restaurants |
| moscow_restaurants/limit | pass | N=5, limit=5 | live_http |
| moscow_restaurants/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| moscow_restaurants/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| moscow_restaurants/country | pass | Expected country RU; missing metadata requires review | live_http |
| moscow_restaurants/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| moscow_restaurants/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/moscow_hotels/response | pass | HTTP 200; objects=5 | geoapify/moscow_hotels |
| moscow_hotels/limit | pass | N=5, limit=5 | live_http |
| moscow_hotels/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| moscow_hotels/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| moscow_hotels/country | pass | Expected country RU; missing metadata requires review | live_http |
| moscow_hotels/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| moscow_hotels/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| open_meteo/istanbul_city/response | pass | HTTP 200; objects=5 | open_meteo/istanbul_city |
| geonames/istanbul_city/response | pass | HTTP 200; objects=1 | geonames/istanbul_city |
| istanbul/open_meteo/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| istanbul/geonames/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| istanbul/iana | warn | timezone=Europe/Istanbul; local IANA database not installed | live_http+local_zoneinfo |
| istanbul/provider_agreement | pass | Compare shared GeoNames ID; these geocoders are not independent datasets | live_http |
| geonames/TR_country/response | pass | HTTP 200; objects=1 | geonames/TR_country |
| TR/currency | pass | Fixture expectation TR/TRY; reference currency, not hotel offer currency | live_http |
| geoapify/istanbul_museums/response | pass | HTTP 200; objects=5 | geoapify/istanbul_museums |
| istanbul_museums/limit | pass | N=5, limit=5 | live_http |
| istanbul_museums/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| istanbul_museums/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| istanbul_museums/country | pass | Expected country TR; missing metadata requires review | live_http |
| istanbul_museums/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| istanbul_museums/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/istanbul_historic/response | pass | HTTP 200; objects=5 | geoapify/istanbul_historic |
| istanbul_historic/limit | pass | N=5, limit=5 | live_http |
| istanbul_historic/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| istanbul_historic/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| istanbul_historic/country | pass | Expected country TR; missing metadata requires review | live_http |
| istanbul_historic/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| istanbul_historic/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/istanbul_nature/response | pass | HTTP 200; objects=5 | geoapify/istanbul_nature |
| istanbul_nature/limit | pass | N=5, limit=5 | live_http |
| istanbul_nature/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| istanbul_nature/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| istanbul_nature/country | pass | Expected country TR; missing metadata requires review | live_http |
| istanbul_nature/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| istanbul_nature/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/istanbul_restaurants/response | pass | HTTP 200; objects=5 | geoapify/istanbul_restaurants |
| istanbul_restaurants/limit | pass | N=5, limit=5 | live_http |
| istanbul_restaurants/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| istanbul_restaurants/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| istanbul_restaurants/country | pass | Expected country TR; missing metadata requires review | live_http |
| istanbul_restaurants/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| istanbul_restaurants/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/istanbul_hotels/response | pass | HTTP 200; objects=5 | geoapify/istanbul_hotels |
| istanbul_hotels/limit | pass | N=5, limit=5 | live_http |
| istanbul_hotels/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| istanbul_hotels/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| istanbul_hotels/country | pass | Expected country TR; missing metadata requires review | live_http |
| istanbul_hotels/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| istanbul_hotels/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| open_meteo/suzdal_city/response | pass | HTTP 200; objects=10 | open_meteo/suzdal_city |
| geonames/suzdal_city/response | pass | HTTP 200; objects=1 | geonames/suzdal_city |
| suzdal/open_meteo/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| suzdal/geonames/unambiguous | pass | Exactly one named populated-place candidate expected; no first-result fallback | live_http |
| suzdal/iana | warn | timezone=Europe/Moscow; local IANA database not installed | live_http+local_zoneinfo |
| suzdal/provider_agreement | pass | Compare shared GeoNames ID; these geocoders are not independent datasets | live_http |
| geoapify/suzdal_museums/response | pass | HTTP 200; objects=5 | geoapify/suzdal_museums |
| suzdal_museums/limit | pass | N=5, limit=5 | live_http |
| suzdal_museums/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| suzdal_museums/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| suzdal_museums/country | pass | Expected country RU; missing metadata requires review | live_http |
| suzdal_museums/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| suzdal_museums/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/suzdal_historic/response | pass | HTTP 200; objects=5 | geoapify/suzdal_historic |
| suzdal_historic/limit | pass | N=5, limit=5 | live_http |
| suzdal_historic/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| suzdal_historic/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| suzdal_historic/country | pass | Expected country RU; missing metadata requires review | live_http |
| suzdal_historic/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| suzdal_historic/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/suzdal_nature/response | pass | HTTP 200; objects=5 | geoapify/suzdal_nature |
| suzdal_nature/limit | pass | N=5, limit=5 | live_http |
| suzdal_nature/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| suzdal_nature/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| suzdal_nature/country | pass | Expected country RU; missing metadata requires review | live_http |
| suzdal_nature/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| suzdal_nature/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/suzdal_restaurants/response | pass | HTTP 200; objects=5 | geoapify/suzdal_restaurants |
| suzdal_restaurants/limit | pass | N=5, limit=5 | live_http |
| suzdal_restaurants/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| suzdal_restaurants/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| suzdal_restaurants/country | pass | Expected country RU; missing metadata requires review | live_http |
| suzdal_restaurants/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| suzdal_restaurants/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/suzdal_hotels/response | pass | HTTP 200; objects=5 | geoapify/suzdal_hotels |
| suzdal_hotels/limit | pass | N=5, limit=5 | live_http |
| suzdal_hotels/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| suzdal_hotels/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| suzdal_hotels/country | pass | Expected country RU; missing metadata requires review | live_http |
| suzdal_hotels/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| suzdal_hotels/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| open_meteo/russian_name/response | pass | HTTP 200; objects=2 | open_meteo/russian_name |
| open_meteo/cyrillic | pass | Cyrillic query resolves the expected populated place | live_http |
| geonames/russian_name/response | pass | HTTP 200; objects=7 | geonames/russian_name |
| geonames/cyrillic | pass | Cyrillic query resolves the expected populated place | live_http |
| open_meteo/ambiguous_name/response | pass | HTTP 200; objects=10 | open_meteo/ambiguous_name |
| city/ambiguity | pass | 10 candidates: product should request a selection, not assume first result | live_http |
| open_meteo/country_filter/response | pass | HTTP 200; objects=10 | open_meteo/country_filter |
| city/country_filter | pass | Explicit US filter; returned IDs remain candidates | live_http |
| open_meteo/unknown_city/response | pass | HTTP 200; objects=0 | open_meteo/unknown_city |
| city/empty | pass | Deliberately unknown query; inspect any unexpected real matches | live_http |
| geoapify/empty_place_name/response | pass | HTTP 200; objects=0 | geoapify/empty_place_name |
| empty_place_name/limit | pass | N=0, limit=5 | live_http |
| empty_place_name/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| poi/empty | pass | Unknown name with valid category and coordinates | live_http |
| geoapify/vegetarian_restaurants/response | pass | HTTP 200; objects=5 | geoapify/vegetarian_restaurants |
| vegetarian_restaurants/limit | pass | N=5, limit=5 | live_http |
| vegetarian_restaurants/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| vegetarian_restaurants/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| vegetarian_restaurants/country | pass | Expected country FR; missing metadata requires review | live_http |
| poi/condition | pass | Validate vegetarian metadata when exposed; acceptance of filter alone proves less | live_http |
| geoapify/hotels_details/response | pass | HTTP 200; objects=1 | geoapify/hotels_details |
| hotels/detail_identity | fail | Details must identify the same provider object | live_http |
| geoapify/restaurants_details/response | pass | HTTP 200; objects=1 | geoapify/restaurants_details |
| restaurants/detail_identity | fail | Details must identify the same provider object | live_http |

## Пределы

Это небольшие выборки в радиусе, не полный список городских объектов. Категории — фильтры поставщика; качество описаний/фото не гарантируется.
Отсутствие prices/availability не исправляется успешным HTTP. CountryInfo currency — валюта страны, не цена отеля.
Геокодеры Open-Meteo и GeoNames используют общую основу; совпадение не независимая проверка географии.
Отклонения/dedup проверены локально на живой выборке. Кэш/TTL/публикация карточки/повторный подбор production-приложения здесь не реализованы.
Время ответа — наблюдение этого запуска; повторов для статистики задержек не было. Overpass, партнёрские и визовые API не вызываются.

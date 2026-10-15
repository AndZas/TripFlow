# Расширенная проверка источников

Run `20261015T144430479785Z`. UTC 2026-10-15T14:44:30.479774+00:00.
Проверки: pass=19, warn=2, fail=0, skipped=0.
Сетевых попыток: 5; предел 40. Все последовательно.

[Полные запросы и поля](live-results.md) · [JSON результатов](results.json) · [Проверки JSON](checks.json)

HTTP 200 проверяется отдельно от полноты данных. warn = ограничение/нужна проверка, fail = ожидание не выполнено.
Пустая корректная выдача не ошибка транспорта. Повторных запросов для замены отклонённых объектов нет.

## Заполненность POI

Доли по всем объектам запроса. Сохранены только 2 примера на endpoint.

| Запрос | N | Название | Адрес | Сайт | Фото | Описание | Кухня | Часы | Цена | Наличие |
|---|---:|---|---|---|---|---|---|---|---|---|
| paris_hotels | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| paris_restaurants | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 3/5 | 1/5 | 0/5 | 0/5 |
| hotels_details | 1 | 1/1 | 1/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| restaurants_details | 1 | 1/1 | 1/1 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 0/1 | 0/1 |

## Проверки

| Проверка | Результат | Подробности | Тип доказательства |
|---|---|---|---|
| open_meteo/paris_city/response | pass | HTTP 200; objects=10 | open_meteo/paris_city |
| geoapify/paris_hotels/response | pass | HTTP 200; objects=5 | geoapify/paris_hotels |
| paris_hotels/limit | pass | N=5, limit=5 | live_http |
| paris_hotels/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_hotels/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_hotels/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_hotels/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_hotels/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/paris_restaurants/response | pass | HTTP 200; objects=5 | geoapify/paris_restaurants |
| paris_restaurants/limit | pass | N=5, limit=5 | live_http |
| paris_restaurants/categories | pass | All returned categories match a requested prefix; empty set is checked separately | live_http |
| paris_restaurants/identity_coordinates | pass | Provider IDs are present/unique and WGS84 coordinates valid | live_http |
| paris_restaurants/country | pass | Expected country FR; missing metadata requires review | live_http |
| paris_restaurants/card_scope | pass | Reject first live ID in card A; card B retains it; no extra provider call | local_on_live_candidates |
| paris_restaurants/all_rejected | pass | Empty list when all sampled candidates rejected; no infinite refill/retry | local_on_live_candidates |
| geoapify/hotels_details/response | pass | HTTP 200; objects=1 | geoapify/hotels_details |
| hotels/detail_identity | pass | Same source object node/2775842952 | live_http |
| hotels/lookup_id_changed | warn | Opaque place_id changed; retain source OSM type/id and lookup ID aliases | live_http |
| geoapify/restaurants_details/response | pass | HTTP 200; objects=1 | geoapify/restaurants_details |
| restaurants/detail_identity | pass | Same source object node/4647410494 | live_http |
| restaurants/lookup_id_changed | warn | Opaque place_id changed; retain source OSM type/id and lookup ID aliases | live_http |

## Пределы

Это небольшие выборки в радиусе, не полный список городских объектов. Категории — фильтры поставщика; качество описаний/фото не гарантируется.
Отсутствие prices/availability не исправляется успешным HTTP. CountryInfo currency — валюта страны, не цена отеля.
Геокодеры Open-Meteo и GeoNames используют общую основу; совпадение не независимая проверка географии.
Отклонения/dedup проверены локально на живой выборке. Кэш/TTL/публикация карточки/повторный подбор production-приложения здесь не реализованы.
Время ответа — наблюдение этого запуска; повторов для статистики задержек не было. Overpass, партнёрские и визовые API не вызываются.

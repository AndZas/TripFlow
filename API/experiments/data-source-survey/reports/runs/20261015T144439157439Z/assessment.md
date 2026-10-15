# Расширенная проверка источников

Run `20261015T144439157439Z`. UTC 2026-10-15T14:44:39.157431+00:00.
Проверки: pass=0, warn=0, fail=0, skipped=60.
Сетевых попыток: 0; предел 40. Все последовательно.

[Полные запросы и поля](live-results.md) · [JSON результатов](results.json) · [Проверки JSON](checks.json)

HTTP 200 проверяется отдельно от полноты данных. warn = ограничение/нужна проверка, fail = ожидание не выполнено.
Пустая корректная выдача не ошибка транспорта. Повторных запросов для замены отклонённых объектов нет.

## Заполненность POI

Доли по всем объектам запроса. Сохранены только 2 примера на endpoint.

| Запрос | N | Название | Адрес | Сайт | Фото | Описание | Кухня | Часы | Цена | Наличие |
|---|---:|---|---|---|---|---|---|---|---|---|

## Проверки

| Проверка | Результат | Подробности | Тип доказательства |
|---|---|---|---|
| open_meteo/paris_city/response | skipped | Offline or not selected | not_called |
| geonames/paris_city/response | skipped | Offline or not selected | not_called |
| geonames/FR_country/response | skipped | Offline or not selected | not_called |
| geoapify/paris_museums/response | skipped | Offline or not selected | not_called |
| paris_museums/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/paris_historic/response | skipped | Offline or not selected | not_called |
| paris_historic/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/paris_nature/response | skipped | Offline or not selected | not_called |
| paris_nature/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/paris_restaurants/response | skipped | Offline or not selected | not_called |
| paris_restaurants/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/paris_hotels/response | skipped | Offline or not selected | not_called |
| paris_hotels/rejections | skipped | No live candidates for local rejection check | not_measured |
| open_meteo/moscow_city/response | skipped | Offline or not selected | not_called |
| geonames/moscow_city/response | skipped | Offline or not selected | not_called |
| geonames/RU_country/response | skipped | Offline or not selected | not_called |
| geoapify/moscow_museums/response | skipped | Offline or not selected | not_called |
| moscow_museums/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/moscow_historic/response | skipped | Offline or not selected | not_called |
| moscow_historic/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/moscow_nature/response | skipped | Offline or not selected | not_called |
| moscow_nature/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/moscow_restaurants/response | skipped | Offline or not selected | not_called |
| moscow_restaurants/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/moscow_hotels/response | skipped | Offline or not selected | not_called |
| moscow_hotels/rejections | skipped | No live candidates for local rejection check | not_measured |
| open_meteo/istanbul_city/response | skipped | Offline or not selected | not_called |
| geonames/istanbul_city/response | skipped | Offline or not selected | not_called |
| geonames/TR_country/response | skipped | Offline or not selected | not_called |
| geoapify/istanbul_museums/response | skipped | Offline or not selected | not_called |
| istanbul_museums/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/istanbul_historic/response | skipped | Offline or not selected | not_called |
| istanbul_historic/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/istanbul_nature/response | skipped | Offline or not selected | not_called |
| istanbul_nature/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/istanbul_restaurants/response | skipped | Offline or not selected | not_called |
| istanbul_restaurants/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/istanbul_hotels/response | skipped | Offline or not selected | not_called |
| istanbul_hotels/rejections | skipped | No live candidates for local rejection check | not_measured |
| open_meteo/suzdal_city/response | skipped | Offline or not selected | not_called |
| geonames/suzdal_city/response | skipped | Offline or not selected | not_called |
| geoapify/suzdal_museums/response | skipped | Offline or not selected | not_called |
| suzdal_museums/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/suzdal_historic/response | skipped | Offline or not selected | not_called |
| suzdal_historic/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/suzdal_nature/response | skipped | Offline or not selected | not_called |
| suzdal_nature/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/suzdal_restaurants/response | skipped | Offline or not selected | not_called |
| suzdal_restaurants/rejections | skipped | No live candidates for local rejection check | not_measured |
| geoapify/suzdal_hotels/response | skipped | Offline or not selected | not_called |
| suzdal_hotels/rejections | skipped | No live candidates for local rejection check | not_measured |
| open_meteo/russian_name/response | skipped | Offline or not selected | not_called |
| geonames/russian_name/response | skipped | Offline or not selected | not_called |
| open_meteo/ambiguous_name/response | skipped | Offline or not selected | not_called |
| open_meteo/country_filter/response | skipped | Offline or not selected | not_called |
| open_meteo/unknown_city/response | skipped | Offline or not selected | not_called |
| geoapify/empty_place_name/response | skipped | Offline or not selected | not_called |
| geoapify/vegetarian_restaurants/response | skipped | Offline or not selected | not_called |
| geoapify/hotels_details/response | skipped | Offline or not selected | not_called |
| geoapify/restaurants_details/response | skipped | Offline or not selected | not_called |

## Пределы

Это небольшие выборки в радиусе, не полный список городских объектов. Категории — фильтры поставщика; качество описаний/фото не гарантируется.
Отсутствие prices/availability не исправляется успешным HTTP. CountryInfo currency — валюта страны, не цена отеля.
Геокодеры Open-Meteo и GeoNames используют общую основу; совпадение не независимая проверка географии.
Отклонения/dedup проверены локально на живой выборке. Кэш/TTL/публикация карточки/повторный подбор production-приложения здесь не реализованы.
Время ответа — наблюдение этого запуска; повторов для статистики задержек не было. Overpass, партнёрские и визовые API не вызываются.

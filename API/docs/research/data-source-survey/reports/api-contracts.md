# Параметры, схемы и границы интеграций

Проверка документации: **15.10.2026**. **L** означает выполненный запрос; **D** — документированный или предварительный контракт, не доказанный живым ответом. Здесь нет скриптов бронирования и нет действительных секретов. Ссылки и условия каждого поставщика — в [sources.md](sources.md); измерения — в [comparison.md](comparison.md).

## Реализованные бесплатные запросы

| Endpoint | Вход / фильтрация | Ответ и интерпретация |
|---|---|---|
| **L** `GET geocoding-api.open-meteo.com/v1/search` | `name=Paris`, `countryCode=FR`, `language=en`, `count=10`. Сначала фильтр страны, затем выбор `feature_code=PPLC`, `name=Paris` | `results[]`: `id`, `name`, `latitude`, `longitude`, `country_code`, `country`, `timezone`, `feature_code`, admin/population. EUR не возвращался. Пропущенные поля у других городов допустимы |
| **L** `GET overpass-api.de/api/interpreter` | Параметр `data` содержит Overpass QL, WGS84. Серверный `timeout=15`, `out center 10`. Радиус указан в отчёте каждой попытки | `elements[]`: `type`, `id`, `lat/lon` для node или `center` для way/relation, `tags`. `osm3s.timestamp_osm_base` — свежесть реплики. `remark` даже при HTTP 200 считается ошибкой/неполной выдачей |
| **D** `GET api.geoapify.com/v2/places` | `apiKey`, `categories`, `filter=circle:lon,lat,radius`, `limit=10`, `lang=en`. API также поддерживает name, conditions, bias и offset; эти дополнительные фильтры описаны, но не измерены | GeoJSON `features[].properties`: name/place_id/адрес/координаты/categories, дополнительные свойства по данным. Наличие свойства не гарантировано |
| **D** `GET api.geoapify.com/v2/place-details` | Возвращённый `id`, `features=details`, ключ; не более двух объектов, без isolines/дополнительных features | GeoJSON; description, opening_hours, website, wiki_and_media, timezone и прочее по документации. Объект с `feature_type=details` не равен всем произвольным geometry features |
| **D, требует проверки схемы** `GET api.opentripmap.com/0.1/en/places/radius` | Подготовлены `lat`, `lon`, `radius`, `kinds`, `limit=10`, `format=json`, `apikey`; затем не более двух `/places/xid/{xid}` | Ожидаются `xid`, name, kinds, point, rate; details — address, wikipedia_extracts, preview, ссылки. Ключа не было, интерактивный Swagger недоступен в исследовании. Адаптер предварительный: перед применением сверить текущую схему и category keys. `rate` — не поле rating отзывов |
| **D** `GET secure.geonames.org/searchJSON` | `name_equals=Paris`, `country=FR`, `featureCode=PPLC`, `maxRows=10`, `style=FULL`, собственный username | `geonames[]`; идентификатор, имя, страна, lat/lng и дополнительные поля. Числа могут быть строками. Нельзя предполагать те же имена полей, что у Open-Meteo |
| **D** `GET secure.geonames.org/countryInfoJSON` | `country=FR`, username | Справочные поля страны, в том числе валюта по контракту. Это валюта страны, не валюта гостиничного оффера |
| **D** `GET secure.geonames.org/timezoneJSON` | `lat`, `lng`, username | Идентификатор IANA и offsets; ошибка может приходить JSON `status` при HTTP 200 |
| **L** `GET api.frankfurter.dev/v2/rate/EUR/RUB` | В данном тесте только пара в пути, без query. Документированы date и providers | `date`, `base`, `quote`, `rate`. Для денег в приложении использовать Decimal/оговорённое округление; этот эксперимент сумму бюджета не считает |
| **E** `GET api.frankfurter.dev/v1/latest` | `base=EUR`, `symbols=RUB` | HTTP 404; не подставлять старый или фиксированный курс. Не делать автоматический EUR→USD→RUB без согласованной политики и дат |
| **E** SIX `list-one.xml` | Публикуемый XML List One; после разбора отбор `CtryNm=FRANCE` | Планировались CcyNm/Ccy/CcyNbr/CcyMnrUnts; в запуске TLS-ошибка, полученных записей нет |
| **L** CLDR `currencyData.json` из официального репозитория Unicode | Из `supplemental.currencyData.region.FR` выбираются записи, действующие на дату запуска и не `_tender=false` | `currency_code=EUR`, `_from=1999-01-01`, version. Файл загружается один раз за запуск; сохраняется маленькая выборка, не полная база. Записан SHA-256 ответа; main изменяема, production должен закреплять версию |

### Категории POI и жилья

Это прикладные группы запроса, не общий классификатор для всех поставщиков. Типы объекта сохраняются в исходных полях.

| Группа | Фильтр OSM в эксперименте | Geoapify по документации | OpenTripMap, предварительно |
|---|---|---|---|
| Музеи | `tourism=museum` | `entertainment.museum` | `museums` |
| История/культура | наличие `historic` | `tourism.sights` | `historic,cultural` |
| Природа/парки/вид | объединение `leisure=park`, `tourism=viewpoint`, `natural=wood` | `leisure.park,natural,tourism.attraction.viewpoint` | `natural,gardens_and_parks` |
| Рестораны/кафе | `amenity` regex `^(restaurant\|cafe)$` | `catering.restaurant,catering.cafe` | `restaurants,cafes` |
| Жильё | `tourism` regex `^(hotel\|hostel\|guest_house)$` | `accommodation.hotel,accommodation.hostel,accommodation.guest_house` | Не добавлено в этот адаптер |

Пример **реальной формы** запроса музеев A (конкретные возвращённые объекты — в samples):

```text
[out:json][timeout:15];
(nwr(around:3000,48.85341,2.3488)["tourism"="museum"];);
out center 10;
```

Отбор по `historic` шире туристических хитов и даёт объекты без имени. Категории разных API не совпадают точно, поэтому сравнение количества без выравнивания классификаторов не измеряет превосходство покрытия. Для budget/price-фильтра в POI каталогах нет универсального эквивалента.

## Кандидаты, не вызываемые скриптом

| Поставщик | Вход / API | Возможные поля и ограничения |
|---|---|---|
| Foursquare | Новый `/places/search`: query, ll/radius либо near либо ne/sw; категории, limit, fields; `X-Places-Api-Version` по reference | fsq_place_id, имя, координаты, location, categories; website/hours/photos/price/rating зависят от доступа. `price` 1–4 — уровень расходов, не сумма билета. Старый V3 не брать за основу |
| Google Places New | POST `/v1/places:searchNearby`: includedTypes/excludedTypes, locationRestriction.circle, maxResultCount, languageCode/rankPreference; key + FieldMask | `places.id`, `displayName`, location, formattedAddress; rating/websiteUri повышают SKU. photos — ссылки/имена ресурсов, изображение получает отдельный endpoint. Нет тарифа гостиничного номера на даты |
| Tripadvisor Terra | locations search/nearby/details, reviews/photos; набор параметров/полей зависит от endpoint и пакета | Контент и отзывы, usage per entity. Это не готовый hotel-shopping. У старого Content API нельзя предполагать дальнейшую работу; новый контракт не внедрён |
| Yelp | `/v3/businesses/search`: term, categories, location либо latitude/longitude, radius, price, open_now, limit, locale | business ID, name, categories, coordinates, location, rating/review_count, image_url; поля зависят от плана. `price` — ценовая категория, URL Yelp не обязательно официальный сайт ресторана |
| Amadeus | **Исторически** Hotel List `/v1/reference-data/locations/hotels/by-city?cityCode=PAR`, далее Hotel Search `/v3/shopping/hotel-offers` с hotelIds, checkInDate, checkOutDate, adults, roomQuantity, currency и фильтрами | List: hotelId/name/geoCode; Search: available/offers, room, guests, price.total/currency/taxes/policies по версии. **Self-Service закрыт**, это пояснение разделения каталог/офферы, не инструкция получать ключ или рабочий контракт Enterprise. Конкретные Enterprise параметры согласовать с поставщиком |
| Booking Demand 3.3 | POST `/accommodations/search`, `/accommodations/availability`, `/accommodations/details`; token + X-Affiliate-Id. Даты checkin/checkout, guests.number_of_adults/number_of_rooms, booker.country/platform, city или другие spatial filters, currency/extras по endpoint | Каталог отдельно; тарифы и продукты отдельно. Guest count, стоимость за весь stay, включённые/исключённые налоги, chargeable/booker currency и политики читать из текущей схемы. Не выдумывать booker.country по городу назначения |
| Expedia Rapid | Content `/v3/properties/content`, Shopping `/v3/properties/availability` на разрешённом test/prod домене; checkin/checkout, occupancy, property_id, currency, language, country_code и другие обязательные поля текущей схемы | Несколько тарифов/bed groups и способы оплаты, totals и налоговые компоненты. Occupancy не равно room count одним числом: состав передаётся по комнатам. Content без Shopping не доказывает наличие. Auth — API key + timestamp/SHA-512 signature из shared secret |

Даты и число гостей в живые гостиничные офферы **не передавались**. В будущей проверке hotel ID нужно получить из того же поставщика; OSM ID не является Booking/Amadeus/Expedia ID. Никакого автоматического бронирования для получения цены не требуется и в эксперименте не предусмотрено.

## Визы и документы

Ниже описаны **схемы**, а не правила для гражданства пользователя. Никакого выбранного паспорта или результата о разрешённом въезде в данных эксперимента нет.

| Источник | Что передавать | Что получать | Пробелы / доступ |
|---|---|---|---|
| Sherpa | POST `https://requirements-api.sandbox.joinsherpa.com/v3/trips`, x-api-key, Content-Type application/vnd.api+json. data.type=TRIP, attributes.traveller.passports (ISO alpha-3), locale, travelNodes ORIGIN/DESTINATION/TRANSIT, arrival/departure dates, route; `include=restriction,procedure` | informationGroups и included PROCEDURE/RESTRICTION: visa/ETA, паспортные/документальные/иные требования, описание, обязательность, sources/actions. Наличие продукта с ценой не равно правительственному сбору без комиссии | Рассмотренная публичная схема содержит паспорта и маршрут; residency, тип паспорта, purpose, имеющиеся визы/ВНЖ нельзя добавлять выдуманными полями. Уточнить расширенный контракт. Sandbox доступен по документации, а не проверен HTTP-запросом; бесплатность не установлена |
| Visafar | GET `/api/v1/evaluate`: passport (ISO alpha-3), held (document codes), residence, date; Bearer/X-Api-Key. В рассмотренной схеме результат охватывает набор направлений, а не обязательный destination query | destinations с entry/status/maxStayDays/conditions/source/lastChecked; data freshness/basis и attribution | Нет подтверждённых параметров типа паспорта, детальной цели поездки и транзитного маршрута в этом контракте. Ключ вручную, тариф API уточнить. Пример на сайте — пример поставщика, не результат нашего запроса |
| Государственный сайт | Профиль вводит сам путешественник: гражданство/тип документа, резидентство, цель/длительность/даты, имеющиеся разрешения и транзит по конкретному помощнику | Официальная информация о необходимости визы/документах и порядке обращения | Формы не отправлялись, пользовательский профиль не подбирался, HTML не парсился. Общий JSON API не подтверждён |

Для будущего приложения надо отдельно определить обязательность каждого поля профиля. Тип паспорта, разрешённая цель/срок, наличие нескольких гражданств, условия действительности визы/ВНЖ и airside/landside транзит могут менять результат. Нельзя считать поддержку поля доказанной только потому, что оно важно предметной области. Результат должен содержать дату проверки и ссылку на официальный источник; экспериментальный ответ не является официальной консультацией.

## Нормализация и измерения

Дополнение второго этапа: GeoNames теперь также нормализуется (`currency_code` отдельно от `price_currency`). Для Geoapify сохраняются `source_provider/source_external_id` из OSM type/id; при наличии этой пары она используется для устойчивого локального исключения кандидата, поскольку lookup ID Search/Details может отличаться. Детали изменения и измерения — в [расширенном отчёте](extended-findings.md). Старые JSON не переписываются.

В samples используются provider/external_id, name/category, latitude/longitude, address, description, website_url/image_url, rating, price_amount/price_currency/price_period_or_total, availability, source_url/retrieved_at/raw_fields и дополнительные cuisine/opening_hours/entrance_fee/country_code/timezone. Для города, OSM и keyed POI есть нормализация; для FX/валютных справочников и GeoNames сохраняется маленькая исходная структура, без выдачи `0/0` за статистику POI.

`category` нормализованной записи — группа поиска, а не реально возвращённый дополнительный факт. Адрес может содержать только часть компонентов. Поля валюты страны и валюта конкретной цены не смешиваются. Отсутствие картинки в normalizer не доказывает отсутствие ссылки на Wikimedia в raw_fields. При необходимости добавляйте новый подтверждённый mapping, а не генерируйте недостающий контент.

Latency измеряется вокруг запроса/чтения/разбора, без намеренной паузы перед запросом. При timeout это длительность попытки, а не успешного ответа. HTTP 401/403/429 останавливают дальнейшие обращения к данному провайдеру в этом запуске; 404/5xx записываются без автоматического повтора. Сырые тела ошибок не сохраняются, поскольку могут отражать ключи. SHA-256 публичного ответа помогает сверять изменяемые справочники, но не заменяет сохранение версии релиза.

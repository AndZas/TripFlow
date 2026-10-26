# Free API Gap Test

Отдельный исследовательский CLI для `TASK.md`. Сам по себе запуск не обращается к внешним API: для этого нужен явный `--live`. Код не читает `.env` автоматически и не копирует ключи из прежнего эксперимента.

Результаты последнего живого запуска и решение по источникам описаны в [assessment.md](reports/assessment.md); условия и официальные ссылки — в [sources.md](reports/sources.md). Сырые результаты по датированным запускам сохраняются локально и не включаются в Git.

## Подготовка в Windows PowerShell

```powershell
cd F:\Files\PythonProjects\TripFlow\API\experiments\free-api-gap-test
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe gap_test.py --offline
```

Сторонние библиотеки не нужны. Отчёты создаются в `reports/runs/<UTC-id>/`; `results.json` содержит статусы, заполненность, сравнения и длительность; `live-results.md` — читаемую сводку; `samples/` — до двух очищенных нормализованных объектов на endpoint/тип. `reports/assessment.md` обновляется после запуска. Папка runs игнорируется Git.

## Бесплатные ключи

1. **Geoapify:** зарегистрируйтесь на [Geoapify MyProjects](https://myprojects.geoapify.com/) и оставьте план **Free**. Создайте проект; ключ доступен в **API Keys**. Бесплатный план на 26.10.2026: 3 000 кредитов/день, до 5 запросов/с, карта не нужна. В нашей проверке нужен только Geocoding. Установите `GEOAPIFY_API_KEY` и `GEOAPIFY_FREE_PLAN=1`.
2. **OpenTripMap:** лично зарегистрируйтесь на [OpenTripMap](https://dev.opentripmap.org/register), выберите **Free** и получите API key в кабинете. На 26.10.2026 Free — только **non-commercial**, 5 000 запросов/день и 10 запросов/с. Не выбирайте платный план и trial. Установите `OPENTRIPMAP_API_KEY` и `OPENTRIPMAP_FREE_NONCOMMERCIAL=1`.
3. **Frankfurter:** ключ не нужен.
4. **Wikidata/Commons:** ключ не нужен. Для условного этапа задайте `WIKIMEDIA_USER_AGENT` с названием `TripFlow` и своим контактным email или URL, например `TripFlow-FreeApiGapTest/1.0 (you@example.org)`. Не используйте вымышленный контакт. Без него этап будет пропущен.

В текущей сессии PowerShell:

```powershell
$env:GEOAPIFY_API_KEY = 'ваш_ключ'
$env:GEOAPIFY_FREE_PLAN = '1'
$env:OPENTRIPMAP_API_KEY = 'ваш_ключ'
$env:OPENTRIPMAP_FREE_NONCOMMERCIAL = '1'
$env:WIKIMEDIA_USER_AGENT = 'TripFlow-FreeApiGapTest/1.0 (ваш_email_или_URL)'
```

Переменные действуют только в этом процессе PowerShell. Если запускать скрипт через Codex, переменные должны быть доступны **процессу, запускающему Python**; настройка в другом окне PowerShell не переносится автоматически. Ключи в чат не отправляйте. `.env.example` — перечень имён, не файл для реальных значений. Реальный `.env` игнорируется Git, но скрипт его не читает.

## Живой запуск после вашего указания

```powershell
.\.venv\Scripts\python.exe gap_test.py --live
```

Для части источников: `--providers geoapify frankfurter`. Можно уменьшить `--max-requests 20`; верхний предел 50. `--delay-seconds` не меньше 1, запросы идут последовательно и без повторов. При 401/403/429 запросы к соответствующему поставщику прекращаются. При глобальном пределе оставшиеся шаги получают `skipped`. Перед первым живым запуском сверьте статус Free в кабинетах и актуальные правила в [reports/sources.md](reports/sources.md).

OpenTripMap сначала проверяет выбранные `kinds` по официальному каталогу. Если каталог не доступен или категорий в нём нет, POI-запросы пропускаются. Это осознанная проверка схемы, а не нулевая заполненность. Старые Places, GeoNames, Open-Meteo, EUR/RUB и Overpass повторно не вызываются.

Если основной прогон не сопоставил объекты с сохранёнными Geoapify samples, возможен небольшой точечный этап по QID, уже встречающимся в этих samples:

```powershell
.\.venv\Scripts\python.exe gap_test.py --live --targeted-from <UTC-id-основного-прогона> --max-requests 16
```

Он не повторяет основной поиск и создаёт новый связанный отчёт. Ответ 404 означает лишь, что конкретный QID не найден через OpenTripMap Details; его нельзя считать доказательством отсутствия объекта во всех источниках.

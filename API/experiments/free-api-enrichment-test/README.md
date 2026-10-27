# Free API Enrichment Test

Изолированный исследовательский стенд для [задания](TASK.md). Он использует только стандартную библиотеку Python, не изменяет код TripFlow и сохраняет каждый запуск в новом `reports/runs/<UTC-id>/`. Итоги — в [оценке](reports/assessment.md), проверенные официальные условия — в [источниках](reports/sources.md), а два очищенных итоговых запуска — в [evidence](reports/evidence/README.md). Предыдущие эксперименты только читаются: базовый набор для сопоставления состоит из шести сохранённых POI Geoapify, фактически найденных в `../data-source-survey/data/samples/20261015T150210175612Z/`; ожидаемого `../free-api-gap-test/data/` в репозитории нет.

## Запуск в PowerShell

Из этой папки:

```powershell
python .\enrichment_test.py --offline
python .\enrichment_test.py --live --providers wikimedia --max-requests 6
python .\enrichment_test.py --live --providers datatourisme wikimedia --max-requests 20
```

`--offline` не делает HTTP запросов. В live режиме провайдер без переменных среды получает `skipped_missing_config`. CLI никогда не читает `.env` автоматически. Ключи нельзя передавать флагами, добавлять в Git или присылать в чат. Пределы: до 24 запросов за запуск, до 10 объектов в ответе, последовательные запросы с паузой минимум 1 с, timeout 2–30 с. По умолчанию 18/5/1 с/15 с. При 401/403/429 провайдер прекращается без повтора. Amadeus Self-Service закрыт; этот маршрут всегда получает `skipped_provider_unavailable`, а HTTP-клиент блокирует вызов.

## Получение переменных среды

**DATAtourisme.** Заполните [официальную форму получения бесплатного ключа](https://www.datatourisme.fr/utiliser-les-donnees/) (можно указать профиль студент). Дождитесь ключа от сервиса. Он нужен для `DATATOURISME_API_KEY`. Используется заголовок `X-API-Key`, ключ не попадает в URL или отчёт.

**Amadeus Self-Service.** [Официальный портал](https://developers.amadeus.com/toolbox) сообщает, что Self-Service закрыт 17 июля 2026 года; `register` перенаправляет на портал Enterprise. Получать `AMADEUS_CLIENT_ID` и `AMADEUS_CLIENT_SECRET` для этого эксперимента больше не нужно. Варианты `Contact sales` на общей странице относятся к Enterprise и не подтверждают бесплатный доступ. Историческое описание Test API оставлено только для анализа старого контракта.

**Wikimedia.** Ключ не нужен. Установите `WIKIMEDIA_USER_AGENT` в формате `TripFlow-EnrichmentTest/1.0 (ваш_реальный_email_или_URL)`. Контакт должен быть вашим, фиктивный контакт не подойдёт. Политика [Wikimedia User-Agent](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy/en) требует идентифицируемый клиент и контакт.

Пример настройки **в том же окне PowerShell, где запустится Python**:

```powershell
$env:DATATOURISME_API_KEY = 'полученный_ключ'
$env:WIKIMEDIA_USER_AGENT = 'TripFlow-EnrichmentTest/1.0 (ваш_реальный_контакт)'
python .\enrichment_test.py --live --providers datatourisme wikimedia --max-requests 20
```

Если ключ уже сохранён как пользовательская переменная Windows, но Codex был запущен до её создания, для одного запуска в PowerShell можно загрузить его в дочерний процесс без печати значения:

```powershell
$env:DATATOURISME_API_KEY = [Environment]::GetEnvironmentVariable('DATATOURISME_API_KEY', 'User')
python .\enrichment_test.py --live --providers datatourisme --max-requests 14
```

Переменные из другого окна PowerShell не передаются автоматически в процесс Codex. Если хотите, чтобы live-run запустил Codex, настройте их в окружении, из которого стартует Codex, перезапустите его при необходимости и сообщите **только что переменные доступны**, без значений. Скрипт сам проверяет их наличие; можно сначала запустить `--offline`.

## Чтение результатов

`results.json` содержит статусы, HTTP код, задержки, нормализованные объекты и `filled/denominator` по каждому полю. `live-results.md` — сводка, `samples/` — до двух очищенных примеров на endpoint. Сырые ответы API, заголовки и тела ошибок не сохраняются. Папка `reports/runs/` локальна и игнорируется Git. Для воспроизводимого вывода на GitHub сохранены только два очищенных итоговых запуска в `reports/evidence/`; абсолютный путь к исходным samples заменён на относительный. Для обсуждения нового запуска достаточно его UTC-id, `live-results.md` и очищенного `results.json`; ключи не отправляйте.

Сопоставление по сохранённым POI допускает точный Wikidata ID только с подтверждением имени и расстояния не более 150 м, либо одинаковое нормализованное имя в 150 м. Возможные или неоднозначные совпадения не повышают coverage. Малый набор в Париже не измеряет мировое покрытие. Для цен без известной единицы не вычисляется стоимость «за человека за ночь» и рубли. Изображение допускается к показу только после проверки конкретной лицензии и исполнения условий атрибуции.

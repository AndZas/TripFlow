# TripFlow Backend

Backend на ASP.NET Core Minimal API, .NET 10 и PostgreSQL. Схемой базы управляют миграции EF Core.

## Запуск для показа через Docker

Запустите Docker Desktop с поддержкой Linux-контейнеров и укажите локальный пароль базы в `Backend/.env` через `TRIPFLOW_POSTGRES_PASSWORD`. Скопируйте репозиторий целиком. Backend использует общий справочник направлений. Из папки `Backend/` выполните:

```powershell
docker compose up --build -d
```

При первой сборке Docker скачает образы .NET и пакеты NuGet. Когда команда завершится, откройте [Swagger UI](http://127.0.0.1:5080/swagger) и проверьте `GET /api/health`. Для показа можно зарегистрировать тестового пользователя и создать дашборд по шагам ниже.

Compose запускает PostgreSQL и Backend в режиме `Development` со Swagger. При первом старте Backend применяет миграции к пустой базе. Данные PostgreSQL сохраняются в томе `postgres-data` после `docker compose down`.

Если Swagger не открывается, проверьте `docker compose ps` и `docker compose logs backend`. После показа остановите сервер командой `docker compose down`.

## Запуск Backend через .NET

Для локального запуска нужен .NET 10 SDK. Из каталога `Backend/` поднимите базу в Docker и запустите Backend:

```powershell
docker compose up -d --wait postgres
dotnet run --project .\TripFlow.Backend.csproj -- --urls http://127.0.0.1:5080 --environment Development
```

## Локальный PostgreSQL через Docker Desktop

В `Backend/.env` задайте `TRIPFLOW_POSTGRES_PASSWORD` с локальным паролем. Запустите Docker Desktop и выполните из `Backend/`:

```powershell
docker compose up -d --wait postgres
docker compose exec postgres psql -U tripflow -d tripflow -c "SELECT 1;"
```

При первом запуске Docker скачает образ PostgreSQL 18. С компьютера база доступна на `127.0.0.1:5433`, имя базы и пользователь — `tripflow`. Порт можно изменить через `TRIPFLOW_POSTGRES_PORT`. Для другого сервера или отдельной тестовой базы задайте строку подключения через `ConnectionStrings__TripFlow` при запуске через .NET.

`docker compose stop postgres` остановит базу. `docker compose down postgres` удалит контейнер с сохранением тома `postgres-data`. Удаление самого тома удаляет данные PostgreSQL.

## Проверка через Swagger

Откройте [Swagger UI](http://127.0.0.1:5080/swagger). Страница доступна в режиме `Development`.

1. Разверните `GET /api/health`, нажмите **Try it out**, затем **Execute**. Ответ `200` с `{"status":"ok"}` означает, что Backend работает и база доступна.
2. Откройте `POST /api/auth/register`. Нажмите **Try it out** и введите тестовые email и пароль, например `{"email":"swagger@example.test","password":"local-example-password"}`. Если аккаунт уже создан, используйте `POST /api/auth/login` с теми же данными.
3. Скопируйте `accessToken` из ответа. Нажмите **Authorize** и вставьте токен как есть, без префикса `Bearer`.
4. Вызовите `GET /api/auth/me`, чтобы проверить вход. Затем попробуйте `POST /api/dashboards` с телом `{"name":"Поездка в Москву"}` и посмотрите результат через `GET /api/dashboards`.

Запросы из Swagger сохраняются в той же базе, которую использует приложение. При первом запуске после перехода с JSON зарегистрируйте аккаунт заново.

Проверка запуска без Swagger:

```powershell
Invoke-RestMethod http://127.0.0.1:5080/api/health
```

API принимает JSON с `Content-Type: application/json`. После регистрации или входа передавайте полученный `accessToken` в заголовке `Authorization: Bearer <accessToken>`. Доступ к дашборду получают его владелец и зарегистрированные участники, вступившие по приглашению.

| Метод и путь | Действие |
|---|---|
| `GET /api/health` | Проверить доступность сервера |
| `GET /api/destinations` | Получить направления из общего справочника |
| `POST /api/auth/register` | Создать аккаунт и сессию. Тело с `email` и `password` |
| `POST /api/auth/login` | Войти. Тело с `email` и `password` |
| `GET /api/auth/me` | Получить идентификатор и email своего аккаунта |
| `POST /api/auth/logout` | Завершить текущую сессию |
| `GET /api/dashboards` | Получить список своих дашбордов |
| `POST /api/dashboards` | Создать дашборд. Тело с `name` и необязательным `description` |
| `GET /api/dashboards/{id}` | Получить дашборд с опубликованными карточками и своими черновиками |
| `DELETE /api/dashboards/{id}` | Удалить дашборд со всеми карточками. Доступно владельцу |
| `POST /api/dashboards/{id}/invite` | Выпустить токен приглашения. Доступно владельцу. Предыдущий токен перестаёт действовать |
| `POST /api/dashboards/join` | Вступить по приглашению. Тело с `token` |
| `POST /api/dashboards/{id}/cards` | Создать черновик с параметрами поездки |
| `GET /api/dashboards/{id}/cards/{cardId}` | Прочитать карточку |
| `PUT /api/dashboards/{id}/cards/{cardId}` | Заменить параметры поездки. Доступно автору |
| `DELETE /api/dashboards/{id}/cards/{cardId}` | Удалить черновик или опубликованную карточку. Доступно автору |
| `POST /api/dashboards/{id}/cards/{cardId}/publish` | Опубликовать карточку. Доступно автору |
| `POST /api/dashboards/{id}/cards/{cardId}/generation` | Запустить подбор или запросить дополнительные варианты |
| `PUT /api/dashboards/{id}/cards/{cardId}/hotel` | Сохранить выбор отеля и тарифа |
| `PUT /api/dashboards/{id}/cards/{cardId}/attractions` | Сохранить список выбранных достопримечательностей |
| `POST /api/dashboards/{id}/cards/{cardId}/budget` | Запустить расчёт бюджета по текущему выбору |
| `PUT /api/dashboards/{id}/cards/{cardId}/vote` | Проголосовать или подтвердить голос. Тело с `cardVersion` |
| `DELETE /api/dashboards/{id}/cards/{cardId}/vote` | Снять свой голос |

Первые четыре маршрута доступны без токена. Пароль должен содержать от 10 до 128 символов. При ошибках проверки JSON с описанием проблемы содержит `status`, а ошибки отдельных полей возвращаются в `errors`.

Пример создания и публикации карточки из PowerShell:

```powershell
$api = 'http://127.0.0.1:5080/api'
$credentials = @{ email = 'student@example.test'; password = 'local-example-password' }
$session = Invoke-RestMethod "$api/auth/register" -Method Post -ContentType 'application/json' -Body ($credentials | ConvertTo-Json)
$auth = @{ Authorization = "Bearer $($session.accessToken)" }
$board = Invoke-RestMethod "$api/dashboards" -Method Post -Headers $auth -ContentType 'application/json' -Body '{"name":"Moscow trip"}'
$trip = @{
    destinationId = 'ru-moscow'
    startDate = '2027-06-10'
    endDate = '2027-06-15'
    travelers = 2
    budgetRub = 75000
    preferences = 'Museums and parks'
}
$cards = "$api/dashboards/$($board.id)/cards"
$card = Invoke-RestMethod $cards -Method Post -Headers $auth -ContentType 'application/json' -Body ($trip | ConvertTo-Json)
Invoke-RestMethod "$cards/$($card.id)/publish" -Method Post -Headers $auth
```

После редактирования опубликованной карточки предыдущий голос продолжает учитываться в `voteCount`. У проголосовавшего участника `myVoteNeedsReview` становится `true`. Чтобы подтвердить голос, клиент передаёт актуальное значение `version` карточки в поле `cardVersion`. При попытке проголосовать за старую версию сервер возвращает `409`.

Аккаунты, сессии, дашборды, участники, карточки, голоса и задачи Python хранятся в PostgreSQL. Снимки запросов Python, варианты, выбор и смета сохраняются в колонках `jsonb`. Сессия действует 12 часов или до выхода, в базе хранится хеш токена. Для запросов с другого origin добавьте его через `Cors__Origins__0`, например `http://localhost:5173`.

Карточку можно опубликовать с валидными параметрами поездки. Предложения изменений относятся к следующей итерации.

## Удаление дашбордов и карточек

Оба запроса `DELETE` выполняются без тела и при успехе возвращают `204 No Content`. Удаление окончательное. Вместе с карточкой удаляются её голоса. При удалении дашборда удаляются все карточки (включая чужие и черновики) с голосами, записи об участии и приглашение.

Запрос без действующей сессии получает `401`. Участник, пытающийся удалить дашборд или видимую карточку без нужных прав, получает `403`. Ответ `404` означает, что ресурс отсутствует или скрыт от пользователя. Этот же код возвращается при повторном удалении уже удалённого ресурса.

## Подбор и смета

Маршруты относятся к карточке (`{card} = /api/dashboards/{dashboardId}/cards/{cardId}`). Автор запускает подбор и смету и меняет выбор. Маршруты ниже описывают интерфейс C# для React. Состояние соединения с Python описано отдельно. Чтение карточки использует общие правила видимости. [Сценарии](../API/docs/SCENARIOS.md) · [JSON-схемы](../API/docs/BACKEND-HANDOFF.md)

| Запрос | Тело и результат |
|---|---|
| `POST {card}/generation` | `{"target":"all"}` запускает поиск обоих типов. Для отдельного типа используется `hotels` или `attractions` и необязательное `refinement`. Для замены посещения можно передать `replaceAttractionId` с ID выбранного варианта. |
| `PUT {card}/hotel` | `{"hotelId":"<UUID варианта>"}` выбирает сохранённый вариант со снимком тарифа. `{"hotelId":null}` снимает выбор. |
| `PUT {card}/attractions` | `{"attractionIds":["<UUID варианта>"]}` заменяет список. Пустой список снимает выбор. |
| `POST {card}/budget` | Без тела. Backend берёт параметры, выбранные объекты, цены и включённые услуги из хранилища. |
| `GET {card}` | Возвращает `recommendations`, `selection` и `budget` вместе с существующими полями карточки. |

Запуск подбора и сметы возвращает `202` с расширенной карточкой после подтверждения Python. Изменение выбора возвращает `200` с той же структурой. Для сохранения выбора используются ID из `recommendations.*.items[].id`. Стабильный `candidate.objectId` используется при обмене с Python.

Клиент может опрашивать `GET {card}`, пока нужные статусы равны `pending`. После догенерации новый пакет добавляется к предыдущим вариантам. `hasMore` равен `null` во время поиска. При сбое сохраняется прежняя выдача, а причина доступна в `recommendations.*.error`. По умолчанию запрашивается до трёх отелей и четырёх мест. Если есть полная смета, лимит определяется по доступному остатку, с учётом стоимости заменяемого варианта.

При изменении параметров или выбора версия карточки увеличивается, прежняя смета получает `stale`, а backend завершает старые попытки. При смене направления, дат или состава группы ранее выбранные варианты остаются видны с `needsReview: true`. Для новой сметы их надо обновить из новой выдачи или снять выбор.

### Связь с Python

Укажите выпущенный в кабинете ключ в `Backend/.env` как `API_TRIPFLOW=<ключ>`. При запуске из каталога `Backend/` его подхватывают `dotnet run` и Docker Compose. При необходимости ключ можно передать через переменную окружения `PythonApi__ApiKey`, которая имеет приоритет. [Инструкция по кабинету](../API/docs/PORTAL.md)

Backend по умолчанию использует `https://tripflow-api-x1p5.onrender.com`. Адрес можно переопределить через `PythonApi__BaseUrl`. При запуске через `dotnet run` в режиме `Development` поддерживается локальный Python, например `http://127.0.0.1:8000`. При отсутствии ключа запуск задач возвращает `503`. Backend использует формат первого этапа миграции с `destinationId` из общего справочника. [План миграции](../API/docs/BACKEND-MIGRATION.md) · [Текущий контракт Python](../API/docs/CONTRACT.md)

Backend создаёт отдельный `taskId` для каждой категории подбора и сметы. После `202 Accepted` фоновая служба читает `Location` с тем же `X-API-Key`, учитывает `Retry-After` и применяет `result` к актуальной версии карточки. Статусы читаются через `GET {card}`. При запуске обеих категорий ответ C# возвращает `202`, если Python принял хотя бы одну. Состояние каждой видно в её списке.

При временном сбое C# повторяет POST с сохранённым ID и телом либо продолжает GET. При перезапуске C# возобновляет незавершённые задачи. Для задач, сохранённых старым клиентом, C# пробует прочитать результат по ID. Если на Python такой задачи нет, можно запустить новую. По истечении срока попытка получает `failed` с кодом `TASK_TIMEOUT`. Срок по умолчанию 300 секунд, настройка `PythonApi__TaskTimeoutSeconds`.

C# добавляет стоимость отеля и известных посещений к расходам Python. Смета содержит итог и округлённую вверх сумму на человека. При ночёвке без выбранного отеля, неизвестной цене или цене «от» итог помечается как нижняя граница, `remainingRub` возвращается как `null`.

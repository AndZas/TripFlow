# TripFlow Backend

Первый рабочий вариант на C# и ASP.NET Core Minimal API.

## Запуск для показа через Docker

На компьютере для показа должен быть запущен Docker с поддержкой Linux-контейнеров. Скопируйте репозиторий целиком: backend использует справочник `shared/data/destinations.json`. Из папки `Backend/` выполните:

```powershell
docker compose up --build -d
```

При первой сборке Docker скачает образы .NET и пакеты NuGet. Когда команда завершится, откройте [Swagger UI](http://127.0.0.1:5080/swagger) и проверьте `GET /api/health`. Для показа можно зарегистрировать тестового пользователя и создать дашборд по шагам ниже.

Docker запускает сервер в режиме `Development`, чтобы был доступен Swagger. Адрес доступен на компьютере, где запущен контейнер. Данные Docker сохраняются в отдельном томе `backend-data`. При первом запуске хранилище пустое. Оно сохраняется после `docker compose down`, а при следующем запуске нужно заново войти в аккаунт.

Если Swagger не открывается, проверьте `docker compose ps` и `docker compose logs backend`. После показа остановите сервер командой `docker compose down`.

## Запуск без Docker

Для локального запуска нужен .NET 10 SDK.

Выполните из каталога `Backend/`:

```powershell
dotnet run --project .\TripFlow.Backend.csproj -- --urls http://127.0.0.1:5080 --environment Development
```

## Проверка через Swagger

Откройте [Swagger UI](http://127.0.0.1:5080/swagger). Страница доступна в режиме `Development`.

1. Разверните `GET /api/health`, нажмите **Try it out**, затем **Execute**. Ответ `200` с `{"status":"ok"}` означает, что сервер запущен.
2. Откройте `POST /api/auth/register`. Нажмите **Try it out** и введите тестовые email и пароль, например `{"email":"swagger@example.test","password":"local-example-password"}`. Если аккаунт уже создан, используйте `POST /api/auth/login` с теми же данными.
3. Скопируйте `accessToken` из ответа. Нажмите **Authorize** и вставьте токен как есть, без префикса `Bearer`.
4. Вызовите `GET /api/auth/me`, чтобы проверить вход. Затем попробуйте `POST /api/dashboards` с телом `{"name":"Поездка в Москву"}` и посмотрите результат через `GET /api/dashboards`.

Запросы из Swagger сохраняют данные так же, как запросы из приложения. Чтобы повторять примеры с чистого листа, перед запуском можно указать отдельное хранилище через `TripFlow__StorePath`.

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

Данные сохраняются в `App_Data/tripflow.json`. Хранилище рассчитано на один экземпляр API. Путь можно задать через `TripFlow__StorePath`. Сессии действуют 12 часов или до выхода или перезапуска сервера. Для запросов с другого origin добавьте его через `Cors__Origins__0`, например `http://localhost:5173`.

Карточку можно опубликовать с валидными параметрами поездки. Предложения изменений относятся к следующей итерации.

## Удаление дашбордов и карточек

Оба запроса `DELETE` выполняются без тела и при успехе возвращают `204 No Content`. Удаление окончательное. Вместе с карточкой удаляются её голоса. При удалении дашборда удаляются все карточки (включая чужие и черновики) с голосами, записи об участии и приглашение.

Запрос без действующей сессии получает `401`. Участник, пытающийся удалить дашборд или видимую карточку без нужных прав, получает `403`. Ответ `404` означает, что ресурс отсутствует или скрыт от пользователя. Этот же код возвращается при повторном удалении уже удалённого ресурса.

## Подбор и смета

Маршруты относятся к карточке (`{card} = /api/dashboards/{dashboardId}/cards/{cardId}`). Автор запускает подбор и смету и меняет выбор. Чтение карточки использует общие правила видимости. [Сценарии](../API/docs/SCENARIOS.md) · [JSON-схемы](../API/docs/BACKEND-HANDOFF.md)

| Запрос | Тело и результат |
|---|---|
| `POST {card}/generation` | `{"target":"all"}` запускает поиск обоих типов. Для отдельного типа используется `hotels` или `attractions` и необязательное `refinement`. Для замены посещения можно передать `replaceAttractionId` с ID выбранного варианта. |
| `PUT {card}/hotel` | `{"hotelId":"<UUID варианта>"}` выбирает сохранённый вариант со снимком тарифа. `{"hotelId":null}` снимает выбор. |
| `PUT {card}/attractions` | `{"attractionIds":["<UUID варианта>"]}` заменяет список. Пустой список снимает выбор. |
| `POST {card}/budget` | Без тела. Backend берёт параметры, выбранные объекты, цены и включённые услуги из хранилища. |
| `GET {card}` | Возвращает `recommendations`, `selection` и `budget` вместе с существующими полями карточки. |

Запуск подбора и сметы возвращает `202` с расширенной карточкой после подтверждения Python. Изменение выбора возвращает `200` с той же структурой. Для сохранения выбора используются ID из `recommendations.*.items[].id`. Стабильный `candidate.objectId` используется при обмене с Python.

Клиент может опрашивать `GET {card}`, пока нужные статусы равны `pending`. После догенерации новый пакет добавляется к предыдущим вариантам. `hasMore` равен `null` во время поиска. При сбое сохраняется прежняя выдача, а причина доступна в `recommendations.*.error`. По умолчанию запрашивается до трёх отелей и четырёх мест. Если есть полная смета, лимит определяется по доступному остатку, с учётом стоимости заменяемого варианта.

При изменении параметров или выбора версия карточки увеличивается, прежняя смета получает `stale`, а callback старой версии подтверждается без применения. При смене направления, дат или состава группы ранее выбранные варианты остаются видны с `needsReview: true`. Для новой сметы их надо обновить из новой выдачи или снять выбор.

### Связь с Python

Задайте `PythonApi__BaseUrl`, `PythonApi__ApiKey` и `PythonApi__CallbackKey` в окружении Backend. Базовый URL использует HTTPS. Для локальной проверки в Development допускается HTTP по loopback. Backend отправляет `X-API-Key` на `POST /v1/recommendations` и `POST /v1/budget`. В Python настройте HTTPS-адрес Backend с путём `POST /internal/tripflow/events` и заголовок `X-Callback-Key`. При отсутствующих настройках запуск задач возвращает `503`.

Backend сохраняет задачу до отправки. При временной ошибке связи повтор исходного запроса использует тот же `taskId` и снимок входа. Предельное ожидание результата по умолчанию составляет 300 секунд и настраивается через `PythonApi__TaskTimeoutSeconds`. После истечения срока ближайший опрос или новая попытка переводит просроченную задачу в `failed` с кодом `TASK_TIMEOUT`. Новый запуск получает новый ID.

В `recommendations.finished` приходят `taskId` и `results` с запрошенными типами, их `items`, статусом, `hasMore` и ошибкой при необходимости. Отель имеет `price` в целых рублях за всё проживание группы или `null`. Цена посещения содержит сумму, единицу и основание либо равна `null`. В `budget.finished` успешный результат содержит четыре статьи дополнительных расходов, а ошибка передаётся с `expenses: null` и `error`. Полные примеры приведены в [handoff](../API/docs/BACKEND-HANDOFF.md#2-итоговый-callback-подбора).

C# добавляет стоимость отеля и известных посещений к расходам Python. Смета содержит итог и округлённую вверх сумму на человека. При ночёвке без выбранного отеля, неизвестной цене или цене «от» итог помечается как нижняя граница, `remainingRub` возвращается как `null`.

Callback с корректным ключом получает `204` после записи результата, при повторной доставке или для устаревшей задачи. Неверный ключ даёт `401`, неизвестная задача — `404`, некорректное событие — `400`.

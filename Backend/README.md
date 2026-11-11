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
| `POST /api/dashboards/{id}/invite` | Выпустить токен приглашения. Доступно владельцу. Предыдущий токен перестаёт действовать |
| `POST /api/dashboards/join` | Вступить по приглашению. Тело с `token` |
| `POST /api/dashboards/{id}/cards` | Создать черновик с параметрами поездки |
| `GET /api/dashboards/{id}/cards/{cardId}` | Прочитать карточку |
| `PUT /api/dashboards/{id}/cards/{cardId}` | Заменить параметры поездки. Доступно автору |
| `POST /api/dashboards/{id}/cards/{cardId}/publish` | Опубликовать карточку. Доступно автору |
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

Пока карточка публикуется с валидными параметрами поездки. Подключение Python API, выбор отелей и достопримечательностей, расчёт итоговой стоимости и предложения изменений относятся к следующим итерациям.

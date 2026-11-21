# TripFlow · Карточка поездки на DeepSeek Flash

Рабочая папка для команд и файлов стенда — `API/experiments/deepseek-flash`.

Стенд повторяет сценарий [card-preferences](../../../experiments/card-preferences). Он разбирает пожелания, получает отели из Russhotels и места из Geoapify, проверяет дополнительные условия по выдержкам из источников и оценивает расходы после выбора. Для оценок используются справочные ставки Росстата, а Python проверяет цитаты, применяет подтверждённые включения и рассчитывает суммы на группу.

Модель `deepseek-flash` вызывается через Chat Completions. Схема ответа передаётся в промпте, DeepSeek возвращает JSON, а Python проверяет структуру, значения и связь с исходными данными. Обычные запросы выполняются с отключённым рассуждением. Флаг `analyze.py --reasoning` включает его для первичного разбора фильтров. [Режим JSON в DeepSeek](https://api-docs.deepseek.com/guides/json_mode/)

## Браузерный конструктор

Укажи `DEEPSEEK_API_KEY` в локальном `.env` рядом со скриптами. Для выдачи мест нужна переменная окружения `GEOAPIFY_API_KEY`. Запусти [start-stand.cmd](../../../experiments/deepseek-flash/start-stand.cmd) двойным кликом или из PowerShell в папке эксперимента.

```powershell
.\start-stand.cmd
```

Скрипт подготовит своё окружение и откроет [стенд на порту 8766](http://127.0.0.1:8766/). Кнопка «Заполнить пример» подставит карточку для первого прогона. Для остановки используй «Остановить стенд» или `Ctrl+C`. Порт можно сменить через `--port`, а запуск браузера отключить через `--no-browser`.

## Отдельные этапы

Из папки эксперимента после установки зависимостей через `start-stand.cmd` или `pip install -r requirements.txt` в `.venv`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest
.\.venv\Scripts\python.exe -X utf8 probe.py
.\.venv\Scripts\python.exe -X utf8 analyze.py --suite --cases audit-preferences.json --output runs/preferences.jsonl
.\.venv\Scripts\python.exe -X utf8 stage2.py --snapshot audit-judge-cases.json --output runs/judge.json
.\.venv\Scripts\python.exe -X utf8 stage3.py --suite budget-cases.json --output runs/budget.jsonl
.\.venv\Scripts\python.exe -X utf8 audit_pipeline.py --card audit-card.json --output runs/pipeline.json
```

Для живого поиска по карточке используй `stage2.py --card demo-card.json --output runs/card.json`. Для серии проверок источников доступен `stage2.py --judge-suite --cases discovery-cases.json --output runs/discovery.json`. `stage2.py --check` принимает JSON с одним отелем и условием по образцу `discovery-cases.json`. `stage3.py --card budget-demo.json --verify-tariff` может проверить завтрак в конкретном тарифе. Для каждой серии указывай новый путь `--output`.

Для чтения динамических страниц используется Playwright. Если Edge отсутствует, установи Chromium командой `.\.venv\Scripts\python.exe -m playwright install chromium` или задай `TRIPFLOW_BROWSER_CHANNEL`. OCR сканов требует Tesseract и `rus.traineddata` в `.venv/tessdata` или каталоге `TRIPFLOW_TESSDATA`. Поисковые движки задаются в `TRIPFLOW_SEARCH_BACKEND`, по умолчанию `yandex,seznam`.

`.env` и `runs/` игнорируются Git. В журналах отдельных этапов сохраняются идентификаторы ответов DeepSeek (`responseId`), время и токены (`usage`). `probe.py --balance-only` запрашивает только баланс.

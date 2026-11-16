"""HTTP client shared by the experiment and the connection probe."""

import json
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
ENV_FILE = Path(__file__).with_name(".env")


class InferenceError(RuntimeError):
    """DeepSeek could not be reached or rejected the request."""


def read_api_key():
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DEEPSEEK_API_KEY":
                api_key = value.strip().strip("\"'")
                if api_key:
                    return api_key
    raise InferenceError(f"Заполни DEEPSEEK_API_KEY в {ENV_FILE}")


def request_api(path, payload=None):
    headers = {"Authorization": f"Bearer {read_api_key()}"}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(BASE_URL + path, data=body, headers=headers)
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as error:
        hints = {401: "Проверь ключ в .env.", 402: "Недостаточно средств на API-балансе.",
                 429: "Превышен лимит запросов."}
        hint = hints.get(error.code, "")
        raise InferenceError(f"DeepSeek {path}: HTTP {error.code}. {hint}".rstrip()) from None
    except (URLError, TimeoutError):
        raise InferenceError(f"DeepSeek {path}: ошибка подключения или истекло время ожидания.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise InferenceError(f"DeepSeek {path}: сервер вернул нечитаемый ответ.") from None


def complete(data, prompt, schema, trace, reasoning=False):
    system_prompt = (f"{prompt}\n\nВерни один JSON-объект с данными по этой схеме, "
                     f"соблюдай имена полей и типы:\n{json.dumps(schema, ensure_ascii=False)}")
    payload = {
        "model": MODEL,
        "thinking": {"type": "enabled" if reasoning else "disabled"},
        "temperature": 0,
        "max_tokens": 8192 if reasoning else 1600,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
        "response_format": {"type": "json_object"},
    }
    if reasoning:
        payload["reasoning_effort"] = "low"
    started = monotonic()
    try:
        reply = request_api("/chat/completions", payload)
    finally:
        trace["requestSeconds"] = round(monotonic() - started, 3)
    try:
        choice = reply["choices"][0]
        message = choice["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError):
        raise InferenceError("DeepSeek вернул ответ без сообщения модели.") from None
    trace.update(responseId=reply.get("id"), model=reply.get("model"),
                 finishReason=choice.get("finish_reason"), usage=reply.get("usage"), message=message)
    if choice.get("finish_reason") == "length":
        raise ValueError("Ответ модели обрезан по лимиту")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek вернул пустой JSON-ответ")
    return json.loads(content)

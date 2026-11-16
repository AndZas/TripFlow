import json
import logging
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODEL = "deepseek-flash"
BASE = "https://api.deepseek.com"
ENV = Path(__file__).with_name(".env")


class DeepSeekError(RuntimeError):
    pass


def api_key():
    if ENV.is_file():
        for line in ENV.read_text(encoding="utf-8-sig").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DEEPSEEK_API_KEY" and (key := value.strip().strip("\"'")):
                return key
    raise DeepSeekError("Укажи DEEPSEEK_API_KEY в локальном .env.")


def call(path, payload, timeout=100):
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    request = Request(BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
    start = monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        hint = {401: " Проверь API-ключ.", 402: " Проверь баланс API.", 429: " Превышен лимит запросов."}
        raise DeepSeekError(f"DeepSeek ответил HTTP {error.code}.{hint.get(error.code, '')}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise DeepSeekError("Не удалось получить ответ DeepSeek.") from None
    if not isinstance(result, dict) or result.get("error"):
        raise DeepSeekError("DeepSeek вернул ошибку обработки запроса.")
    logging.info("DeepSeek %s %.1f s id=%s usage=%s", path, monotonic() - start,
                 result.get("id", "–"), result.get("usage", "–"))
    return result


def complete(prompt, data, *, web=False):
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
        "thinking": {"type": "enabled" if web else "disabled"},
    }
    if web:
        payload.update(tools=[{"type": "deepseek_web_search"}], reasoning_effort="low")
    else:
        payload.update(response_format={"type": "json_object"}, max_tokens=3300, temperature=0)
    response = call("/chat/completions", payload)
    try:
        choice = response["choices"][0]
        message = choice["message"]
        if web and choice["finish_reason"] in {"stop", "length"}:
            return message
        if choice["finish_reason"] == "stop" and isinstance(result := json.loads(message["content"]), dict):
            return result
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    raise DeepSeekError("DeepSeek не вернул пригодный ответ для этого этапа.")

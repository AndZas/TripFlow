import json
import logging
from pathlib import Path
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODEL = "deepseek-flash"
BASE = "https://api.deepseek.com"
ENV = Path(__file__).with_name(".env")


class DeepSeekError(RuntimeError):
    pass


class Usage:
    LIMITS = {"search": 7, "fetch": 5, "model": 6}
    INPUT_LIMIT = 140_000
    OUTPUT_LIMIT = 13_200

    def __init__(self):
        self.lock = Lock()
        self.attempts = dict.fromkeys(self.LIMITS, 0)
        self.billed = {"search": 0, "fetch": 0}
        self.tokens = {"cacheHit": 0, "cacheMiss": 0, "output": 0}
        self.input_bytes = 0
        self.output_reserved = 0

    def reserve(self, kind, body, max_output=0):
        with self.lock:
            if self.attempts[kind] >= self.LIMITS[kind]:
                raise DeepSeekError(f"Исчерпан лимит этапа {kind}.")
            if kind == "model":
                if self.input_bytes + len(body) > self.INPUT_LIMIT or self.output_reserved + max_output > self.OUTPUT_LIMIT:
                    raise DeepSeekError("Исчерпан лимит объёма запросов к Flash.")
                self.input_bytes += len(body)
                self.output_reserved += max_output
            self.attempts[kind] += 1

    def record(self, kind, result):
        with self.lock:
            if (kind == "search" and result.get("results")) or (kind == "fetch" and result.get("content")):
                self.billed[kind] += 1
            if kind == "model":
                usage = result.get("usage") or {}
                hit = usage.get("prompt_cache_hit_tokens", 0)
                self.tokens["cacheHit"] += hit
                self.tokens["cacheMiss"] += usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
                self.tokens["output"] += usage.get("completion_tokens", 0)

    def snapshot(self):
        with self.lock:
            total = 0.005 * sum(self.billed.values()) + (0.04 * self.tokens["cacheHit"] +
                    2 * self.tokens["cacheMiss"] + 8 * self.tokens["output"]) / 1_000_000
            return {"attempts": dict(self.attempts), "billed": dict(self.billed), "tokens": dict(self.tokens),
                    "peakCny": round(total, 5)}


def api_key():
    if ENV.is_file():
        for line in ENV.read_text(encoding="utf-8-sig").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DEEPSEEK_API_KEY" and (key := value.strip().strip("\"'")):
                return key
    raise DeepSeekError("Укажи DEEPSEEK_API_KEY в локальном .env.")


def call(path, payload, usage, kind, *, timeout=22):
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    usage.reserve(kind, body, payload.get("max_tokens", 0))
    request = Request(BASE + path, data=body, headers=headers)
    start = monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        hint = {401: " Проверь API-ключ.", 402: " Проверь баланс API.", 429: " Превышен лимит запросов."}
        raise DeepSeekError(f"DeepSeek ответил HTTP {error.code}.{hint.get(error.code, '')}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise DeepSeekError("Не удалось получить ответ DeepSeek.") from None
    if isinstance(result, dict):
        usage.record(kind, result)
    if not isinstance(result, dict) or result.get("error"):
        raise DeepSeekError("DeepSeek вернул ошибку обработки запроса.")
    logging.info("DeepSeek %s %.1f s id=%s usage=%s", path, monotonic() - start,
                 result.get("id", "–"), result.get("usage", "–"))
    return result


def complete(prompt, data, usage, *, max_tokens):
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    response = call("/chat/completions", payload, usage, "model", timeout=35)
    try:
        choice = response["choices"][0]
        message = choice["message"]
        if choice["finish_reason"] == "stop" and isinstance(result := json.loads(message["content"]), dict):
            return result
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    raise DeepSeekError("DeepSeek не вернул пригодный ответ для этого этапа.")

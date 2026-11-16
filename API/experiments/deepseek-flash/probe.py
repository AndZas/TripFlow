import argparse
import json
from time import perf_counter

from deepseek_api import MODEL, InferenceError, request_api


PREFERENCES = "Нужен отель с завтраком, не дороже 7000 рублей за ночь. Хотелось бы сходить в музеи."


def main():
    parser = argparse.ArgumentParser(description="Проверка ключа и один запрос к DeepSeek Flash.")
    parser.add_argument("--balance-only", action="store_true", help="Проверить только баланс.")
    args = parser.parse_args()

    balance = request_api("/user/balance")
    print(json.dumps(balance, ensure_ascii=False, indent=2), flush=True)
    if args.balance_only:
        return
    if not balance["is_available"]:
        raise SystemExit("DeepSeek сообщает, что баланс недоступен для генерации.")

    print(f"\nПожелания: {PREFERENCES}", flush=True)
    start = perf_counter()
    response = request_api("/chat/completions", {
        "model": MODEL,
        "thinking": {"type": "disabled"},
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "Извлеки предпочтения путешественника. Верни JSON с полями breakfastRequired "
                "(обязателен ли завтрак), hotelMaxNightlyRub (лимит за ночь в рублях), "
                "interests (интересы по-русски). Пример структуры: "
                '{"breakfastRequired": false, "hotelMaxNightlyRub": null, "interests": []}. '
                "Не называй конкретные отели или достопримечательности."
            )},
            {"role": "user", "content": PREFERENCES},
        ],
    })
    elapsed = perf_counter() - start
    choice = response["choices"][0]
    content = choice["message"]["content"] or ""
    print(f"\nМодель: {response['model']} | {elapsed:.2f} с | finish_reason: {choice['finish_reason']}")
    print(f"ID ответа: {response.get('id')}")
    print(f"Токены: {json.dumps(response.get('usage'), ensure_ascii=False)}")
    print(f"Ответ:\n{content if content.strip() else '(пустой)'}")
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise SystemExit("Ответ модели не удалось прочитать как JSON.") from None
    expected = {"breakfastRequired": True, "hotelMaxNightlyRub": 7000, "interests": ["музеи"]}
    if result != expected:
        raise SystemExit(f"API ответил, но результат отличается от ожидаемого: {expected}")
    print("Все три пожелания распознаны.")


if __name__ == "__main__":
    try:
        main()
    except InferenceError as error:
        raise SystemExit(str(error)) from None

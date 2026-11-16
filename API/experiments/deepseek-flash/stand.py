"""TripFlow card experiment with DeepSeek Flash."""

import argparse
import json
import logging
import os
import re
import secrets
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from deepseek_api import InferenceError, request_api
from stage2 import read_destinations, select
from stage3 import estimate, group_total


ASSETS = Path(__file__).with_name("stand_web")
FILES = {"/": ("index.html", "text/html"), "/stand.css": ("stand.css", "text/css"),
         "/stand.js": ("stand.js", "text/javascript")}


def lodging_limit(budget, preferences):
    match = re.search(
        r"(?:отел\w*|проживани\w*|жиль[её])\s*[-—:–]?\s*(?:до|максимум|не больше|не более)\s*"
        r"(\d+(?:[ \u00a0\u202f]\d{3})*)(?:\s*(тыс(?:яч\w*)?\.?))?(?:\s*(?:₽|руб\w*\.?))?",
        preferences, re.I,
    )
    if match:
        tail = re.split(r"[.!?;,]", preferences[match.end():], maxsplit=1)[0]
        if not re.search(r"за ночь|в сутки|на (?:одного |1 )?человека|с человека", tail, re.I):
            rubles = int(re.sub(r"\s+", "", match[1])) * (1000 if match[2] else 1)
            return min(rubles, budget)
    return budget // 2


def card_input(data, destinations):
    try:
        duration = (date.fromisoformat(data["endDate"]) - date.fromisoformat(data["startDate"])).days
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError("Укажи даты начала и окончания поездки.") from error
    if not 1 <= duration < 90:
        raise ValueError("Поездка должна длиться от 1 до 89 ночей.")
    if data.get("destination") not in {row["id"] for row in destinations}:
        raise ValueError("Выбери направление из списка.")
    group, budget = (data.get(key) for key in ("travelers", "budgetRub"))
    if type(group) is not int or not 1 <= group <= 50:
        raise ValueError("Укажи от 1 до 50 путешественников.")
    if type(budget) is not int or not 1 <= budget <= 10_000_000:
        raise ValueError("Укажи целевой бюджет группы в рублях.")
    preferences = data.get("preferences")
    if not isinstance(preferences, str) or len(preferences) > 2000:
        raise ValueError("Пожелания должны содержать до 2000 символов.")
    return {**{key: data[key] for key in ("destination", "startDate", "endDate", "travelers", "budgetRub")},
            "hotelBudgetRub": lodging_limit(budget, preferences), "preferences": preferences.strip()}


def budget_input(pick, recommendations):
    hotel = next((row for row in recommendations["hotels"] if row["id"] == pick.get("hotelId")), None)
    if hotel is None:
        raise ValueError("Выбери отель из текущей подборки.")
    ids = pick.get("placeIds", [])
    available = {row["id"]: row for row in recommendations["attractions"]}
    if (not isinstance(ids, list) or any(not isinstance(key, str) or key not in available for key in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Выбери места из текущей подборки.")
    places = [available[key] for key in ids]
    card = recommendations["card"]
    nights = (date.fromisoformat(card["endDate"]) - date.fromisoformat(card["startDate"])).days
    benefits = []
    if hotel.get("breakfastStatus") == "confirmed":
        benefits.append({"kind": "breakfast", "status": "confirmed", "coveredDays": nights,
                         "dayIndices": list(range(2, nights + 2)), "source": hotel["source"]})
    return {**{key: card[key] for key in ("startDate", "endDate", "travelers", "budgetRub")},
            "hotel": hotel, "benefits": benefits, "expenseNotes": recommendations["parsed"]["expenses"],
            "selectedPlaces": places}


def calculate(card, args, progress):
    trace = {}
    places = []
    for place in card["selectedPlaces"]:
        if place["price"] is not None:
            places.append({"id": place["id"], "name": place["name"],
                           "groupRub": place["price"] * card["travelers"], "origin": "Geoapify"})
        elif reference := place.get("priceReference"):
            places.append({"id": place["id"], "name": place["name"], "origin": "Росстат · ориентир",
                           "groupRub": group_total(reference["amount_rub"], "person_trip", card["travelers"], 1),
                           "reference": reference})
    priced = {place["id"] for place in places}
    estimate_card = {**card, "selectedPlaces": [
        {**row, "alreadyPriced": row["id"] in priced} for row in card["selectedPlaces"]
    ]}
    result = estimate(estimate_card, args, trace, progress)
    lodging = card["hotel"]["indicativeGroupRub"]
    tickets = sum(place["groupRub"] for place in places)
    other = result["expenses"].get("other")
    if other is not None:
        core = lodging + tickets + result["extraTotalRub"] - other["groupRub"]
        planned = other["groupRub"]
        if not planned and not card["expenseNotes"]["other"]:
            planned = max(1, card["budgetRub"] * 3 // 100)
        allowed = min(planned, max(0, card["budgetRub"] - core), other.get("capGroupRub", planned))
        other.update(groupRub=allowed, plannedGroupRub=planned, reducedRub=planned - allowed)
        if not card["expenseNotes"]["other"] and other.get("amountRub") == 0:
            other["assumption"] = "На необязательные покупки заложено 3% целевого бюджета до применения лимита."
        result["extraTotalRub"] = core - lodging - tickets + allowed
    known = lodging + tickets + result["extraTotalRub"]
    return {**result, "lodgingRub": lodging, "knownTotalRub": known, "targetRub": card["budgetRub"],
            "remainingRub": card["budgetRub"] - known, "ticketsRub": tickets, "ticketLines": places,
            "unpricedPlaces": [row["name"] for row in card["selectedPlaces"] if row["id"] not in priced]}


class Cancelled(Exception):
    pass


class Stand(ThreadingHTTPServer):
    def __init__(self, address):
        shared = read_destinations()
        local = json.loads(Path(__file__).with_name("stand-destinations.json").read_text(encoding="utf-8"))
        self.destinations = list(({row["id"]: row for row in [*local, *shared]}).values())
        self.destinations.sort(key=lambda row: row["id"] != "ru-moscow")
        self.token = secrets.token_urlsafe(24)
        self.jobs = {}
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.workers = {}
        self.model_lock = threading.Lock()
        super().__init__(address, Handler)

    def start_job(self, kind, data):
        with self.lock:
            if self.stopping.is_set() or (kind in self.workers and self.workers[kind].is_alive()):
                return None
            if kind == "select":
                if not os.getenv("GEOAPIFY_API_KEY"):
                    raise ValueError("Geoapify недоступен. Задай GEOAPIFY_API_KEY в Windows и перезапусти стенд.")
                card = card_input(data, self.destinations)
            else:
                source_id = data.get("selectionId")
                source = self.jobs.get(source_id) if isinstance(source_id, str) else None
                if not source or source["kind"] != "select" or "result" not in source:
                    raise ValueError("Сначала получи новую подборку.")
                card = budget_input(data, source["result"])
            if len(self.jobs) >= 24:
                expired = next(key for key, previous in self.jobs.items()
                               if previous["state"] != "running" and key != data.get("selectionId"))
                self.jobs.pop(expired)
            job_id = secrets.token_urlsafe(16)
            self.jobs[job_id] = {"kind": kind, "state": "running", "message": "Запускаем задачу"}
            self.workers[kind] = threading.Thread(target=self.work, args=(job_id, kind, card), name=f"card-{kind}")
            self.workers[kind].start()
            return job_id

    def work(self, job_id, kind, card):
        def progress(message):
            if self.stopping.is_set():
                raise Cancelled()
            with self.lock:
                self.jobs[job_id]["message"] = message

        def publish(result):
            with self.lock:
                self.jobs[job_id]["result"] = result

        try:
            if kind == "select":
                args = SimpleNamespace(model_lock=self.model_lock,
                                       cancelled=self.stopping.is_set, destinations=self.destinations)
                result = select(card, args, None, progress, publish)
            else:
                args = SimpleNamespace(verify_tariff=False, stand_budget=True)
                with self.model_lock:
                    progress("Считаем бюджет выбранного маршрута")
                    result = calculate(card, args, progress)
            if self.stopping.is_set():
                raise Cancelled()
            update = {"state": "done", "result": result}
        except Cancelled:
            update = {"state": "error", "message": "Стенд останавливается."}
        except InferenceError:
            logging.exception("DeepSeek inference failed")
            update = {"state": "error", "message": "Запрос к DeepSeek не прошёл. Подробности в окне запуска стенда."}
        except Exception:
            logging.exception("Card job failed")
            update = {"state": "error", "message": "Операция прервалась. Подробности есть в окне запуска стенда."}
        with self.lock:
            self.jobs[job_id].update(update)

    def stop(self):
        self.stopping.set()
        self.shutdown()


class Handler(BaseHTTPRequestHandler):
    def send_data(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError:
            pass

    def reply(self, status, value):
        self.send_data(status, json.dumps(value, ensure_ascii=False).encode(), "application/json")

    def local_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_GET(self):
        if not self.local_host():
            return self.reply(403, {"message": "Локальный адрес стенда не совпадает."})
        if self.path in FILES:
            name, mime = FILES[self.path]
            return self.send_data(200, (ASSETS / name).read_bytes(), mime)
        if self.path == "/api/config":
            return self.reply(200, {"destinations": self.server.destinations, "token": self.server.token})
        if self.path.startswith("/api/job/"):
            with self.server.lock:
                job = self.server.jobs.get(self.path.removeprefix("/api/job/"))
                result = job.copy() if job else None
            if result:
                return self.reply(200, result)
        return self.reply(404, {"message": "Результат не найден. Обнови подборку."})

    def do_POST(self):
        expected = self.server.token
        if not self.local_host() or not secrets.compare_digest(self.headers.get("X-Stand-Token", ""), expected):
            return self.reply(403, {"message": "Обнови страницу стенда."})
        if self.path == "/api/stop":
            self.reply(200, {"stopping": True})
            threading.Thread(target=self.server.stop, daemon=True).start()
            return
        kinds = {"/api/select": "select", "/api/budget": "budget"}
        if self.path not in kinds:
            return self.reply(404, {"message": "Действие не найдено."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 24_000:
                raise ValueError("Слишком большой или пустой запрос.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Ожидались данные карточки.")
            job = self.server.start_job(kinds[self.path], data)
        except ValueError as error:
            return self.reply(400, {"message": str(error)})
        if job is None:
            return self.reply(409, {"message": "Стенд уже выполняет задачу. Дождись результата."})
        self.reply(202, {"jobId": job})

    def log_message(self, format, *args):
        if not self.path.startswith("/api/job/"):
            super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766, help="Local stand HTTP port")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        if not request_api("/user/balance").get("is_available"):
            raise InferenceError("DeepSeek сообщает, что баланс API недоступен для генерации.")
        server = Stand(("127.0.0.1", args.port))
    except (InferenceError, OSError, ValueError) as error:
        parser.exit(1, f"Ошибка запуска стенда: {error}\n")

    try:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"TripFlow · {url}\nОстановка: кнопка на странице или Ctrl+C в этой консоли.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError) as error:
        print(f"Ошибка запуска стенда: {error}", flush=True)
        return 1
    finally:
        server.stopping.set()
        server.server_close()
        with server.lock:
            workers = tuple(server.workers.values())
        for worker in workers:
            if not worker.is_alive():
                continue
            print("Завершаем текущий шаг…", flush=True)
            try:
                worker.join()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

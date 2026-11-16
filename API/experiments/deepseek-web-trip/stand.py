"""Local TripFlow experiment with DeepSeek web search."""

import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
from secrets import token_urlsafe
from threading import Lock
import webbrowser

from deepseek import DeepSeekError, api_key
from trip import calculate, find_options, trip_input


WEB = Path(__file__).with_name("web")
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}


class Stand(ThreadingHTTPServer):
    def __init__(self, port):
        self.searches = OrderedDict()
        self.lock = Lock()
        super().__init__(("127.0.0.1", port), Handler)

    def search(self, data):
        trip = trip_input(data)
        results, errors = {}, {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {kind: pool.submit(find_options, trip, kind) for kind in ("hotels", "places")}
            for kind, job in jobs.items():
                try:
                    results[kind] = job.result()
                except DeepSeekError as error:
                    results[kind], errors[kind] = [], str(error)
        if len(errors) == len(jobs):
            raise DeepSeekError(next(iter(errors.values())))
        search_id = token_urlsafe(18)
        with self.lock:
            self.searches[search_id] = (trip, results)
            if len(self.searches) > 20:
                self.searches.popitem(last=False)
        return {"searchId": search_id, "trip": trip, **results, "errors": errors}

    def budget(self, data):
        search_id = data.get("searchId")
        with self.lock:
            saved = self.searches.get(search_id) if isinstance(search_id, str) else None
        if saved is None:
            raise ValueError("Подборка недоступна. Запусти поиск ещё раз.")
        trip, results = saved
        hotel = next((hotel for hotel in results["hotels"] if hotel["id"] == data.get("hotelId")), None)
        if hotel is None:
            raise ValueError("Выбери отель из подборки.")
        ids = data.get("placeIds")
        places = {place["id"]: place for place in results["places"]}
        if (not isinstance(ids, list) or any(not isinstance(key, str) or key not in places for key in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("Выбери достопримечательности из подборки.")
        return calculate(trip, hotel, [places[key] for key in ids])


class Handler(BaseHTTPRequestHandler):
    def trusted_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}",
                                            f"localhost:{self.server.server_port}"}

    def send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https:; "
                         "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
                         "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def reply(self, status, data):
        self.send(status, "application/json", json.dumps(data, ensure_ascii=False).encode())

    def do_GET(self):
        if not self.trusted_host():
            return self.reply(403, {"message": "Используй локальный адрес стенда."})
        if self.path in ASSETS:
            name, content_type = ASSETS[self.path]
            return self.send(200, content_type, (WEB / name).read_bytes())
        self.reply(404, {"message": "Страница не найдена."})

    def do_POST(self):
        if not self.trusted_host() or self.headers.get("Origin") != f"http://{self.headers.get('Host')}":
            return self.reply(403, {"message": "Открой локальную страницу стенда."})
        action = {"/api/search": self.server.search, "/api/budget": self.server.budget}.get(self.path)
        if not action:
            return self.reply(404, {"message": "Действие не найдено."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 16000 or self.headers.get_content_type() != "application/json":
                raise ValueError("Ожидалась карточка в формате JSON.")
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise ValueError("Непригодный JSON запроса.") from None
            if not isinstance(data, dict):
                raise ValueError("Ожидалась карточка поездки.")
            self.reply(200, action(data))
        except ValueError as error:
            self.reply(400, {"message": str(error)})
        except DeepSeekError as error:
            self.reply(502, {"message": str(error)})
        except Exception:
            logging.exception("Ошибка эксперимента")
            self.reply(500, {"message": "Эксперимент прервался. Подробности в консоли запуска."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        api_key()
        with Stand(args.port) as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"TripFlow · {url}\nОстановка по Ctrl+C", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (OSError, DeepSeekError) as error:
        parser.exit(1, f"Ошибка запуска: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

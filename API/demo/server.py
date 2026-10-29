"""Local TripFlow source explorer. Python 3.11+, standard library only."""
import argparse
import concurrent.futures
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT.parent / 'research/data-coverage-russia-2026-10-28'
spec = importlib.util.spec_from_file_location('reference', REFERENCE / 'offline_reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
CACHE = {}
LOCK = threading.Lock()


def load_environment():
    """Read only known settings, including newly saved Windows user variables."""
    names = ('GEOAPIFY_API_KEY', 'GEONAMES_USERNAME')
    try:
        import winreg
        for name in names:
            if os.environ.get(name):
                continue
            for hive, path in ((winreg.HKEY_CURRENT_USER, 'Environment'),
                               (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')):
                try:
                    with winreg.OpenKey(hive, path) as key:
                        value, _ = winreg.QueryValueEx(key, name)
                        if value:
                            os.environ[name] = str(value)
                            break
                except OSError:
                    pass
    except ImportError:
        pass


def request(url, params=None, post=False):
    encoded = urllib.parse.urlencode(params or {})
    req = urllib.request.Request(url if post else url + '?' + encoded,
        data=encoded.encode() if post else None,
        headers={'User-Agent': 'TripFlow-LocalDemo/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=16) as response:
        result = json.loads(response.read(6_000_000))
    if isinstance(result, dict) and ('error' in result or isinstance(result.get('status'), dict)):
        raise ValueError('Источник вернул ошибку API. Проверьте настройки и квоту.')
    return result


def cached(key, fn):
    with LOCK:
        item = CACHE.get(key)
        if item and time.monotonic() - item[0] < 600:
            return item[1]
    value = fn()
    with LOCK:
        if len(CACHE) > 150:
            CACHE.clear()
        CACHE[key] = (time.monotonic(), value)
    return value


def text(value):
    return html.unescape(re.sub(r'<[^>]*>', ' ', str(value or ''))).strip()


def cities(query):
    def fetch():
        username = os.environ.get('GEONAMES_USERNAME')
        if username:
            data = request('https://secure.geonames.org/searchJSON', {
                'name_startsWith': query, 'country': 'RU', 'featureClass': 'P',
                'maxRows': 8, 'lang': 'ru', 'style': 'FULL', 'username': username})
            return [dict(id=str(x['geonameId']), city=x.get('name'), region=x.get('adminName1'),
                         lat=float(x['lat']), lon=float(x['lng']),
                         timezone=x.get('timezone', {}).get('timeZoneId'), source='GeoNames')
                    for x in data.get('geonames', [])]
        key = os.environ.get('GEOAPIFY_API_KEY')
        if not key:
            raise ValueError('Нужна GEONAMES_USERNAME или GEOAPIFY_API_KEY в окружении Windows.')
        data = request('https://api.geoapify.com/v1/geocode/search', {
            'text': query, 'type': 'city', 'filter': 'countrycode:ru', 'lang': 'ru', 'limit': 8, 'apiKey': key})
        return [dict(id=x['properties']['place_id'], city=x['properties'].get('city') or x['properties'].get('name'),
                     region=x['properties'].get('state'), lat=x['properties']['lat'], lon=x['properties']['lon'],
                     timezone=x['properties'].get('timezone', {}).get('name'), source='Geoapify')
                for x in data.get('features', [])]
    return cached(('cities', query.casefold()), fetch)


def hotels(city):
    data = request('https://russhotels.ru/api/hotel/index', {'city_name': city['city'], 'limit': 8, 'offset': 0}, post=True)
    result = []
    for h in data:
        if reference.normalize(h.get('city', {}).get('name', '')) != reference.normalize(city['city']):
            continue
        try:
            lat, lon = float(h['geo_lat']), float(h['geo_lon'])
            distance = math.hypot((lat-city['lat'])*111, (lon-city['lon'])*111*math.cos(math.radians(city['lat'])))
            if distance > 60:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        rooms = []
        for room in h.get('rooms', []):
            amount = room.get('price_client')
            if amount is not None:
                rooms.append({'name': text(room.get('name')), 'placement': room.get('placement_type', {}).get('name'),
                              'priceRub': amount, 'updatedAt': room.get('updated_at')})
        result.append(dict(id=h['id'], name=text(h.get('name')), address=text(h.get('address')),
            description=text(h.get('hotel_description') or h.get('description_client'))[:1800],
            lat=lat, lon=lon, rooms=rooms[:8], checkIn=h.get('check_in'), checkOut=h.get('check_out'),
            updatedAt=h.get('last_modified') or h.get('updated_at'), source='Russhotels'))
    return result


def places(city):
    key = os.environ.get('GEOAPIFY_API_KEY')
    if not key:
        raise ValueError('Не задана GEOAPIFY_API_KEY.')
    data = request('https://api.geoapify.com/v2/places', {
        'categories': 'entertainment.museum,tourism.sights',
        'filter': f"circle:{city['lon']},{city['lat']},7000", 'limit': 12, 'lang': 'ru', 'apiKey': key})
    result = []
    for feature in data.get('features', []):
        p = feature['properties']
        if not p.get('name'):
            continue
        result.append(dict(id=p.get('place_id'), name=p['name'], address=p.get('formatted'), lat=p['lat'], lon=p['lon'],
            categories=p.get('categories', []), website=p.get('website'), openingHours=p.get('opening_hours'),
            description=text(p.get('description')), source='Geoapify / OpenStreetMap'))
    return result


def metadata(city):
    username = os.environ.get('GEONAMES_USERNAME')
    if not username:
        raise ValueError('Не задана GEONAMES_USERNAME. География выбранного города доступна отдельно.')
    data = request('https://secure.geonames.org/countryInfoJSON', {'country': 'RU', 'lang': 'ru', 'username': username})
    country = (data.get('geonames') or [{}])[0]
    zone = city.get('timezone')
    if not zone:
        z = request('https://secure.geonames.org/timezoneJSON', {'lat': city['lat'], 'lng': city['lon'], 'username': username})
        zone = z.get('timezoneId')
    return dict(country=country.get('countryName'), currency=country.get('currencyCode'),
                languages=country.get('languages'), timezone=zone, source='GeoNames')


def rates(city):
    rows = []
    for metric in reference.METRICS:
        value = reference.get_reference(metric, city['city'], city.get('region'), allow_country_fallback=True)
        if value:
            rows.append(value)
    return rows


def section(name, fn):
    start = time.monotonic()
    try:
        data = fn()
        return dict(source=name, status='ok', data=data, durationMs=round((time.monotonic()-start)*1000))
    except Exception as error:
        if isinstance(error, urllib.error.HTTPError):
            message = f'Источник вернул HTTP {error.code}.'
        elif isinstance(error, ValueError):
            message = str(error) if not isinstance(error, json.JSONDecodeError) else 'Некорректный ответ источника.'
        else:
            message = 'Источник временно недоступен или не ответил вовремя.'
        return dict(source=name, status='error', data=None, message=message,
                    durationMs=round((time.monotonic()-start)*1000))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log request URLs or credentials.

    def reply(self, status, data, content_type='application/json; charset=utf-8'):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in ('/', '/app.js', '/style.css'):
            filename = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[parsed.path]
            kind = {'/': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css'}[parsed.path]
            return self.reply(200, (ROOT / filename).read_bytes(), kind+'; charset=utf-8')
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == '/api/cities':
            query = params.get('q', [''])[0].strip()
            if not 2 <= len(query) <= 100:
                return self.reply(400, {'error': 'Введите от 2 до 100 символов.'})
            result = section('geocoding', lambda: cities(query))
            return self.reply(200 if result['status'] == 'ok' else 502, result)
        if parsed.path == '/api/explore':
            # Resolve against server-held search results; do not trust browser coordinates.
            try:
                query, city_id = params['q'][0], params['id'][0]
                if not 2 <= len(query) <= 100:
                    raise ValueError()
                city = next(x for x in cities(query) if x['id'] == city_id)
            except (KeyError, ValueError, StopIteration):
                return self.reply(400, {'error': 'Выберите город из подсказок.'})
            def fetch():
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    tasks = {name: pool.submit(section, source, lambda fn=fn: fn(city)) for name, source, fn in (
                        ('hotels', 'Russhotels', hotels), ('places', 'Geoapify', places),
                        ('metadata', 'GeoNames', metadata), ('rates', 'Росстат · локальная выгрузка', rates))}
                    return dict(city=city, blocks={name: task.result() for name, task in tasks.items()},
                                fetchedAt=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
            return self.reply(200, cached(('explore', city['id']), fetch))
        self.reply(404, {'error': 'Не найдено'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    load_environment()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'TripFlow demo: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

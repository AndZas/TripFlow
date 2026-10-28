"""Bounded HTTPS transport, baseline matching and conservative price semantics."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import http.client
import math
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent
KEYS = {'makcorps': 'MAKCORPS_API_KEY', 'skyscanner': 'SKYSCANNER_API_KEY',
        'dataestur': 'DATAESTUR_API_KEY'}
SAMPLES = ROOT.parent / 'data-source-survey/data/samples/20261015T150210175612Z'
CITIES = {
    'Paris': ('fr', 48.8566, 2.3522), 'Moscow': ('ru', 55.7558, 37.6173),
    'Istanbul': ('tr', 41.0082, 28.9784), 'Suzdal': ('ru', 56.4197, 40.4495),
    'Madrid': ('es', 40.4168, -3.7038), 'Barcelona': ('es', 41.3874, 2.1686),
    'TripFlowNonexistentCityZXQ': (None, None, None),
}
SKY = 'https://partners.api.skyscanner.net'
MAK = 'https://api.makcorps.com'
DATA = 'https://www.dataestur.es'
DATA_PATH = '/API-SEGITTUR-v2/PRECIOS_ALOJAMIENTOS_HOTELEROS_DL'


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def obj(x):
    return x if isinstance(x, dict) else {}


def seq(x):
    return x if isinstance(x, list) else []


def text(x):
    return x if isinstance(x, str) else None


def number(x):
    if isinstance(x, bool):
        return None
    try:
        d = Decimal(str(x))
        return d if d.is_finite() and d >= 0 else None
    except (ValueError, InvalidOperation):
        return None


def money(x):
    """Parse only unambiguous ASCII amounts; never guess a comma decimal."""
    if isinstance(x, str):
        x = x.strip()
        x = re.sub(r'^(?:USD|EUR|GBP|RUB|[$€£])\s*', '', x)
        if re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', x):
            x = x.replace(',', '')
        if not re.fullmatch(r'\d+(?:\.\d+)?', x):
            return None
    n = number(x)
    return str(n) if n is not None else None


def clean_url(value):
    if not isinstance(value, str):
        return None
    try:
        p = parse.urlsplit(value)
        if p.scheme == 'https' and p.hostname and not p.username and not p.password:
            return parse.urlunsplit(('https', p.netloc, p.path, '', ''))
    except ValueError:
        pass
    return None


def sanitize(value):
    """Final recursive secret scrub, in addition to field allowlists."""
    secrets = [os.environ.get(k, '') for k in (*KEYS.values(), 'MAKCORPS_FREE_JWT')]
    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items()
                if not re.search(r'api.?key|authorization|token|password|email|telephone', str(k), re.I)}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                for variant in (secret, parse.quote(secret, safe=''), parse.quote_plus(secret)):
                    value = value.replace(variant, '[REDACTED]')
        value = re.sub(r'https?://[^\s<>"\']+', lambda m: clean_url(m[0]) or '[URL]', value)
        value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', value)
        return value[:1000]
    return value


def point(value):
    value = obj(value)
    try:
        lat = float(value.get('latitude', value.get('lat')))
        lon = float(value.get('longitude', value.get('lon')))
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return [lat, lon]
    except (TypeError, ValueError):
        pass
    return None


def distance(a, b):
    a1, a2 = map(math.radians, (a[0], b[0]))
    dp, dl = a2-a1, math.radians(b[1]-a[1])
    return 12742000 * math.asin(min(1, math.sqrt(math.sin(dp/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(dl/2)**2)))


def norm_name(x):
    return ' '.join(re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', x or '').casefold()).split())


def baseline():
    out = []
    for city in ('Paris', 'Moscow', 'Istanbul', 'Suzdal'):
        path = SAMPLES / f'geoapify_{city.lower()}_hotels.json'
        status, hotels = 'missing_sample', []
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
                for h in seq(data.get('normalized')):
                    h = obj(h)
                    hotels.append({'name': text(h.get('name')), 'geoapify_id': h.get('external_id'),
                                   'coordinates': point(h), 'country': h.get('country_code'), 'city': city})
                status = 'available'
            except (OSError, ValueError, TypeError):
                status = 'invalid_sample'
        out.append({'city': city, 'status': status, 'hotels': hotels})
    return out


def match_hotel(item, refs):
    candidates = []
    for r in refs:
        if r['city'] != item['city'] or not r.get('name'):
            continue
        if norm_name(r['name']) != norm_name(item.get('name')):
            continue
        if not item.get('coordinates') or not r.get('coordinates'):
            candidates.append((r, None))
        elif distance(item['coordinates'], r['coordinates']) <= 150:
            candidates.append((r, round(distance(item['coordinates'], r['coordinates']))))
    if len(candidates) == 1 and candidates[0][1] is not None:
        r, d = candidates[0]
        return {'confidence': 'high_confidence', 'geoapify_id': r['geoapify_id'], 'distance_m': d}
    return {'confidence': 'ambiguous' if candidates else 'no_match', 'geoapify_id': None, 'distance_m': None}


def observation(provider, city, scope):
    return {'provider': provider, 'provider_id': None, 'name': None, 'city': city,
            'country': CITIES.get(city, (None,))[0], 'scope': scope, 'coordinates': None,
            'amount': None, 'currency': None, 'currency_evidence': None,
            'price_basis_evidence': None,
            'period': 'unknown', 'occupancy_basis': 'unknown', 'aggregation': None,
            'date_start': None, 'date_end': None, 'date_context': 'unknown',
            'taxes': 'unknown', 'offers': [], 'offer_count': 0, 'priced_offer_count': 0,
            'min': None, 'median': None, 'max': None, 'retrieved_at': utcnow(),
            'source_updated_at': None, 'freshness': 'unknown', 'source_url': None,
            'match': {'confidence': 'no_match', 'geoapify_id': None, 'distance_m': None},
            'amount_rub': None, 'fx_date': None, 'fx_rate': None,
            'assumptions': [], 'issues': [], 'usable': False}


def finish(item):
    if item['amount'] is None:
        item['issues'].append('missing_or_invalid_amount')
    if not item['currency']:
        item['issues'].append('currency_unknown')
    if item['period'] == 'unknown' or item['occupancy_basis'] == 'unknown':
        item['issues'].append('price_basis_unknown')
    if item['scope'] == 'hotel' and item['match']['confidence'] not in ('exact', 'high_confidence'):
        item['issues'].append('hotel_match_unconfirmed')
    if item['date_context'] == 'unknown':
        item['issues'].append('price_dates_unknown')
    if item['date_end']:
        try:
            if date.fromisoformat(item['date_end']) < datetime.now(timezone.utc).date():
                item['issues'].append('expired')
        except ValueError:
            item['issues'].append('invalid_dates')
    item['issues'] = sorted(set(item['issues']))
    item['usable'] = not item['issues']
    # No inferred FX and no division by travellers. Unknown occupancy stays unknown.
    if item['currency'] == 'RUB' and item['usable']:
        item['amount_rub'], item['fx_rate'] = item['amount'], '1'
    return item


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint_allowed(provider, origin, path, method):
    if provider == 'makcorps' and origin == MAK and method == 'GET':
        return path in ('/account', '/mapping', '/city', '/hotel') or bool(re.fullmatch(r'/free/[A-Za-z0-9_-]+', path))
    if provider == 'skyscanner' and origin == SKY:
        return (method == 'POST' and path in ('/apiservices/v3/autosuggest/hotels', '/apiservices/v1/hotels/indicative/search')) or (method == 'GET' and (path in ('/apiservices/v3/culture/currencies', '/apiservices/v3/culture/locales') or bool(re.fullmatch(r'/apiservices/v3/culture/markets/[a-z]{2}-[A-Z]{2}', path))))
    return provider == 'dataestur' and origin == DATA and path == DATA_PATH and method == 'GET'


class Client:
    def __init__(self, max_requests, timeout=20, delay=1, opener=None):
        self.max_requests, self.timeout, self.delay = max_requests, timeout, delay
        self.opener = opener or request.build_opener(NoRedirect())
        self.records, self.blocked = [], set()
        self.last_call = None

    @property
    def remaining(self):
        return self.max_requests - len(self.records)

    def call(self, provider, origin, path, params=None, headers=None, body=None):
        method = 'POST' if body is not None else 'GET'
        if not endpoint_allowed(provider, origin, path, method):
            raise ValueError('endpoint_not_allowlisted')
        if provider in self.blocked or not self.remaining:
            return {'status': 'skipped_provider_stopped' if provider in self.blocked else 'skipped_request_cap', 'data': None}
        if self.last_call is not None:
            time.sleep(max(0, self.delay - (time.monotonic()-self.last_call)))
        self.last_call = time.monotonic()
        record = {'provider': provider, 'endpoint': path, 'method': method,
                  'requested_at': utcnow(), 'http_status': None, 'latency_ms': None, 'status': 'pending'}
        self.records.append(record)
        url = origin + path + ('?' + parse.urlencode(params) if params else '')
        hdr = {'Accept': 'application/json', 'User-Agent': 'TripFlow-HotelPriceExperiment/1.0', **(headers or {})}
        raw = None
        try:
            payload = json.dumps(body).encode() if body is not None else None
            if payload is not None:
                hdr['Content-Type'] = 'application/json'
            req = request.Request(url, data=payload, headers=hdr, method=method)
            with self.opener.open(req, timeout=self.timeout) as response:
                record['http_status'] = response.status
                raw = response.read(2_000_001)
                content_type = response.headers.get('Content-Type', '')
            if len(raw) > 2_000_000:
                record['status'] = 'response_too_large'
            elif 200 <= record['http_status'] < 300:
                record['status'] = 'ok'
            else:
                record['status'] = 'http_error'
        except error.HTTPError as exc:
            record['http_status'], record['status'] = exc.code, 'http_error'
            exc.close()
        except (OSError, ValueError, http.client.HTTPException):
            record['status'] = 'network_error'
        finally:
            record['latency_ms'] = round((time.monotonic()-self.last_call)*1000)
        if record['status'] != 'ok':
            self.blocked.add(provider)  # Includes 401/403/429; never retry, even transient errors.
            return {**record, 'data': None}
        if provider == 'dataestur' and raw is not None:
            return {**record, 'data': raw, 'content_type': content_type}
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError, TypeError):
            record['status'] = 'invalid_json'
            self.blocked.add(provider)
            data = None
        return {**record, 'data': data}


def metrics(items):
    n = len(items)
    flags = {
        'usable': lambda x: x['usable'],
        'reliable_hotel_match': lambda x: x['scope'] == 'hotel' and x['match']['confidence'] in ('exact', 'high_confidence'),
        'known_basis': lambda x: x['period'] != 'unknown' and x['occupancy_basis'] != 'unknown',
        'known_currency': lambda x: bool(x['currency']),
        'normalized_rub': lambda x: x['amount_rub'] is not None,
        'empty_price': lambda x: x['amount'] is None,
        'expired': lambda x: 'expired' in x['issues'],
        'ambiguous_match': lambda x: x['match']['confidence'] == 'ambiguous',
        'unusable': lambda x: not x['usable'],
    }
    return {k: {'count': sum(bool(f(x)) for x in items), 'denominator': n,
                'fraction': sum(bool(f(x)) for x in items)/n if n else None} for k, f in flags.items()}

"""Official read-only API scenarios. All gates default to closed."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
import re
from statistics import median

from hotel_price_core import (CITIES, DATA, DATA_PATH, KEYS, MAK, SKY, clean_url,
                              distance, finish, match_hotel, money, norm_name,
                              number, obj, observation, point, seq, text)
import os


def mak_offers(value):
    """Read only documented numbered vendor/price/tax fields."""
    rows = []
    if isinstance(value, list):
        for child in value:
            rows.extend(mak_offers(child))
    elif isinstance(value, dict):
        for i in range(1, 31):
            if f'vendor{i}' in value or f'price{i}' in value:
                rows.append({'vendor': text(value.get(f'vendor{i}')), 'amount': money(value.get(f'price{i}')),
                             'tax_amount': money(value.get(f'tax{i}')), 'source_url': None})
    return rows


def normalize_mak(data, city, refs, scenario, cfg):
    result = []
    if scenario['kind'] == 'hotel':
        rows = [{'hotelId': scenario['hotel_id'], 'comparison': obj(data).get('comparison')}]
    else:
        rows = seq(data)
    for raw in rows[:30]:
        # /free returns pairs [identity, [vendor quotes]], /city flat objects.
        identity = obj(raw[0]) if isinstance(raw, list) and raw else obj(raw)
        offers = mak_offers(raw[1] if isinstance(raw, list) and len(raw) > 1 else identity.get('comparison', identity))
        item = observation('makcorps', city, 'hotel')
        item.update(provider_id=str(identity.get('hotelId')) if identity.get('hotelId') is not None else None,
                    name=text(identity.get('hotelName', identity.get('name'))),
                    coordinates=point(identity.get('geocode')))
        if scenario['kind'] == 'hotel':
            # Use only identity/geography established by the earlier mapping scenario.
            item['name'], item['coordinates'] = scenario.get('name'), scenario.get('coordinates')
        item['offers'], item['offer_count'] = offers, len(offers)
        amounts = [Decimal(o['amount']) for o in offers if o['amount'] is not None]
        item['priced_offer_count'] = len(amounts)
        if amounts:
            item.update(amount=str(min(amounts)), min=str(min(amounts)), median=str(median(amounts)), max=str(max(amounts)))
        item['aggregation'] = 'cheapest_returned_offer'
        if scenario['kind'] != 'free':
            item.update(currency=cfg['currency'], currency_evidence='request_cur',
                        date_start=cfg['checkin'], date_end=cfg['checkout'], date_context='explicit_synthetic_test_dates')
        # The old /free docs do not establish currency, stay length or room/person basis.
        # The current dated docs also do not explicitly define the price's denominator.
        basis = obj(cfg.get('verified_price_basis')).get(scenario['kind'], {})
        if basis.get('evidence'):
            item['period'] = basis.get('period', 'unknown')
            item['occupancy_basis'] = basis.get('occupancy_basis', 'unknown')
            item['price_basis_evidence'] = basis['evidence']
            if scenario['kind'] == 'free' and basis.get('currency'):
                item['currency'], item['currency_evidence'] = basis['currency'], 'owner_verified_documentation'
        item['taxes'] = 'separately_reported' if any(o['tax_amount'] is not None for o in offers) else 'unknown'
        if scenario['kind'] == 'city':
            item['taxes'] = 'included'  # /city request explicitly sends tax=true.
        item['match'] = match_hotel(item, refs)
        result.append(finish(item))
    return result


def price_value(value):
    value = obj(value)
    n = number(value.get('amount'))
    divisor = {'PRICE_UNIT_WHOLE': 1, 'PRICE_UNIT_CENTI': 100,
               'PRICE_UNIT_MILLI': 1000, 'PRICE_UNIT_MICRO': 1000000}.get(value.get('unit'))
    return str(n / divisor) if n is not None and divisor else None


def normalize_sky(data, city, entity_id, cfg):
    result = []
    prices = obj(obj(data).get('resultSet')).get('prices')
    if not isinstance(prices, dict):
        return result
    for key, entry in list(prices.items())[:100]:
        for p in seq(obj(entry).get('prices'))[:10]:
            p = obj(p)
            item = observation('skyscanner', city, 'city')
            aggregate = p.get('type', '')
            aggregation = {'PRICE_AGGREGATION_TYPE_CHEAPEST': 'cheapest',
                           'PRICE_AGGREGATION_TYPE_AVERAGE': 'average',
                           'PRICE_AGGREGATION_TYPE_MEDIAN': 'median'}.get(aggregate)
            item.update(provider_id=entity_id, name=city, amount=price_value(p.get('price')),
                        currency=cfg['currency'], currency_evidence='request_currency',
                        period='per_night', aggregation=aggregation,
                        date_start=cfg['date_start'], date_end=cfg['date_end'],
                        date_context='explicit_synthetic_test_range')
            # Documentation says daily quote, but does not establish room/person denominator.
            basis = obj(cfg.get('verified_price_basis'))
            if basis.get('evidence'):
                item['occupancy_basis'] = basis.get('occupancy_basis', 'unknown')
                item['price_basis_evidence'] = basis['evidence']
            item['documented_freshness'] = 'daily_file_aggregating_searches_from_previous_seven_days'
            item['result_key'] = str(key)
            if aggregation is None:
                item['issues'].append('unknown_aggregation')
            if cfg.get('grouping', 'aggregated') != 'aggregated':
                # Composite result keys are undocumented. Do not guess the day/month.
                item['issues'].append('individual_result_period_unresolved')
            result.append(finish(item))
    return result


def normalize_dataestur(blob, cfg):
    """CSV schema is inspected first; money mapping requires named documented columns."""
    decoded = blob.decode('utf-8-sig')
    if decoded.lstrip().lower().startswith(('<!doctype', '<html')):
        raise ValueError('unexpected_html')
    reader = csv.DictReader(io.StringIO(decoded), delimiter=cfg.get('delimiter', ';'))
    headers = reader.fieldnames or []
    if len(headers) > 100:
        raise ValueError('csv_too_wide')
    mapping = obj(cfg.get('columns'))
    observations = []
    row_count = 0
    for row in reader:
        row_count += 1
        if row_count > 2000:
            raise ValueError('csv_too_many_rows')
        if not mapping.get('amount') or mapping['amount'] not in headers:
            continue
        item = observation('dataestur', cfg['province'], 'region')
        item.update(name=cfg['province'], country='es', aggregation='average',
                    amount=money(row.get(mapping['amount'])),
                    currency=cfg.get('verified_currency'),
                    period=cfg.get('verified_period', 'unknown'),
                    occupancy_basis=cfg.get('verified_occupancy_basis', 'unknown'),
                    date_start=cfg['period_start'], date_end=cfg['period_end'],
                    date_context='historical_statistical_period')
        if not cfg.get('semantics_evidence'):
            item.update(currency=None, period='unknown', occupancy_basis='unknown')
        item['source_url'] = DATA + DATA_PATH
        observations.append(finish(item))
    return observations, {'columns': headers, 'row_count': row_count}


def gate(provider, cfg):
    if not cfg.get('enabled'):
        return 'skipped_disabled'
    if not os.environ.get(KEYS[provider]):
        return 'skipped_missing_config'
    review = obj(cfg.get('review'))
    if review.get('free_no_billing') is not True or not review.get('cost_evidence'):
        return 'skipped_cost_not_verified'
    if review.get('research_storage_allowed') is not True or not review.get('terms_evidence'):
        return 'skipped_terms_unclear'
    if provider == 'skyscanner' and (review.get('access_approved') is not True or review.get('price_only_display_allowed') is not True):
        return 'skipped_terms_unclear'
    if cfg.get('environment') != 'production':
        return 'skipped_environment_not_supported'
    return 'ready'


def record_result(response, observations=None, **extra):
    return {'status': response['status'], 'http_status': response.get('http_status'),
            'latency_ms': response.get('latency_ms'), 'observations': observations or [], **extra}


def remaining_credits(data):
    data = obj(data)
    n = number(data.get('remainingLimit'))
    limit, used = number(data.get('requestLimit')), number(data.get('requestUsed'))
    if n is None or limit is None or used is None or n != n.to_integral() or limit != used+n:
        return None
    return int(n)


def run_mak(client, cfg, refs, credit_budget):
    records, key = [], os.environ[KEYS['makcorps']]
    review = obj(cfg.get('review'))
    if review.get('account_check_free') is not True or not review.get('account_cost_evidence'):
        return [{'status': 'skipped_cost_not_verified', 'reason': 'account_check_cost_unknown', 'observations': []}]
    costs = obj(cfg.get('credit_costs'))
    scenarios = cfg.get('scenarios', [])
    spent = 0
    mapping_cache = {}
    city_cache = {}
    for scenario in scenarios:
        kind, city = scenario['kind'], scenario['city']
        cost = costs.get(kind)
        if type(cost) is not int or cost < 0:
            records.append({'status': 'skipped_cost_not_verified', 'scenario': kind, 'city': city, 'observations': []})
            break
        if kind == 'free' and not (review.get('legacy_free_jwt_confirmed') is True and os.environ.get('MAKCORPS_FREE_JWT')):
            records.append({'status': 'skipped_missing_config', 'scenario': kind, 'city': city,
                            'reason': 'legacy_free_requires_separate_verified_jwt', 'observations': []})
            continue
        if client.remaining < 3 or spent + cost > credit_budget:
            records.append({'status': 'skipped_budget', 'scenario': kind, 'city': city, 'observations': []})
            break
        if kind == 'hotel':
            identity = mapping_cache.get(scenario['mapping_name'])
            if identity is None:
                records.append({'status': 'skipped_unresolved_hotel_id', 'city': city, 'observations': []})
                continue
            scenario = {**scenario, **identity}
        if kind == 'city' and not scenario.get('city_id'):
            city_id = city_cache.get(scenario.get('mapping_name'))
            if not city_id:
                records.append({'status': 'skipped_unresolved_city_id', 'city': city, 'observations': []})
                continue
            scenario = {**scenario, 'city_id': city_id}
        before = client.call('makcorps', MAK, '/account', {'api_key': key})
        credits = remaining_credits(before.get('data'))
        records.append(record_result(before, scenario='account_before', credits=credits))
        # Both quota and full configured budget must leave at least one credit untouched.
        if credits is None or credit_budget >= credits or credits-cost < 1:
            records.append({'status': 'skipped_quota_not_verified', 'observations': []})
            break
        params = {'api_key': key}
        headers = None
        if kind == 'mapping':
            endpoint, params['name'] = '/mapping', scenario['name']
        elif kind == 'free':
            endpoint, params = '/free/' + city.lower(), None
            headers = {'Authorization': 'JWT ' + os.environ['MAKCORPS_FREE_JWT']}
        else:
            endpoint = '/' + kind
            params.update(cur=cfg['currency'], rooms=cfg['rooms'], adults=cfg['adults'],
                          checkin=cfg['checkin'], checkout=cfg['checkout'])
            if kind == 'city':
                params.update(cityid=scenario['city_id'], pagination=0, tax='true')
            else:
                params['hotelid'] = scenario['hotel_id']
        response = client.call('makcorps', MAK, endpoint, params, headers)
        spent += cost  # Treat even failed calls as charged; never recover/retry the budget.
        after = client.call('makcorps', MAK, '/account', {'api_key': key}) if 'makcorps' not in client.blocked else {'status': 'skipped_provider_stopped', 'data': None}
        after_credits = remaining_credits(after.get('data'))
        records.append(record_result(after, scenario='account_after', credits=after_credits))
        items = []
        extra = {}
        if response['status'] == 'ok' and kind == 'mapping':
            matches = []
            city_matches = []
            for raw in seq(response['data'])[:30]:
                raw, details = obj(raw), obj(obj(raw).get('details'))
                coords = text(raw.get('coords')) or ''
                pair = coords.split(',')
                pt = point({'lat': pair[0], 'lon': pair[1]}) if len(pair) == 2 else None
                candidate = {'name': text(details.get('name')), 'coordinates': pt, 'city': city}
                match = match_hotel(candidate, refs)
                if raw.get('type') == 'HOTEL' and match['confidence'] == 'high_confidence' and raw.get('document_id'):
                    matches.append({**candidate, 'hotel_id': str(raw['document_id']), 'match': match})
                center = CITIES[city]
                if raw.get('type') == 'GEO' and norm_name(details.get('name')) == norm_name(city) and pt and center[1] is not None and distance(pt, center[1:]) <= 30_000 and raw.get('document_id'):
                    city_matches.append(str(raw['document_id']))
            if len(matches) == 1:
                mapping_cache[scenario['name']] = matches[0]
            if len(set(city_matches)) == 1:
                city_cache[scenario['name']] = city_matches[0]
            extra = {'mapping_candidates': len(seq(response['data'])), 'reliable_mapping': matches if len(matches) == 1 else [],
                     'resolved_city_id': city_cache.get(scenario['name'])}
        elif response['status'] == 'ok':
            items = normalize_mak(response['data'], city, refs, scenario, cfg)
        records.append(record_result(response, items, city=city, scenario=kind, credits_before=credits,
                                     credits_after=after_credits, expected_credit_cost=cost,
                                     actual_credit_cost=credits-after_credits if after_credits is not None else None, **extra))
        if after_credits is None or credits-after_credits != cost:
            records.append({'status': 'stopped_credit_accounting_unclear', 'observations': []})
            break
    return records


def resolve_sky_city(data, city):
    expected = CITIES[city]
    matches = []
    for place in seq(obj(data).get('places')):
        place = obj(place)
        p = point(place.get('location'))
        if place.get('type') == 'PLACE_TYPE_CITY' and norm_name(place.get('name')) == norm_name(city) and p and expected[1] is not None and distance(p, expected[1:]) <= 30_000 and place.get('entityId'):
            matches.append(str(place['entityId']))
    return matches[0] if len(set(matches)) == 1 else None


def run_sky(client, cfg):
    headers, records = {'x-api-key': os.environ[KEYS['skyscanner']]}, []
    # Verify market, locale and currency using the documented Culture API.
    for resource, field, expected in (('currencies', 'currencies', cfg['currency']),
                                     ('locales', 'locales', cfg['locale']),
                                     ('markets/' + cfg['locale'], 'markets', cfg['market'])):
        response = client.call('skyscanner', SKY, '/apiservices/v3/culture/' + resource, headers=headers)
        codes = [obj(x).get('code') for x in seq(obj(response.get('data')).get(field))]
        supported = expected in codes
        records.append(record_result(response, scenario='culture_' + field, requested_code=expected, supported=supported,
                                     rub_listed=('RUB' in codes) if field == 'currencies' else None))
        if response['status'] != 'ok' or not supported:
            return records
    for city in cfg['cities']:
        if client.remaining < 2:
            records.append({'status': 'skipped_budget', 'city': city, 'observations': []})
            break
        response = client.call('skyscanner', SKY, '/apiservices/v3/autosuggest/hotels', headers=headers,
                               body={'query': {'market': cfg['market'], 'locale': cfg['locale'], 'searchTerm': city,
                                               'includedEntityTypes': ['PLACE_TYPE_CITY']}, 'limit': 5})
        entity = resolve_sky_city(response.get('data'), city)
        records.append(record_result(response, scenario='autosuggest', city=city, resolved_entity_id=entity,
                                     candidate_count=len(seq(obj(response.get('data')).get('places')))))
        if response['status'] != 'ok':
            break
        if entity is None:
            records.append({'status': 'empty_or_ambiguous_destination', 'city': city, 'observations': []})
            continue
        def parts(value):
            d = date.fromisoformat(value)
            return {'year': d.year, 'month': d.month, 'day': d.day}
        query = {'market': cfg['market'], 'locale': cfg['locale'], 'currency': cfg['currency'],
                 'destinationEntityIds': [entity],
                 'travelDate': {'dateRange': {'startDate': parts(cfg['date_start']), 'endDate': parts(cfg['date_end'])}},
                 'dateTimeGroupingType': 'DATE_TIME_GROUPING_TYPE_' + cfg['grouping'].upper()}
        if cfg.get('filter'):
            query['filter'] = cfg['filter']
        response = client.call('skyscanner', SKY, '/apiservices/v1/hotels/indicative/search', headers=headers, body={'query': query})
        items = normalize_sky(response.get('data'), city, entity, cfg) if response['status'] == 'ok' else []
        records.append(record_result(response, items, city=city, scenario='indicative', entity_id=entity,
                                     date_start=cfg['date_start'], date_end=cfg['date_end'], grouping=cfg['grouping']))
        if response['status'] != 'ok':
            break
    return records


def run_dataestur(client, cfg):
    start, end = date.fromisoformat(cfg['period_start']), date.fromisoformat(cfg['period_end'])
    params = {'desde (año)': start.year, 'desde (mes)': start.month,
              'hasta (año)': end.year, 'hasta (mes)': end.month, 'Provincia': cfg['province']}
    response = client.call('dataestur', DATA, DATA_PATH, params,
                           {'Ocp-Apim-Subscription-Key': os.environ[KEYS['dataestur']]})
    items, metadata = [], {}
    if response['status'] == 'ok':
        try:
            items, metadata = normalize_dataestur(response['data'], cfg)
        except (UnicodeError, ValueError, csv.Error):
            response['status'] = 'unexpected_csv_schema'
    return [record_result(response, items, scenario='province_average_csv', **metadata)]

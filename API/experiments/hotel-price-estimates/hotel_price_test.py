"""Isolated, bounded experiment for hotel and destination price estimates (stdlib only)."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys

from hotel_price_core import (CITIES, KEYS, ROOT, Client, baseline, metrics, obj,
                              sanitize, utcnow)
from hotel_price_providers import gate, run_dataestur, run_mak, run_sky


def validate_config(config):
    """Validate every enabled scenario before constructing an HTTP client."""
    if not isinstance(config, dict):
        raise ValueError('configuration_must_be_object')
    for provider in KEYS:
        cfg = config.get(provider, {})
        if not isinstance(cfg, dict) or type(cfg.get('enabled', False)) is not bool:
            raise ValueError('invalid_provider_configuration')
        if not cfg.get('enabled'):
            continue
        if cfg.get('environment') != 'production':
            raise ValueError('only_documented_production_endpoints_supported_no_sandbox')
        if not isinstance(cfg.get('review'), dict):
            raise ValueError('review_required')
        bases = cfg.get('verified_price_basis', {})
        if not isinstance(bases, dict):
            raise ValueError('invalid_price_basis')
        for basis in (bases.values() if provider == 'makcorps' else [bases]):
            if not isinstance(basis, dict) or basis.get('period', 'unknown') not in ('unknown', 'per_night', 'per_stay') or basis.get('occupancy_basis', 'unknown') not in ('unknown', 'per_room', 'per_person'):
                raise ValueError('invalid_price_basis_semantics')
            if basis.get('currency') and not re.fullmatch('[A-Z]{3}', basis['currency']):
                raise ValueError('invalid_basis_currency')
        if provider == 'makcorps':
            if not re.fullmatch('[A-Z]{3}', cfg.get('currency', '')):
                raise ValueError('makcorps_currency_required')
            for k in ('rooms', 'adults'):
                if type(cfg.get(k)) is not int or not 1 <= cfg[k] <= 5:
                    raise ValueError('makcorps_occupancy_out_of_range')
            checkin, checkout = date.fromisoformat(cfg['checkin']), date.fromisoformat(cfg['checkout'])
            if checkin < datetime.now(timezone.utc).date() or not 1 <= (checkout-checkin).days <= 30:
                raise ValueError('makcorps_dates_must_be_future_1_to_30_nights')
            scenarios = cfg.get('scenarios')
            if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 6:
                raise ValueError('makcorps_requires_1_to_6_scenarios')
            if sum(s.get('kind') == 'hotel' for s in scenarios) > 2:
                raise ValueError('max_two_hotel_specific_calls')
            for scenario in scenarios:
                if scenario.get('kind') not in ('free', 'mapping', 'city', 'hotel') or scenario.get('city') not in CITIES:
                    raise ValueError('invalid_makcorps_scenario')
                if scenario['kind'] == 'city' and scenario.get('city_id') and not re.fullmatch(r'\d+', str(scenario['city_id'])):
                    raise ValueError('city_id_must_come_from_documented_mapping')
                if scenario['kind'] == 'city' and scenario.get('city_id') and not scenario.get('id_evidence'):
                    raise ValueError('city_id_evidence_required')
                if scenario['kind'] == 'city' and not scenario.get('city_id') and not scenario.get('mapping_name'):
                    raise ValueError('city_requires_previous_mapping_or_documented_id')
                if scenario['kind'] == 'mapping' and not isinstance(scenario.get('name'), str):
                    raise ValueError('mapping_name_required')
                if scenario['kind'] == 'hotel' and not isinstance(scenario.get('mapping_name'), str):
                    raise ValueError('hotel_requires_previous_mapping_name')
        elif provider == 'skyscanner':
            if not re.fullmatch('[A-Z]{2}', cfg.get('market', '')) or not re.fullmatch('[a-z]{2}-[A-Z]{2}', cfg.get('locale', '')) or not re.fullmatch('[A-Z]{3}', cfg.get('currency', '')):
                raise ValueError('invalid_skyscanner_localisation')
            start, end = date.fromisoformat(cfg['date_start']), date.fromisoformat(cfg['date_end'])
            today = datetime.now(timezone.utc).date()
            if start < today or end < start or end > today+timedelta(days=364):
                raise ValueError('skyscanner_dates_must_be_within_next_12_months')
            if cfg.get('grouping') not in ('aggregated', 'by_date', 'by_month'):
                raise ValueError('invalid_skyscanner_grouping')
            cities = cfg.get('cities')
            if not isinstance(cities, list) or not 1 <= len(cities) <= 7 or any(c not in CITIES for c in cities):
                raise ValueError('invalid_skyscanner_cities')
            filters = cfg.get('filter', {})
            if not isinstance(filters, dict) or set(filters) - {'starsFilter', 'accommodationTypeFilter', 'chainIdFilter', 'hotelGroupFilter'}:
                raise ValueError('invalid_skyscanner_filter')
            filter_count = 1
            for f in filters.values():
                if not isinstance(f, dict) or set(f) != {'values'} or not isinstance(f['values'], list) or not 1 <= len(f['values']) <= 5 or any(not isinstance(v, str) or not re.fullmatch('[A-Za-z0-9_]+', v) for v in f['values']):
                    raise ValueError('invalid_skyscanner_filter_values')
                filter_count *= len(f['values'])
            if filters and not cfg.get('filter_evidence'):
                raise ValueError('filter_enum_documentation_evidence_required')
            if ((end-start).days+1)*filter_count > 5000:
                raise ValueError('skyscanner_query_exceeds_5000_price_constraint')
        else:
            start, end = date.fromisoformat(cfg['period_start']), date.fromisoformat(cfg['period_end'])
            if end < start or (end-start).days > 62 or end >= datetime.now(timezone.utc).date():
                raise ValueError('dataestur_requires_small_historical_period')
            if cfg.get('province') not in ('Madrid', 'Barcelona'):
                raise ValueError('dataestur_test_province_must_be_Madrid_or_Barcelona')
            if cfg.get('delimiter', ';') not in (';', ',','\t'):
                raise ValueError('invalid_csv_delimiter')
    return config


def init_config(path):
    config = json.loads((ROOT/'config.example.json').read_text(encoding='utf-8-sig'))
    start = datetime.now(timezone.utc).date()+timedelta(days=30)
    config['makcorps'].update(checkin=start.isoformat(), checkout=(start+timedelta(days=2)).isoformat())
    config['skyscanner'].update(date_start=start.isoformat(), date_end=(start+timedelta(days=29)).isoformat())
    previous_month_end = datetime.now(timezone.utc).date().replace(day=1)-timedelta(days=1)
    config['dataestur'].update(period_start=previous_month_end.replace(day=1).isoformat(), period_end=previous_month_end.isoformat())
    with path.open('x', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def md(value):
    return str(value if value is not None else '—').replace('|', '\\|').replace('\n', ' ')


def render(result):
    lines = [f"# Hotel price experiment {result['run_id']}", '',
             f"Режим: {result['mode']}. HTTP-запросов: {len(result['requests'])}. Статус: {result['status']}.",
             '', '| Источник | Статус | Наблюдений | Пригодных | Решение |', '|---|---|---:|---:|---|']
    for p in result['providers']:
        lines.append(f"| {p['provider']} | {p['status']} | {len(p['observations'])} | {sum(x['usable'] for x in p['observations'])} | {p['decision']} |")
    lines += ['', '## Сценарии и кредиты', '', '| Источник | Город | Сценарий | Статус | HTTP | мс | До | После |', '|---|---|---|---|---:|---:|---:|---:|']
    for p in result['providers']:
        for r in p['records']:
            lines.append('| ' + ' | '.join(md(v) for v in (p['provider'], r.get('city'), r.get('scenario'), r['status'], r.get('http_status'), r.get('latency_ms'), r.get('credits_before', r.get('credits')), r.get('credits_after'))) + ' |')
    lines += ['', '## Цены и их смысл', '', '| Источник | Город | Объект/область | Сумма | Валюта | Период | Номер/человек | Match | RUB | Ограничения |', '|---|---|---|---:|---|---|---|---|---:|---|']
    for p in result['providers']:
        for x in p['observations']:
            lines.append('| ' + ' | '.join(md(v) for v in (x['provider'], x['city'], f"{x['name']} ({x['scope']})", x['amount'], x['currency'], x['period'], x['occupancy_basis'], x['match']['confidence'], x['amount_rub'], ', '.join(x['issues']))) + ' |')
        lines += ['', f"### Метрики {p['provider']}", '']
        for scope in ('hotel', 'city', 'region'):
            group = [x for x in p['observations'] if x['scope'] == scope]
            if group:
                lines.append(scope + ': ' + '; '.join(f"{k}={v['count']}/{v['denominator']}" for k, v in metrics(group).items()))
    lines += ['', 'Пустой список наблюдений означает отсутствие измерений, а не нулевое покрытие. HTTP 200 не доказывает пригодность цены. Свежесть ответа не равна свежести цены. Городская/региональная оценка не прикрепляется к отелю. Неизвестные суммы и RUB остаются null; пересчёт по неподтверждённому курсу не выполняется. Все даты тестовые и явно отмечены в JSON. Никаких выводов о глобальном покрытии по этой выборке.', '']
    return '\n'.join(lines)


def execute(args, config, client=None):
    refs_data = baseline()
    refs = [h for city in refs_data for h in city['hotels']]
    client = client or Client(args.max_requests, args.timeout_seconds, args.delay_seconds)
    providers = []
    for provider in dict.fromkeys(args.providers):
        cfg = config.get(provider, {})
        status = gate(provider, cfg)
        records = []
        if args.offline:
            records = [{'status': 'skipped_offline', 'observations': []}]
        elif status == 'ready':
            try:
                if provider == 'makcorps':
                    records = run_mak(client, cfg, refs, args.credit_budget)
                elif provider == 'skyscanner':
                    records = run_sky(client, cfg)
                else:
                    records = run_dataestur(client, cfg)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError):
                records.append({'status': 'stopped_unexpected_response', 'observations': []})
            failed = any(r['status'] not in ('ok', 'empty_or_ambiguous_destination') for r in records)
            status = 'incomplete' if failed else ('completed' if records else 'skipped_no_scenarios')
        items = [x for r in records for x in r.get('observations', [])]
        # Promotion to use_* requires an actual interpretable price; never promote docs alone.
        decision = 'not_tested'
        if items:
            if cfg.get('review', {}).get('price_only_display_allowed') is not True:
                decision = 'not_tested'
            else:
                decision = ('use_hotel_level' if provider == 'makcorps' else 'use_city_level' if provider == 'skyscanner' else 'optional') if any(x['usable'] for x in items) else 'reject'
        providers.append({'provider': provider, 'status': status, 'credential_present': bool(os.environ.get(KEYS[provider])),
                          'display_rights': 'owner_confirmed' if cfg.get('review', {}).get('price_only_display_allowed') is True else 'access_or_display_rights_unclear',
                          'decision': decision, 'records': records, 'observations': items,
                          'metrics': {scope: metrics([x for x in items if x['scope'] == scope]) for scope in ('hotel', 'city', 'region')}})
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    status = 'offline' if args.offline else ('completed' if providers and all(p['status'] == 'completed' for p in providers) else 'incomplete_or_skipped')
    return sanitize({'version': '2.0', 'run_id': run_id, 'created_utc': utcnow(),
                     'mode': 'offline' if args.offline else 'live', 'status': status,
                     'limits': {'max_requests': args.max_requests, 'credit_budget': args.credit_budget,
                                'timeout_seconds': args.timeout_seconds, 'delay_seconds': args.delay_seconds},
                     'geoapify_baseline': refs_data, 'requests': client.records, 'providers': providers})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--offline', action='store_true')
    modes.add_argument('--live', action='store_true')
    modes.add_argument('--init-config', action='store_true')
    parser.add_argument('--config', type=Path, default=ROOT/'config.local.json')
    parser.add_argument('--providers', nargs='+', choices=tuple(KEYS), default=list(KEYS))
    parser.add_argument('--max-requests', type=int, default=12)
    parser.add_argument('--credit-budget', type=int, default=3)
    parser.add_argument('--timeout-seconds', type=float, default=20)
    parser.add_argument('--delay-seconds', type=float, default=1)
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 24 or not 1 <= args.credit_budget <= 14 or not 2 <= args.timeout_seconds <= 30 or not 1 <= args.delay_seconds <= 20:
        parser.error('limits: requests 1..24, credits 1..14, timeout 2..30s, delay 1..20s')
    if args.init_config:
        try:
            init_config(args.config)
        except OSError:
            print('Configuration creation failed (file may already exist).', file=sys.stderr)
            return 2
        print('Created local configuration; all live gates remain disabled.')
        return 0
    try:
        path = args.config if args.config.is_file() else ROOT/'config.example.json'
        config = validate_config(json.loads(path.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print('Invalid configuration: check required fields, dates and documented scenario limits. No requests made.', file=sys.stderr)
        return 2
    if 'dataestur' in args.providers:
        args.delay_seconds = max(6, args.delay_seconds)
    result = execute(args, config)
    run = ROOT/'reports/runs'/result['run_id']
    run.mkdir(parents=True, exist_ok=False)
    (run/'samples').mkdir()
    (run/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (run/'live-results.md').write_text(render(result), encoding='utf-8')
    for p in result['providers']:
        # Only normalized allowlisted observations, never original payloads or errors.
        if config.get(p['provider'], {}).get('review', {}).get('research_storage_allowed') is True:
            for i, item in enumerate(p['observations'][:2]):
                (run/'samples'/f"{p['provider']}_{i}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Run {result['run_id']}: {result['status']}; HTTP requests={len(result['requests'])}")
    for p in result['providers']:
        print(f"  {p['provider']}: {p['status']}; {p['decision']}; observations={len(p['observations'])}")
    print('Report:', run/'live-results.md')
    return 0 if args.offline or result['status'] == 'completed' else 3


if __name__ == '__main__':
    raise SystemExit(main())

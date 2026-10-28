"""Offline regression tests: no sockets, credentials or paid provider calls."""
from argparse import Namespace
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from hotel_price_core import (Client, MAK, SKY, baseline, endpoint_allowed, finish,
                              match_hotel, metrics, money, observation, sanitize)
from hotel_price_providers import (gate, normalize_dataestur, normalize_mak,
                                   normalize_sky, price_value, remaining_credits,
                                   resolve_sky_city, run_mak, run_sky)
from hotel_price_test import execute, init_config, render, validate_config


def template():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'config.local.json'
        init_config(path)
        return json.loads(path.read_text(encoding='utf-8'))


def allow(cfg):
    cfg['enabled'] = True
    cfg['review'].update(free_no_billing=True, cost_evidence='test fixture only',
                         research_storage_allowed=True, terms_evidence='test fixture only',
                         account_check_free=True, account_cost_evidence='test fixture only',
                         access_approved=True, price_only_display_allowed=True)
    return cfg


class Response:
    def __init__(self, data):
        self.status, self.headers = 200, {'Content-Type': 'application/json'}
        self.data = json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.data[:n]


class Opener:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
    def open(self, req, timeout):
        self.calls.append(req)
        value = self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return Response(value)


def client(*responses, cap=12):
    opener = Opener(*responses)
    return Client(cap, delay=0, opener=opener), opener


def account(n):
    return {'requestLimit': 15, 'requestUsed': 15-n, 'remainingLimit': n}


class HotelPriceTests(unittest.TestCase):
    def test_template_validation_and_exclusive_creation(self):
        self.assertIsInstance(validate_config(template()), dict)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'x.json'
            init_config(p)
            with self.assertRaises(FileExistsError): init_config(p)

    def test_enabled_config_rejects_stale_dates_and_sandbox(self):
        config = template()
        config['makcorps']['enabled'] = True
        config['makcorps']['checkin'] = '2000-01-01'
        with self.assertRaises(ValueError): validate_config(config)
        config = template()
        config['skyscanner'].update(enabled=True, environment='sandbox')
        with self.assertRaises(ValueError): validate_config(config)

    def test_skyscanner_limits_and_filter_evidence(self):
        config = template()
        config['skyscanner'].update(enabled=True, filter={'starsFilter': {'values': ['STARS_3']}})
        with self.assertRaises(ValueError): validate_config(config)

    def test_endpoint_allowlist_rejects_payment_redirect_and_different_host(self):
        for path in ('/prebook', '/checkout', '/hotel/../checkout', '/account?x=1'):
            self.assertFalse(endpoint_allowed('makcorps', MAK, path, 'GET'))
        self.assertFalse(endpoint_allowed('makcorps', 'http://api.makcorps.com', '/account', 'GET'))
        self.assertFalse(endpoint_allowed('makcorps', 'https://evil.example', '/account', 'GET'))

    def test_redirect_does_not_forward_secret(self):
        from hotel_price_core import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example'))

    def test_http_auth_rate_limit_stop_without_retry(self):
        for code in (401, 403, 429, 500, 302):
            c, op = client(HTTPError(MAK+'/account?api_key=SECRET', code, 'SECRET', {}, BytesIO(b'SECRET')))
            a = c.call('makcorps', MAK, '/account', {'api_key': 'SECRET'})
            b = c.call('makcorps', MAK, '/account')
            self.assertEqual(a['http_status'], code)
            self.assertEqual(b['status'], 'skipped_provider_stopped')
            self.assertEqual(len(op.calls), 1)
            self.assertNotIn('SECRET', json.dumps(c.records))

    def test_network_failure_does_not_log_exception(self):
        c, op = client(URLError('https://host/?api_key=SECRET'))
        c.call('makcorps', MAK, '/account')
        self.assertNotIn('SECRET', json.dumps(c.records))
        self.assertEqual(len(op.calls), 1)

    def test_request_cap_is_global(self):
        c, op = client({}, cap=1)
        c.call('makcorps', MAK, '/account')
        self.assertEqual(c.call('skyscanner', SKY, '/apiservices/v3/culture/currencies')['status'], 'skipped_request_cap')
        self.assertEqual(len(op.calls), 1)

    def test_secret_scrub_handles_query_and_encoded_values(self):
        from urllib.parse import quote
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'private/key+secret'}):
            data = sanitize({'name': 'private/key+secret '+quote('private/key+secret', safe=''),
                             'url': 'https://example.com/hotel?api_key=private',
                             'authorization': 'JWT private', 'email': 'a@example.com'})
        self.assertNotIn('secret', json.dumps(data))
        self.assertNotIn('?', data['url'])
        self.assertNotIn('authorization', data)

    def test_no_cost_or_terms_evidence_means_no_requests(self):
        c, op = client()
        cfg = template()
        cfg['makcorps']['enabled'] = True
        args = Namespace(offline=False, providers=['makcorps'], max_requests=12,
                         timeout_seconds=20, delay_seconds=1, credit_budget=3)
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'fixture-secret'}):
            result = execute(args, cfg, c)
        self.assertEqual(result['providers'][0]['status'], 'skipped_cost_not_verified')
        self.assertEqual(len(op.calls), 0)

    def test_offline_never_calls_even_when_ready(self):
        c, op = client()
        cfg = template()
        allow(cfg['makcorps'])
        args = Namespace(offline=True, providers=['makcorps'], max_requests=12,
                         timeout_seconds=20, delay_seconds=1, credit_budget=3)
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'fixture-secret'}):
            result = execute(args, cfg, c)
        self.assertEqual(len(op.calls), 0)
        self.assertEqual(result['status'], 'offline')

    def test_uncertain_account_cost_blocks_before_first_call(self):
        cfg = allow(template()['makcorps'])
        cfg['review']['account_check_free'] = False
        c, op = client()
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'test'}):
            run_mak(c, cfg, [], 3)
        self.assertEqual(len(op.calls), 0)

    def test_credit_budget_cannot_exhaust_quota(self):
        cfg = allow(template()['makcorps'])
        cfg.update(scenarios=[{'kind': 'mapping', 'city': 'Paris', 'name': 'test'}], credit_costs={'mapping': 1})
        c, op = client(account(3))
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'test'}):
            records = run_mak(c, cfg, [], 3)
        self.assertEqual(len(op.calls), 1)
        self.assertEqual(records[-1]['status'], 'skipped_quota_not_verified')

    def test_credit_drift_stops_further_scenarios(self):
        cfg = allow(template()['makcorps'])
        cfg.update(scenarios=[{'kind': 'mapping', 'city': 'Paris', 'name': 'test'}]*2, credit_costs={'mapping': 1})
        c, op = client(account(15), [], account(13))
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'test'}):
            records = run_mak(c, cfg, [], 3)
        self.assertEqual(len(op.calls), 3)
        self.assertEqual(records[-1]['status'], 'stopped_credit_accounting_unclear')

    def test_mak_mapping_then_hotel_fixture_end_to_end(self):
        cfg = allow(template()['makcorps'])
        cfg['scenarios'] = [
            {'kind': 'mapping', 'city': 'Paris', 'name': 'Le Relais de Lyon Paris'},
            {'kind': 'hotel', 'city': 'Paris', 'mapping_name': 'Le Relais de Lyon Paris'}]
        cfg['credit_costs'].update(mapping=1, hotel=1)
        refs = [{'name': 'Le Relais de Lyon', 'city': 'Paris', 'geoapify_id': 'geo-id',
                 'coordinates': [48.84958, 2.37988]}]
        mapping = [{'document_id': '42', 'type': 'HOTEL', 'details': {'name': 'Le Relais de Lyon'},
                    'coords': '48.84958,2.37988'}]
        c, op = client(account(15), mapping, account(14), account(14),
                       {'comparison': [[{'vendor1': 'Vendor', 'price1': '$100', 'tax1': '$10'}], []]}, account(13))
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'fixture-secret'}):
            records = run_mak(c, cfg, refs, 3)
        self.assertEqual(len(op.calls), 6)
        hotels = [x for r in records for x in r['observations']]
        self.assertEqual(hotels[0]['match']['confidence'], 'high_confidence')
        self.assertEqual(hotels[0]['provider_id'], '42')
        self.assertIsNone(hotels[0]['amount_rub'])
        self.assertIn('price_basis_unknown', hotels[0]['issues'])
        self.assertIn('hotelid=42', op.calls[4].full_url)

    def test_mak_city_mapping_does_not_guess_city_id(self):
        cfg = allow(template()['makcorps'])
        cfg['scenarios'] = [{'kind': 'mapping', 'city': 'Paris', 'name': 'Paris'},
                            {'kind': 'city', 'city': 'Paris', 'mapping_name': 'Paris'}]
        cfg['credit_costs'].update(mapping=1, city=1)
        c, op = client(account(15), [{'document_id': '43', 'type': 'GEO', 'details': {'name': 'Paris'}, 'coords': '48.8566,2.3522'}],
                       account(14), account(14), [], account(13))
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'fixture-secret'}):
            run_mak(c, cfg, [], 3)
        self.assertEqual(len(op.calls), 6)
        self.assertIn('cityid=43', op.calls[4].full_url)
        self.assertIn('tax=true', op.calls[4].full_url)

    def test_unknown_credit_schema_is_not_zero(self):
        self.assertIsNone(remaining_credits({'remainingLimit': 15}))
        self.assertIsNone(remaining_credits({'remainingLimit': 15, 'requestLimit': 15, 'requestUsed': 3}))
        self.assertEqual(remaining_credits(account(15)), 15)

    def test_no_price_call_without_postcheck_budget(self):
        cfg = allow(template()['makcorps'])
        cfg.update(scenarios=[{'kind': 'mapping', 'city': 'Paris', 'name': 'test'}], credit_costs={'mapping': 1})
        c, op = client(cap=2)
        with patch.dict(os.environ, {'MAKCORPS_API_KEY': 'test'}):
            run_mak(c, cfg, [], 3)
        self.assertEqual(len(op.calls), 0)

    def test_same_name_without_geography_is_ambiguous(self):
        refs = [{'name': 'Central Hotel', 'city': 'Paris', 'coordinates': [48.85, 2.35], 'geoapify_id': 'x'}]
        item = {'name': 'Central Hotel', 'city': 'Paris', 'coordinates': None}
        self.assertEqual(match_hotel(item, refs)['confidence'], 'ambiguous')
        item['coordinates'] = [48.85, 2.35]
        self.assertEqual(match_hotel(item, refs)['confidence'], 'high_confidence')
        self.assertEqual(match_hotel(item, refs+refs)['confidence'], 'ambiguous')

    def test_free_prices_do_not_infer_currency_or_basis(self):
        cfg = template()['makcorps']
        items = normalize_mak([[{'hotelName': 'A', 'hotelId': '1'}, [{'vendor1': 'V', 'price1': '100', 'tax1': '10'}]]], 'Paris', [], {'kind': 'free'}, cfg)
        self.assertEqual(items[0]['amount'], '100')
        self.assertIsNone(items[0]['currency'])
        self.assertIsNone(items[0]['amount_rub'])
        self.assertFalse(items[0]['usable'])

    def test_number_parsing_does_not_guess_decimal_separator(self):
        self.assertEqual(money('$1,443'), '1443')
        self.assertIsNone(money('1,44'))
        self.assertIsNone(money(float('inf')))
        self.assertIsNone(money(True))
        self.assertIsNone(money('-2'))

    def test_sky_units_and_scope(self):
        self.assertEqual(price_value({'amount': '123450000', 'unit': 'PRICE_UNIT_MICRO'}), '123.45')
        self.assertIsNone(price_value({'amount': '123', 'unit': 'PRICE_UNIT_UNSPECIFIED'}))
        cfg = template()['skyscanner']
        data = {'resultSet': {'prices': {'opaque': {'prices': [{'type': 'PRICE_AGGREGATION_TYPE_AVERAGE', 'price': {'amount': '12345', 'unit': 'PRICE_UNIT_CENTI'}}]}}}}
        x = normalize_sky(data, 'Paris', 'verified-id', cfg)[0]
        self.assertEqual(x['scope'], 'city')
        self.assertIsNone(x['match']['geoapify_id'])
        self.assertIsNone(x['amount_rub'])  # Unit room/person is still unknown.

    def test_autosuggest_does_not_choose_wrong_paris_or_first_id(self):
        place = {'type': 'PLACE_TYPE_CITY', 'name': 'Paris', 'entityId': 'abc', 'location': {'latitude': 33.66, 'longitude': -95.55}}
        self.assertIsNone(resolve_sky_city({'places': [place]}, 'Paris'))
        place['location'] = {'latitude': 48.8566, 'longitude': 2.3522}
        self.assertEqual(resolve_sky_city({'places': [place]}, 'Paris'), 'abc')
        self.assertIsNone(resolve_sky_city({'places': [place, {**place, 'entityId': 'def'}]}, 'Paris'))

    def test_sky_fake_end_to_end_uses_official_paths_and_no_guessed_id(self):
        cfg = allow(template()['skyscanner'])
        cfg['cities'] = ['Paris', 'TripFlowNonexistentCityZXQ']
        c, op = client({'currencies': [{'code': 'RUB'}]}, {'locales': [{'code': 'en-GB'}]},
                       {'markets': [{'code': 'UK'}]},
                       {'places': [{'name': 'Paris', 'type': 'PLACE_TYPE_CITY', 'entityId': 'from-api', 'location': {'latitude': 48.8566, 'longitude': 2.3522}}]},
                       {'resultSet': {'prices': {}}}, {'places': []})
        with patch.dict(os.environ, {'SKYSCANNER_API_KEY': 'test-secret'}):
            records = run_sky(c, cfg)
        self.assertEqual(len(op.calls), 6)
        query = json.loads(op.calls[4].data)['query']
        self.assertEqual(query['destinationEntityIds'], ['from-api'])
        self.assertNotIn('adults', query)
        self.assertEqual(records[-1]['status'], 'empty_or_ambiguous_destination')

    def test_dataestur_csv_unmapped_is_inspected_not_guessed(self):
        cfg = template()['dataestur']
        items, meta = normalize_dataestur(b'category;amount\nhotel;100\n', cfg)
        self.assertEqual(items, [])
        self.assertEqual(meta['row_count'], 1)
        self.assertEqual(meta['columns'], ['category', 'amount'])
        with self.assertRaises(ValueError): normalize_dataestur(b'<html>error</html>', cfg)

    def test_no_observations_means_no_coverage_claim(self):
        self.assertIsNone(metrics([])['usable']['fraction'])
        self.assertEqual(metrics([])['usable']['denominator'], 0)

    def test_existing_baseline_is_read_without_network(self):
        cities = baseline()
        self.assertEqual(len(cities), 4)
        self.assertTrue(all('status' in c for c in cities))

    def test_report_does_not_claim_completed_live_from_offline(self):
        args = Namespace(offline=True, providers=['makcorps'], max_requests=12,
                         timeout_seconds=20, delay_seconds=1, credit_budget=3)
        c, _ = client()
        result = execute(args, template(), c)
        self.assertEqual(result['providers'][0]['decision'], 'not_tested')
        self.assertIn('HTTP-запросов: 0', render(result))


if __name__ == '__main__':
    unittest.main()

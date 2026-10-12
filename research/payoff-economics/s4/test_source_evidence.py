"""Synthetic adversarial controls; no network or economic authority."""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import source_audit as source
import campaign
from capture_real import checked_protocol, experiment_config, select_from_definitions, require_future_dates, event_request
from analyze_real import checked_capture


def candles():
    boundary = source.noon_ms(source.PROBE_DAY)
    rows = [[boundary - 60_000 + i * 60_000, '82000.00', '82001.00', '81999.00',
        '82000.00000001' if i else '82000.00000000', '1.00', boundary - 1 + i * 60_000,
        '82000.00', 2, '0.50', '41000.00', '0'] for i in range(2)]
    return boundary, rows


def source_fixture(root, *, status=200):
    (root / 'raw').mkdir(parents=True)
    boundary, body = candles()
    records = []
    for label, url in source.requests_by_label().items():
        data = json.dumps(body).encode() if label == 'binance-candles' else ('SYNTHETIC DOC ' + label).encode()
        digest = sha256(data).hexdigest()
        (root / 'raw' / (digest + '.bin')).write_bytes(data)
        actual_status = status if label == 'binance-candles' else 200
        records.append({'label': label, 'url': url, 'method': 'GET', 'status': actual_status,
            'started_ns': (boundary + 120_000) * 1_000_000,
            'received_ns': (boundary + 120_001) * 1_000_000,
            'bytes': len(data), 'body_sha256': digest, 'error': None if actual_status == 200 else 'HTTP_' + str(actual_status),
            'headers': {}})
    source.write_json(root / 'requests.json', records)
    return records


class SourceEvidenceTests(unittest.TestCase):
    def test_noon_named_timezone_handles_both_dst_transitions(self):
        for day, hour in [('2026-03-07', 17), ('2026-03-08', 16), ('2026-10-31', 16), ('2026-11-01', 17)]:
            value = source.noon_ms(date.fromisoformat(day))
            actual = datetime.fromtimestamp(value // 1000, timezone.utc)
            self.assertEqual(actual.hour, hour)
            self.assertEqual(actual.date().isoformat(), day)
        with self.assertRaises(ValueError):
            source.noon_ms(datetime.now(timezone.utc))

    def test_both_source_candidates_retained_without_selecting_contract_value(self):
        boundary, rows = candles()
        result = source.validate_candles(rows, boundary, boundary + 120_000)
        self.assertEqual(len(result['candles']), 2)
        self.assertFalse(result['equal_close_values'])
        self.assertIsNone(result['selected_contract_value'])
        self.assertFalse(result['contract_candle_choice_certified'])
        self.assertFalse(result['revision_finality_certified'])
        self.assertFalse(result['execution_authority'])

    def test_decimal_equality_does_not_imply_candle_identity(self):
        boundary, rows = candles()
        rows[1][4] = '82000.0000'
        result = source.validate_candles(rows, boundary, boundary + 120_000)
        self.assertTrue(result['equal_close_values'])
        self.assertNotEqual(result['candles'][0]['open_ms'], result['candles'][1]['open_ms'])
        self.assertIsNone(result['selected_contract_value'])

    def test_partial_or_future_candle_rejected(self):
        boundary, rows = candles()
        for now in (boundary - 1, boundary, boundary + 59_998, boundary + 59_999, True):
            with self.subTest(now=now), self.assertRaises(ValueError):
                source.validate_candles(rows, boundary, now)

    def test_wrong_identity_and_incomplete_source_do_not_become_fallback(self):
        boundary, rows = candles()
        variants = [[], rows[:1], rows[::-1], rows + rows[:1], [rows[0], rows[0]], [rows[0][:-1], rows[1]]]
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                source.validate_candles(value, boundary, boundary + 120_000)
        for field, value in [(0, True), (0, boundary), (6, boundary), (8, True), (8, -1), (4, 82000.0), (4, 'NaN'), (4, '82002')]:
            bad = deepcopy(rows)
            bad[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                source.validate_candles(bad, boundary, boundary + 120_000)

    def test_decimals_are_exact_and_bounded(self):
        self.assertEqual(source.exact_decimal('82000.00000001'), Fraction(8200000000001, 100000000))
        for value in (True, 1, '1e2', 'NaN', 'Infinity', '-1', '+1', ' 1', '1 ', '01', '1/2', '1.' + '1' * 17):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source.exact_decimal(value)

    def test_negative_or_inconsistent_ohlc_rejected(self):
        boundary, rows = candles()
        for field, value in [(1, '82002'), (2, '81000'), (3, '0'), (5, '-1'), (9, 'Infinity')]:
            bad = deepcopy(rows)
            bad[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                source.validate_candles(bad, boundary, boundary + 120_000)

    def test_redirect_is_never_followed(self):
        with self.assertRaises(ValueError):
            source.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.invalid/key')

    def test_source_receipts_do_not_remove_contract_specific_unknowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_fixture(root)
            report = source.audit(root)
            self.assertEqual(report['candle_probe']['status'], 'TWO_CLOSED_API_INTERVALS_OBSERVED')
            self.assertGreaterEqual(len(report['unresolved']), 7)
            self.assertFalse(report['certificate_authority'])
            self.assertIsNone(report['contract_final_value'])
            self.assertIsNone(report['realized_profit'])

    def test_unavailable_source_is_not_zero_price_or_success(self):
        for status in (0, 301, 403, 404, 429, 451, 500):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_fixture(root, status=status)
                report = source.audit(root)
                self.assertEqual(report['candle_probe']['status'], 'NOT_ESTABLISHED')
                self.assertIsNone(report['candle_probe']['selected_contract_value'])
                self.assertFalse(report['certificate_authority'])

    def test_raw_hash_and_request_identity_rechecked(self):
        for kind in ('raw', 'url', 'method', 'clock', 'status', 'duplicate'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                records = source_fixture(root)
                if kind == 'raw':
                    (root / 'raw' / (records[0]['body_sha256'] + '.bin')).write_bytes(b'changed')
                elif kind == 'url':
                    records[0]['url'] += '?altered=1'
                elif kind == 'method':
                    records[0]['method'] = 'POST'
                elif kind == 'clock':
                    records[0]['received_ns'] = records[0]['started_ns'] - 1
                elif kind == 'status':
                    records[0]['status'] = True
                else:
                    records[1] = records[0]
                (root / 'requests.json').write_text(json.dumps(records))
                with self.assertRaises(ValueError):
                    source.audit(root)

    def test_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            source.write_json(path, {'first': True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                source.write_json(path, {'later': True})
            self.assertEqual(path.read_bytes(), before)


class PopulationTests(unittest.TestCase):
    def test_explicit_followup_and_original_protocols_differ(self):
        self.assertEqual(experiment_config(8)['dates'], ['2026-10-12', '2026-10-13'])
        fixed = campaign.fixed_protocol()
        self.assertEqual(len(fixed['dates']), 4)
        self.assertEqual(fixed['cycles'], 12)
        self.assertEqual(fixed['interval_seconds'], 5)
        with self.assertRaises(ValueError):
            experiment_config(12)

    def test_bad_population_and_authority_are_rejected(self):
        for key, value in [('dates', []), ('dates', ['2026-10-13'] * 2), ('dates', ['2026-02-30']),
                           ('dates', ['2026-10-14', '2026-10-13']), ('dates', [20261013]),
                           ('cycles', True), ('cycles', 13), ('interval_seconds', 0),
                           ('selection_uses_prices', True), ('no_live_actions', 1), ('fixed_above', ['80,000'])]:
            bad = campaign.fixed_protocol()
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                checked_protocol(bad)
        bad = campaign.fixed_protocol()
        bad['extra'] = 1
        with self.assertRaises(ValueError):
            checked_protocol(bad)

    def test_new_capture_cannot_silently_use_past_date(self):
        config = campaign.fixed_protocol()
        require_future_dates(config, datetime(2026, 10, 12, 13, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            require_future_dates(config, datetime(2026, 10, 13, 16, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            require_future_dates(config, datetime(2026, 10, 12, 13))

    def test_fixed_selector_keeps_missing_dates(self):
        dates = tuple(map(date.fromisoformat, campaign.fixed_protocol()['dates']))
        def read(url, label):
            return {'label': label, 'url': url, 'status': 404, 'error': 'HTTP_404'}, None
        selected, tokens = select_from_definitions(read, dates=dates)
        self.assertEqual(len(selected['families']), 4)
        self.assertEqual(len(selected['exclusions']), 8)
        self.assertEqual(tokens, set())
        self.assertTrue(all(f['selected'] == [] for f in selected['families']))

    def test_manifest_does_not_choose_its_own_expected_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = campaign.fixed_protocol()
            (root / 'config.json').write_text(json.dumps(config))
            evidence = SimpleNamespace(root=root, by_label={})
            with self.assertRaises(ValueError):
                checked_capture(evidence)
            dates = tuple(map(date.fromisoformat, config['dates']))
            def read(url, label):
                record = {'label': label, 'url': url, 'status': 404, 'error': 'HTTP_404'}
                evidence.by_label[label] = record
                return record, None
            selected, _ = select_from_definitions(read, dates=dates)
            (root / 'selection.json').write_text(json.dumps(selected))
            checked, cycles = checked_capture(evidence, expected_config=config)
            self.assertEqual(checked, selected)
            self.assertEqual(cycles, 12)
            config['dates'] = config['dates'][:-1]
            (root / 'config.json').write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                checked_capture(evidence, expected_config=campaign.fixed_protocol())

    def test_missing_whole_windows_stay_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'campaign.json').write_text(json.dumps(campaign.campaign_config()))
            with (
                patch.object(campaign, 'Evidence', side_effect=FileNotFoundError('missing raw')),
                patch.object(campaign, 'audit_source', return_value={'candle_probe': {'status': 'NOT_ESTABLISHED'}}),
            ):
                result = campaign.analyze(root)
            self.assertEqual(result['summary']['group_rounds_attempted'], 96)
            self.assertEqual(result['summary']['group_rounds_admitted'], 0)
            self.assertEqual(result['summary']['group_rounds_excluded'], 96)
            self.assertEqual(result['summary']['exact_gross_witness_rounds'], 0)
            self.assertFalse(result['summary']['no_trade_global_claim'])
            self.assertFalse(result['summary']['planned_window_gap_met'])

    def test_changed_campaign_denominator_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = campaign.campaign_config()
            config['windows'] = 1
            (root / 'campaign.json').write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                campaign.analyze(root)


if __name__ == '__main__':
    unittest.main()

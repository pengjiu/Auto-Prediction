"""Synthetic counterexamples for S4 receipt/protocol integrity, never live data."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import campaign
import source_audit as source
from test_source_evidence import source_fixture

PLAN_HASH = 'a7b7654f16e913081f1d26319f96245cd22ba21a473af6940b17a8d7d37e3ed5'


def dump(path, value):
    path.write_text(json.dumps(value))


def specimen(root):
    """Real Evidence reader, synthetic bytes; stub only costly economic solver."""
    config = campaign.campaign_config()
    dump(root / 'campaign.json', config)
    source_fixture(root / 'source')
    start = (source.noon_ms(source.PROBE_DAY) + 120_000) * 1_000_000 - 1_000
    dump(root / 'provenance.json', {'plan_sha256': PLAN_HASH,
        'config_sha256': sha256(campaign.canonical(config).encode()).hexdigest(),
        'started_ns': start, 'authority': 'ANONYMOUS_PUBLIC_OBSERVATION_ONLY'})
    dump(root / 'capture-complete.json', {'finished_ns': start + 220_000_000_000, 'attempted_windows': 2})
    for window in range(2):
        folder = root / f'window-{window}'
        (folder / 'raw').mkdir(parents=True)
        body = b'{}'
        digest = sha256(body).hexdigest()
        (folder / 'raw' / (digest + '.bin')).write_bytes(body)
        rows = []
        for cycle in range(12):
            at = start + (5 + window * 120 + cycle * 5) * 1_000_000_000
            rows.append({'label': f'book:{cycle}:123', 'url': 'https://clob.polymarket.com/book?token_id=123',
                'method': 'GET', 'status': 200, 'error': None, 'body_sha256': digest, 'bytes': len(body),
                'started_ns': at, 'received_ns': at + 500_000_000})
        (folder / 'requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return start


def economic_report(*args, **kwargs):
    return {'families': [{'date': day, 'blocker': None, 'rows': [
        {'cycle': i, 'admitted': True, 'gross_witness': ['1'],
         'analysis': {'s1': {'lower_floor': 0}, 'incremental_gross_floor': 0}}
        for i in range(12)]} for day in campaign.fixed_protocol()['dates']]}


class SourceIntegrityTests(unittest.TestCase):
    def test_receipt_delay_cannot_finalize_an_open_candle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); rows = source_fixture(root)
            boundary = source.noon_ms(source.PROBE_DAY)
            rows[-1]['started_ns'] = (boundary + 30_000) * 1_000_000
            rows[-1]['received_ns'] = (boundary + 120_000) * 1_000_000
            dump(root / 'requests.json', rows)
            result = source.audit(root)
            self.assertEqual(result['candle_probe']['status'], 'NOT_ESTABLISHED')
            self.assertIsNone(result['contract_final_value'])

    def test_absent_error_status_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); rows = source_fixture(root)
            del rows[-1]['error']; dump(root / 'requests.json', rows)
            with self.assertRaises(ValueError): source.audit(root)

    def test_malformed_receipt_rejected_with_validation_error(self):
        for replacement in (None, [], 7):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); rows = source_fixture(root)
                rows[0] = replacement; dump(root / 'requests.json', rows)
                with self.assertRaises(ValueError): source.audit(root)


class CampaignIntegrityTests(unittest.TestCase):
    def run_analysis(self, root):
        with patch.object(campaign, 'analyze_capture', side_effect=economic_report):
            return campaign.analyze(root)

    def test_valid_receipts_do_not_certify_settlement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); specimen(root); result = self.run_analysis(root)
            self.assertTrue(result['summary'].get('replication_protocol_conformant', False))
            self.assertEqual(result['summary']['group_rounds_admitted'], 96)
            self.assertFalse(result['summary']['fee_debit_certified'])
            self.assertIsNone(result['summary']['realized_profit'])

    def test_changed_plan_config_authority_and_start_rejected(self):
        for key, value in [('plan_sha256', '0'*64), ('config_sha256', '0'*64),
                           ('authority', 'CERTIFIED'), ('started_ns', True)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); specimen(root)
                data = json.loads((root / 'provenance.json').read_text()); data[key] = value
                dump(root / 'provenance.json', data)
                with self.assertRaises(ValueError): self.run_analysis(root)

    def test_changed_completion_population_or_clock_rejected(self):
        for key, value in [('attempted_windows', 1), ('attempted_windows', True), ('finished_ns', 1)]:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); specimen(root)
                data = json.loads((root / 'capture-complete.json').read_text()); data[key] = value
                dump(root / 'capture-complete.json', data)
                with self.assertRaises(ValueError): self.run_analysis(root)

    def test_missing_provenance_cannot_claim_conforming_replication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); specimen(root); (root / 'provenance.json').unlink()
            result = self.run_analysis(root)
            self.assertFalse(result['summary'].get('replication_protocol_conformant', True))
            self.assertEqual(result['summary']['group_rounds_attempted'], 96)
            self.assertEqual(result['summary']['group_rounds_admitted'], 0)

    def test_duplicate_window_is_excluded_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); specimen(root)
            shutil.rmtree(root / 'window-1'); shutil.copytree(root / 'window-0', root / 'window-1')
            result = self.run_analysis(root)
            self.assertEqual(result['summary']['group_rounds_attempted'], 96)
            self.assertEqual(result['summary']['group_rounds_admitted'], 48)
            self.assertEqual(result['summary']['group_rounds_excluded'], 48)
            self.assertFalse(result['summary'].get('replication_protocol_conformant', True))

    def test_window_outside_declared_envelope_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); start = specimen(root)
            data = json.loads((root / 'provenance.json').read_text()); data['started_ns'] = start + 6_000_000_000
            dump(root / 'provenance.json', data)
            result = self.run_analysis(root)
            self.assertEqual(result['summary']['group_rounds_admitted'], 48)
            self.assertFalse(result['summary'].get('replication_protocol_conformant', True))

    def test_overlapping_rounds_are_not_a_time_replication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); specimen(root)
            path = root / 'window-0' / 'requests.jsonl'
            rows = [json.loads(s) for s in path.read_text().splitlines()]
            rows[1]['started_ns'] = rows[0]['started_ns']; rows[1]['received_ns'] = rows[0]['received_ns']
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            result = self.run_analysis(root)
            self.assertEqual(result['summary']['group_rounds_admitted'], 48)
            self.assertFalse(result['summary'].get('replication_protocol_conformant', True))

    def test_missing_source_cannot_erase_market_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); specimen(root); shutil.rmtree(root / 'source')
            result = self.run_analysis(root)
            self.assertEqual(result['summary']['group_rounds_attempted'], 96)
            self.assertEqual(result['summary']['group_rounds_admitted'], 96)
            self.assertEqual(result['summary']['source_probe_status'], 'NOT_ESTABLISHED')
            self.assertFalse(result['source_audit']['certificate_authority'])
            self.assertEqual(len(result['source_audit']['unresolved']), 7)

    def test_missing_completion_preserves_diagnostics_but_is_not_full_replication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); specimen(root); (root / 'capture-complete.json').unlink()
            result = self.run_analysis(root)
            self.assertEqual(result['summary']['group_rounds_attempted'], 96)
            self.assertEqual(result['summary']['group_rounds_admitted'], 96)
            self.assertFalse(result['summary'].get('replication_protocol_conformant', True))


if __name__ == '__main__': unittest.main()

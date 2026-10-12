"""Regression cases from the interrupted real-family review. No network IO."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
import zipfile

from analyze_real import analyze_capture, checked_capture
from bridge import analyze_compiled, Evidence
from test_bridge import case

CAPTURE = Path(__file__).with_name('fixtures')/'real-binance'/'capture-2026-10-12.zip'

@contextmanager
def original_capture():
    with TemporaryDirectory() as tmp:
        if sha256(CAPTURE.read_bytes()).hexdigest() != 'fac0590be30054a37d85775764d75bfe1fe59c6cc9d6ad533d02f307536f6e7a':
            raise AssertionError('original fixture changed')
        with zipfile.ZipFile(CAPTURE) as archive:
            root = Path(tmp).resolve()
            for item in archive.infolist():
                if not (root/item.filename).resolve().is_relative_to(root):
                    raise AssertionError('unsafe fixture path')
            archive.extractall(root)
        yield root/'real-family-evidence'

class ResumedResearchChecks(unittest.TestCase):
    def test_original_capture_population_rounds_and_sources_remain_admitted(self):
        with original_capture() as root:
            selection, cycles=checked_capture(Evidence(root))
            self.assertEqual(len(selection['families']),2)
            self.assertEqual(cycles,8)
            self.assertEqual(selection,json.loads((root/'selection.json').read_text()))

    def test_missing_last_round_is_not_a_smaller_declared_population(self):
        with original_capture() as root:
            rows=[json.loads(line) for line in (root/'requests.jsonl').read_text().splitlines()]
            (root/'requests.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows
                if not r['label'].startswith('book:7:')))
            self.assertEqual(checked_capture(Evidence(root))[1],8)
            with patch('analyze_real.recompile',return_value={}):
                result=analyze_capture(root)
            self.assertEqual(result['summary']['rounds_attempted'],16)
            self.assertEqual(result['summary']['rounds_admitted'],0)
            self.assertTrue(all(f['blocker'] is not None for f in result['families']))

    def test_undeclared_round_or_token_cannot_expand_experiment(self):
        for label in ('book:8:123','book:0:123'):
            with self.subTest(label=label), original_capture() as root:
                rows=[json.loads(line) for line in (root/'requests.jsonl').read_text().splitlines()]
                extra=deepcopy(next(r for r in rows if r['label'].startswith('book:')))
                extra['label']=label
                with (root/'requests.jsonl').open('a') as f:f.write(json.dumps(extra)+'\n')
                with self.assertRaises(ValueError):checked_capture(Evidence(root))

    def test_received_policy_is_usable_but_real_export_requires_policy_receipts(self):
        source,quotes=case()
        source['policySources']=[{'url':'https://docs.polymarket.com/concepts/resolution.md',
            'hash':'a'*64,'receivedAt':source['sources'][0]['sourceReceivedAt']}]
        self.assertEqual(analyze_compiled(source,quotes)['s1']['lower_floor'],1_000_000)
        source['policySources']=[]
        with self.assertRaises(ValueError):analyze_compiled(source,quotes)
        del source['policySources']
        source['interpretation']='FULL_DESCRIPTION_NORMAL_BRANCH_ONLY'
        with self.assertRaises(ValueError):analyze_compiled(source,quotes)

    def test_policy_clock_cannot_be_future_stale_naive_or_missing(self):
        for time in ('2026-10-13T00:00:00.000Z','2026-10-01T00:00:00.000Z',
                     '2026-10-12T00:00:00',None):
            with self.subTest(time=time):
                source, quotes = case()
                source['policySources']=[{'url':'https://docs.polymarket.com/concepts/resolution.md',
                    'hash':'a'*64,'receivedAt':time}]
                with self.assertRaises(ValueError):analyze_compiled(source,quotes)

    def test_shared_analysis_entry_cannot_skip_quote_url_check(self):
        source,quotes=case()
        next(iter(quotes.values()))[0]['url']='https://clob.polymarket.com/book?token_id=foreign'
        with self.assertRaises(ValueError):analyze_compiled(source,quotes)

    def test_full_predetermined_date_population_cannot_be_dropped_or_duplicated(self):
        for action in ('drop','duplicate','date'):
            with self.subTest(action=action), original_capture() as root:
                selection=json.loads((root/'selection.json').read_text())
                if action=='drop':selection['families'].pop()
                elif action=='duplicate':selection['families'][1]=deepcopy(selection['families'][0])
                else:selection['families'][0]['date']='2027-10-12'
                (root/'selection.json').write_text(json.dumps(selection))
                with patch('analyze_real.recompile',return_value={}):
                    with self.assertRaises(ValueError):analyze_capture(root)

    def test_predeclared_configuration_cannot_be_changed_to_claim_another_experiment(self):
        for field,value in (('fixed_above',['84,000','86,000']),('cycles',0),
                            ('selection_uses_prices',True),('dates',['2027-10-12'])):
            with self.subTest(field=field), original_capture() as root:
                config=json.loads((root/'config.json').read_text());config[field]=value
                (root/'config.json').write_text(json.dumps(config))
                with patch('analyze_real.recompile',return_value={}):
                    with self.assertRaises(ValueError):analyze_capture(root)

    def test_selection_members_tokens_and_request_identity_are_bound_to_raw(self):
        for action in ('token','market','definition','label'):
            with self.subTest(action=action), original_capture() as root:
                selection=json.loads((root/'selection.json').read_text());group=selection['families'][0]
                if action=='token':group['selected'][0]['tokens'][0]='wrong'
                elif action=='market':group['selected'][0]['market_id']='5330074'
                elif action=='definition':group['definitions'][0]['url']='https://gamma-api.polymarket.com/events?slug=other'
                else:group['selected'][0]['event_label']='before:other'
                (root/'selection.json').write_text(json.dumps(selection))
                with patch('analyze_real.recompile',return_value={}):
                    with self.assertRaises(ValueError):analyze_capture(root)

if __name__=='__main__':unittest.main()

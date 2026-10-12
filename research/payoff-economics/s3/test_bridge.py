from fractions import Fraction as F
from datetime import datetime
import json
from pathlib import Path
import unittest
from bridge import analyze_compiled, validate_export

FIXTURE = Path(__file__).with_name('fixtures') / 'synthetic-export.json'


def case():
    export = json.loads(FIXTURE.read_text())
    # Entirely invented prices: NO(high) + YES(low) costs 0.9 with floor 1.
    prices = ['0.4', '0.7', '0.6', '0.5']
    quotes = {}
    timestamp = int(datetime.fromisoformat(export['sources'][0]['sourceReceivedAt'].replace('Z','+00:00')).timestamp())
    nanos = timestamp * 1_000_000_000
    for a, price in zip(export['assets'], prices):
        quotes[a['id']] = ({'started_ns':nanos, 'received_ns':nanos+10_000_000,
            'duration_ns':10_000_000, 'method':'GET','status':200,'error':None},
            {'asset_id':a['id'], 'market':a['instrumentId'], 'hash':'SYNTHETIC',
             'timestamp':str(timestamp*1000), 'tick_size':'0.01','min_order_size':'1',
             'asks':[{'price':price,'size':'10'}], 'bids':[]})
    return export,quotes


class SemanticEconomicBridge(unittest.TestCase):
    def test_same_depth_control_and_exception_stress(self):
        e,q = case(); result = analyze_compiled(e,q)
        self.assertEqual(result['s1']['lower_floor'], 1_000_000)
        self.assertEqual(result['same_depth_baseline']['lower_floor'], 1_000_000)
        self.assertEqual(result['incremental_gross_floor'], 0)
        self.assertEqual(result['independent_resolution_stress']['lower_floor'], 0)
        self.assertEqual(result['net_qualification'], 'BLOCKED_UNQUALIFIED_FEES')
        self.assertIsNone(result['realized_profit'])
        self.assertLess(F(result['partial_fill_stress']['worst_floor']), 0)

    def test_cannot_promote_authority_or_drop_states(self):
        for field,value in [('authority','CERTIFIED'),('coverage','REAL_STATES'),('certificateAuthority',True)]:
            e,_ = case(); e[field] = value
            with self.assertRaises(ValueError): validate_export(e)
        e,_ = case(); e['assets'][0]['payoffs'].pop(e['states'][0])
        with self.assertRaises(ValueError): validate_export(e)

    def test_duplicate_and_extra_quote_identity(self):
        e,q = case(); e['assets'][1]['id'] = e['assets'][0]['id']
        with self.assertRaises(ValueError): validate_export(e)
        e,q = case(); q['not-an-asset'] = next(iter(q.values()))
        with self.assertRaises(ValueError): analyze_compiled(e,q)

    def test_stale_skew_foreign_token_and_tick_rejected(self):
        for change in ['stale','skew','token','condition','tick']:
            e,q = case(); rec, body = next(iter(q.values()))
            if change=='stale': body['timestamp']='1';rec['received_ns']=250_000_000_000;rec['started_ns']=250_000_000_000
            elif change=='skew': rec['received_ns']+=10_000_000_000
            elif change=='token': body['asset_id']='other'
            elif change=='condition': body['market']='other'
            else: body['tick_size']='0.3'
            with self.assertRaises(ValueError): analyze_compiled(e,q)

    def test_rule_cannot_arrive_after_quote_or_be_silently_stale(self):
        for stamp in ['2026-10-13T00:00:00.000Z','2026-10-01T00:00:00.000Z']:
            e,q = case(); e['sources'][0]['sourceReceivedAt'] = stamp
            with self.assertRaises(ValueError): analyze_compiled(e,q)

    def test_minimum_size_and_no_trade_controls(self):
        e,q = case()
        for _,body in q.values(): body['min_order_size']='11'
        result = analyze_compiled(e,q)
        self.assertEqual(result['s1']['buys'], ())
        self.assertEqual(result['s1']['lower_floor'],0)

if __name__ == '__main__': unittest.main()

"""Adversarial S2 tests: exact proofs, strong baselines, no invented fills."""
from __future__ import annotations
import copy
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parent))
from capture import allowed_url, market_tokens
from analyze import Evidence, payoff_matrix, nominal_fee_asks, process_replays
from economics import (SCALE, alignment, rational, units, parse_book, rule_identity,
    partition_witness, verify_witness, fee_posture, parse_model, partial_fill_floor,
    solve_maximin, walk_limit, SampledLedger, model_from_books, equal_size_frontier,
    equal_size_depth_frontier, top_of_book_equal_size_baseline, canonical_hash)


def model(levels=None):
    levels=levels or [[(40,2,0),(45,3,0)],[(40,4,0),(46,2,0)]]
    return parse_model({'coverage':'ASSUMED_STATES_ONLY','evidence_id':'test',
        'scale':100,'budget':500,'venue_budgets':{'v':500},'states':['A','B'],
        'assets':[{'id':str(i),'venue':'v','payoffs':{'A':100 if i==0 else 0,'B':0 if i==0 else 100},
                   'asks':[dict(price=p,depth=q,fee_upper=f) for p,q,f in ladder]} for i,ladder in enumerate(levels)]})


def raw_book():
    return {'asset_id':'1','market':'c','timestamp':'10000','hash':'a','min_order_size':'1','tick_size':'0.01',
            'asks':[{'price':'0.60','size':'50'},{'price':'0.40','size':'50'}],
            'bids':[{'price':'0.30','size':'50'}]}


class ExactEvidenceTests(unittest.TestCase):
    def test_only_public_get_urls_admitted(self):
        self.assertTrue(allowed_url('https://clob.polymarket.com/book?token_id=123'))
        for url in ['https://clob.polymarket.com/order','http://clob.polymarket.com/book',
                    'https://evil.invalid/book','https://x:secret@clob.polymarket.com/book',
                    'https://gamma-api.polymarket.com/positions','https://clob.polymarket.com:444/book']:
            self.assertFalse(allowed_url(url))

    def test_exact_decimal_rejects_float_bool_nan(self):
        self.assertEqual(rational('0.123456'),F(1929,15625))
        self.assertEqual(units('0.000001'),1)
        for bad in [0.2,True,'NaN','Infinity','1e-2']:
            with self.assertRaises(ValueError): rational(bad)
        with self.assertRaises(ValueError): units('0.0000001')

    def test_book_uses_both_identity_and_native_constraints(self):
        b=parse_book(raw_book(),'1','c')
        self.assertEqual(b['asks'][0],(F(2,5),F(50)))
        with self.assertRaises(ValueError): parse_book(raw_book(),'2','c')
        b=raw_book();b['tick_size']='0'
        with self.assertRaises(ValueError): parse_book(b,'1','c')

    def test_missing_depth_cannot_be_filled_with_last_trade(self):
        b=raw_book();b['asks']=[];b['last_trade_price']='0.01'
        with self.assertRaisesRegex(ValueError,'empty ask'): parse_book(b,'1','c')
        b=raw_book();b['asks'].append(b['asks'][0])
        with self.assertRaises(ValueError): parse_book(b,'1','c')

    def test_alignment_rejects_errors_skew_staleness(self):
        r={'status':200,'error':None,'method':'GET','started_ns':10_000_000_000,'received_ns':11_000_000_000,'duration_ns':1_000_000_000}
        b={'timestamp_ns':10_000_000_000}
        self.assertEqual(alignment([r],[b]),1_000_000_000)
        for bad in [{**r,'status':404},{**r,'error':'missing'}, {**r,'received_ns':9_000_000_000}]:
            with self.assertRaises(ValueError): alignment([bad],[b])
        with self.assertRaises(ValueError): alignment([r,{**r,'started_ns':30_000_000_000,'received_ns':31_000_000_000}],[b,{'timestamp_ns':30_000_000_000}])
        with self.assertRaises(ValueError): alignment([r],[{'timestamp_ns':-150_000_000_000}])

    def test_rule_changes_invalidate_but_not_prices(self):
        event={'id':'e','markets':[{'id':'1','description':'r','outcomePrices':['0.4','0.6']}]}
        key=rule_identity(event)
        event['markets'][0]['outcomePrices']=['0.3','0.7']
        self.assertEqual(rule_identity(event),key)
        event['markets'][0]['description']='different rule'
        self.assertNotEqual(rule_identity(event),key)
        with self.assertRaises(ValueError): rule_identity(event,['missing'])

    def test_unknown_fees_are_not_zero(self):
        self.assertEqual(fee_posture([{}])['status'],'MATCH_FEE_BOUND_UNQUALIFIED')
        self.assertEqual(fee_posture([{'feesEnabled':False}])['status'],'EXPLICIT_ZERO_METADATA_ONLY')
        with self.assertRaises(ValueError): fee_posture([{'feesEnabled':False,'feeSchedule':{'rate':'0.05'}}])

    def test_byte_tampering_and_digest_traversal_rejected(self):
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'raw').mkdir();body=b'{}';h=sha256(body).hexdigest();(p/'raw'/f'{h}.bin').write_bytes(body)
            r={'body_sha256':h,'bytes':2,'label':'a','method':'GET','url':'https://clob.polymarket.com/book','started_ns':1,'received_ns':2}
            (p/'requests.jsonl').write_text(json.dumps(r)+'\n');Evidence(p)
            (p/'raw'/f'{h}.bin').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError,'integrity'): Evidence(p)
            r['body_sha256']='../secret';(p/'requests.jsonl').write_text(json.dumps(r)+'\n')
            with self.assertRaises(ValueError): Evidence(p)


class PriceWitnessTests(unittest.TestCase):
    def test_binary_and_partition_witness(self):
        w=partition_witness([F('0.51')],[F('0.51')],binary=True)
        self.assertTrue(verify_witness([(F(1),F(0)),(F(0),F(1))],[F('.51'),F('.51')],w))
        self.assertIsNone(partition_witness([F('.4')],[F('.5')],binary=True))
        yes=[F('.25'),F('.35'),F('.45')];no=[F('.8'),F('.7'),F('.6')]
        _,p=payoff_matrix({'markets':[{}, {}, {}]});w=partition_witness(yes,no)
        asks=[x for pair in zip(yes,no) for x in pair];self.assertTrue(verify_witness(p,asks,w))

    def test_forged_witness_never_passes(self):
        p=[(F(1),F(0)),(F(0),F(1))];a=[F('.4'),F('.4')]
        for w in [(),(F(1),),(F('.5'),F('.5')),(F(-1),F(2)),(0.5,0.5)]:
            self.assertFalse(verify_witness(p,a,w))
        self.assertFalse(verify_witness(p,[.4,.4],(F('.5'),F('.5'))))

    def test_three_no_group_and_fee_scenario(self):
        yes=[F('.4')]*3;no=[F('.6')]*3
        self.assertIsNone(partition_witness(yes,no)) # sum lower probabilities=1.2
        self.assertEqual(partial_fill_floor([(F(0),F(1)),(F(1),F(0))],[1,1],[F('.4'),F('.4')])['worst_floor'],'-2/5')
        markets=[{'feesEnabled':True,'feeSchedule':{'exponent':1,'takerOnly':True,'rate':'0.05'}}]
        self.assertEqual(nominal_fee_asks(markets,[F('.49'),F('.50')]),[F('.502495'),F('.5125')])

    def test_witness_random_consistent_models_300(self):
        rng=random.Random(711)
        for _ in range(300):
            n=rng.randint(2,6);p=[rng.randint(1,100) for _ in range(n)];total=sum(p)
            probs=[F(x,total) for x in p];yes=[min(F(1),x+F(rng.randint(0,5),100)) for x in probs]
            no=[min(F(1),1-x+F(rng.randint(0,5),100)) for x in probs]
            states,pays=payoff_matrix({'markets':[{}]*n});asks=[x for pair in zip(yes,no) for x in pair]
            w=partition_witness(yes,no);self.assertIsNotNone(w);self.assertTrue(verify_witness(pays,asks,w))


class BaselineTests(unittest.TestCase):
    def test_analytic_top_equals_original_60(self):
        rng=random.Random(55)
        for _ in range(60):
            m=model([[(rng.randint(1,90),rng.randint(1,5),rng.randint(0,4))] for _ in range(2)])
            self.assertEqual(equal_size_frontier(m).lower_floor,top_of_book_equal_size_baseline(m).lower_floor)

    def test_depth_frontier_equals_independent_exhaustive_equal_80(self):
        rng=random.Random(81)
        for _ in range(80):
            ladders=[]
            for i in range(2):
                lo=rng.randint(1,70); ladders.append([(lo,rng.randint(1,4),rng.randint(0,4)),(rng.randint(lo+1,99),rng.randint(1,4),rng.randint(0,4))])
            m=model(ladders);best=0
            for mask in range(1,4):
                ids=[i for i in range(2) if mask&(1<<i)]
                for q in range(1,min(sum(l.depth for l in m.assets[i].levels) for i in ids)+1):
                    cost=0
                    for i in ids:
                        cap,fee=0,0
                        for l in m.assets[i].levels:
                            cap+=l.depth;fee=max(fee,l.fee_upper)
                            if cap>=q: cost+=q*(l.ask+fee);break
                    if cost>m.budget:continue
                    floor=min(sum(m.assets[i].payoff[k]*q for i in ids) for k in range(2))-cost
                    best=max(best,floor)
            self.assertEqual(equal_size_depth_frontier(m).lower_floor,best)
            self.assertGreaterEqual(solve_maximin(m).lower_floor,best)

    def test_minimum_order_size_not_silently_included(self):
        book=parse_book(raw_book(),'1','c');self.assertEqual(book['min_order_size'],1)
        del_val=raw_book();del del_val['min_order_size']
        with self.assertRaises(KeyError):parse_book(del_val,'1','c')


class ExecutionTests(unittest.TestCase):
    def test_vwap_is_not_limit_fok(self):
        ladder=((F('.4'),F(50)),(F('.6'),F(50)))
        self.assertIsNone(walk_limit(ladder,100,F('.5')))
        self.assertEqual(walk_limit(ladder,100,F('.6')),50)
        for q in [0,-1,True]:
            with self.assertRaises(ValueError):walk_limit(ladder,q,F('.6'))

    def test_duplicate_and_unsorted_ladders_rejected(self):
        for ladder in [((F('.6'),F(5)),(F('.4'),F(5))),((F('.4'),F(5)),(F('.4'),F(5)))]:
            with self.assertRaises(ValueError):walk_limit(ladder,5,F('.6'))

    def test_account_no_double_count_and_no_invented_profit(self):
        # S1 source model uses SCALE=100 here; replay requires 1e6 model.
        pays=[(F(1),F(0)),(F(0),F(1))];books=[{'hash':str(i),'asks':((F('.4'),F(10)),)} for i in range(2)]
        m=model_from_books('test',['A','B'],['a','b'],pays,books,budget_units=10*SCALE)
        p=solve_maximin(m);ledger=SampledLedger(F(10));by=dict(zip(['a','b'],books))
        result=ledger.apply('f',p,by);self.assertEqual(result['status'],'ALL_FILLED');self.assertIsNone(result['realized_profit'])
        self.assertEqual(ledger.cash,2);self.assertEqual(ledger.apply('f',p,by)['status'],'FAMILY_ALREADY_ATTEMPTED')
        rich=SampledLedger(F(100));rich.apply('f',p,by);self.assertEqual(rich.apply('different',p,by)['status'],'REUSED_DEPTH')

    def test_independent_fok_can_leave_partial_inventory(self):
        pays=[(F(1),F(0)),(F(0),F(1))];books=[{'hash':str(i),'asks':((F('.4'),F(10)),)} for i in range(2)]
        p=solve_maximin(model_from_books('test',['A','B'],['a','b'],pays,books,budget_units=10*SCALE))
        books[1]={'hash':'new','asks':((F('.6'),F(10)),)};ledger=SampledLedger(F(10))
        result=ledger.apply('f',p,dict(zip(['a','b'],books)))
        self.assertEqual(result['status'],'PARTIAL');self.assertEqual(ledger.inventory,{'a':10});self.assertEqual(ledger.cash,6)


    def test_account_queue_is_chronological_and_reserves_inflight(self):
        pays=[(F(1),F(0)),(F(0),F(1))];books=[{'hash':str(i),'asks':((F('.4'),F(10)),)} for i in range(2)]
        p=solve_maximin(model_from_books('test',['A','B'],['a','b'],pays,books,budget_units=10*SCALE))
        rows=[{},{}]
        early={'name':'s1','family_id':'a','proposal':p,'books':dict(zip(['a','b'],books)),
               'row':rows[0],'decision_ns':10,'execution_ns':30}
        intervening={**early,'family_id':'b','row':rows[1],'decision_ns':20,'execution_ns':40}
        accounts=process_replays([intervening,early])
        self.assertEqual(rows[0]['s1_sampled_account']['status'],'ALL_FILLED')
        self.assertEqual(rows[1]['s1_sampled_account']['status'],'PRIOR_ORDER_IN_FLIGHT')
        self.assertEqual(accounts['s1'].cash,992)

    def test_account_rejection_is_transactional(self):
        pays=[(F(1),F(0)),(F(0),F(1))];books=[{'hash':str(i),'asks':((F('.4'),F(10)),)} for i in range(2)]
        p=solve_maximin(model_from_books('test',['A','B'],['a','b'],pays,books,budget_units=10*SCALE))
        bad=replace(p,buys=(replace(p.buys[0],conservative_debit=1),p.buys[1]),capital_required=1+p.buys[1].conservative_debit)
        ledger=SampledLedger(F(10))
        with self.assertRaises(ValueError):ledger.apply('bad',bad,dict(zip(['a','b'],books)))
        self.assertEqual(ledger.cash,10);self.assertEqual(ledger.inventory,{})


if __name__=='__main__':unittest.main()

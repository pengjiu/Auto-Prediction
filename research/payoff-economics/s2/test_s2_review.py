import unittest, copy
from fractions import Fraction as F
from dataclasses import replace
from economics import *
from analyze import nominal_fee_asks

def book(token):
    return {"asset_id":token,"hash":token,"asks":((F(".4"),F(10)),),
            "min_order_size":F(1),"tick_size":F(".01")}

class ReviewTests(unittest.TestCase):
    def test_vector_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            model_from_books("e",["A","B"],["a","b"],[(F(1),F(0))],[book("a"),book("b")])
    def test_fractional_payment_not_truncated(self):
        with self.assertRaises(ValueError):
            model_from_books("e",["A"],["a"],[(F(1,3),)],[book("a")])
    def test_event_rule_changes_invalidate_identity(self):
        e={"id":"e","description":"old","markets":[{"id":"m"}]}
        h=rule_identity(e);e["description"]="new"
        self.assertNotEqual(h,rule_identity(e))
    def test_contradictory_fees_cannot_bypass_nominal_path(self):
        with self.assertRaises(ValueError):
            nominal_fee_asks([{"feesEnabled":False,"feeSchedule":{"rate":"0.1"}}],[F(".4"),F(".6")])
    def test_fee_dimensions_not_silently_zipped(self):
        with self.assertRaises(ValueError): nominal_fee_asks([{"feesEnabled":False}],[F(".4")])
    def test_common_decision_time_freshness(self):
        recs=[{"status":200,"error":None,"method":"GET","started_ns":120_000_000_000,
               "received_ns":120_100_000_000,"duration_ns":100_000_000},
              {"status":200,"error":None,"method":"GET","started_ns":124_000_000_000,
               "received_ns":124_100_000_000,"duration_ns":100_000_000}]
        with self.assertRaises(ValueError): alignment(recs,[{"timestamp_ns":100_000_000},{"timestamp_ns":124_000_000_000}])
    def test_changed_hash_does_not_refill_consumed_asset(self):
        books=[book("a"),book("b")]
        p=solve_maximin(model_from_books("e",["A","B"],["a","b"],[(F(1),F(0)),(F(0),F(1))],books))
        l=SampledLedger(F(100));l.apply("f",p,dict(zip(["a","b"],books)))
        updated={t:{**book(t),"hash":"new-"+t} for t in ["a","b"]}
        self.assertEqual(l.apply("g",p,updated)["status"],"REUSED_DEPTH")
    def test_native_minimum_change_rejected(self):
        books=[book("a"),book("b")]
        p=solve_maximin(model_from_books("e",["A","B"],["a","b"],[(F(1),F(0)),(F(0),F(1))],books))
        updated={t:{**book(t),"min_order_size":F(50)} for t in ["a","b"]}
        result=SampledLedger(F(100)).apply("f",p,updated)
        self.assertEqual(result["status"],"NO_FILL")

    def test_ledger_uses_proposal_scale_not_global_scale(self):
        m=parse_model({"coverage":"ASSUMED_STATES_ONLY","evidence_id":"e","states":["A","B"],
            "scale":100,"budget":160,"venue_budgets":{"v":160},"assets":[
            {"id":t,"venue":"v","payoffs":{"A":100 if i==0 else 0,"B":100 if i==1 else 0},
             "asks":[{"price":40,"depth":2,"fee_upper":0}]} for i,t in enumerate(["a","b"])]})
        p=solve_maximin(m);l=SampledLedger(F(10));result=l.apply("f",p,{t:book(t) for t in ["a","b"]})
        self.assertEqual(result["status"],"ALL_FILLED");self.assertEqual(l.cash,F("8.4"))

    def test_off_tick_order_is_not_executed(self):
        books=[book("a"),book("b")]
        p=solve_maximin(model_from_books("e",["A","B"],["a","b"],[(F(1),F(0)),(F(0),F(1))],books))
        updated={t:{**book(t),"tick_size":F(".3")} for t in ["a","b"]}
        self.assertEqual(SampledLedger(F(100)).apply("f",p,updated)["status"],"NO_FILL")

    def test_duplicate_selected_member_is_not_exhaustive(self):
        import tempfile,json
        from pathlib import Path
        from hashlib import sha256
        from analyze import Evidence
        markets=[{"id":str(i),"conditionId":"0x"+str(i)*64,"closed":False,"acceptingOrders":True,
                  "enableOrderBook":True,"description":"same retained fixture rules","outcomes":["Yes","No"],
                  "clobTokenIds":[str(i)+"1",str(i)+"2"]} for i in [1,2]]
        event={"id":"1","negRisk":True,"markets":markets}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'raw').mkdir();body=json.dumps([event]).encode();h=sha256(body).hexdigest()
            (root/'raw'/f'{h}.bin').write_bytes(body)
            rec={"label":"catalog:test","body_sha256":h,"bytes":len(body),"method":"GET","url":"https://gamma-api.polymarket.com/events",
                 "status":200,"error":None,"started_ns":1,"received_ns":2}
            (root/'requests.jsonl').write_text(json.dumps(rec)+'\n')
            selection={"catalog_events":1,"families":[{"kind":"NEG_RISK_ASSUMED_EXHAUSTIVE","event":event,"markets":[markets[0],markets[0]]}]}
            (root/'selection.json').write_text(json.dumps(selection))
            with self.assertRaises(ValueError): Evidence(root).selection()

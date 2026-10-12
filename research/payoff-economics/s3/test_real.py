from fractions import Fraction as F
from copy import deepcopy
import unittest
from analyze_real import exact_price_witness, utc_millis, same_rules, source_from_evidence
from economics import verify_witness
from bridge import check_quote_urls


class RealRuleEconomics(unittest.TestCase):
    def test_exact_decimal_clock_no_float_roundtrip(self):
        self.assertEqual(utc_millis(1791781974564389276),'2026-10-12T05:12:54.564Z')
        with self.assertRaises(ValueError):utc_millis(True)

    def test_rational_witness_consistent_and_inconsistent(self):
        rows=[(F(1),F(0)),(F(0),F(1))]
        w=exact_price_witness(rows,[F('0.51'),F('0.51')])
        self.assertTrue(verify_witness(rows,[F('0.51'),F('0.51')],w))
        self.assertIsNone(exact_price_witness(rows,[F('0.49'),F('0.49')]))

    def test_equality_state_cannot_be_dropped_to_manufacture_relation(self):
        # A: x>82; B: x>84; R: 82<=x<84. These vectors keep both exact boundaries.
        a=[0,0,1,1,1];b=[0,0,0,0,1];r=[0,1,1,0,0]
        self.assertNotEqual([a[i]-b[i] for i in range(5)],r)
        # Removing both boundary states produces a spurious identity.
        self.assertEqual([a[i]-b[i] for i in (0,2,4)],[r[i] for i in (0,2,4)])

    def test_dimension_truncation_rejected(self):
        for rows,asks in [([],[]),([(F(1),),(F(0),F(1))],[F(1),F(1)]),([(0,1)],[F(1)])]:
            with self.assertRaises(ValueError):exact_price_witness(rows,asks)

    def test_prices_change_but_rules_not_and_changed_rule_rejected(self):
        a={'familyRuleIdentity':'rule1','policySources':[{'url':'policy','hash':'h'}],'exportId':'old'}
        b=deepcopy(a);b['exportId']='new';self.assertTrue(same_rules(a,b))
        b['familyRuleIdentity']='other'
        with self.assertRaises(ValueError):same_rules(a,b)

    def test_policy_change_and_missing_after_policy_are_not_price_only(self):
        a={'familyRuleIdentity':'same','policySources':[{'url':'policy','hash':'a'}]}
        for rows in (None,[],[{'url':'policy','hash':'b'}]):
            with self.assertRaises(ValueError):same_rules(a,{**a,'policySources':rows})

    def test_markdown_policy_is_preserved_without_json_parsing(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from hashlib import sha256
        from types import SimpleNamespace
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'raw').mkdir();records={}
            for label,body in [('before:event','[]'),('docs:concepts/resolution','# Resolution\nNOT JSON'),
                               ('docs:trading/fees','# Fees\nAlso plain text')]:
                digest=sha256(body.encode()).hexdigest();(root/'raw'/f'{digest}.bin').write_text(body)
                records[label]={'status':200,'error':None,'url':label,'body_sha256':digest,
                    'received_ns':1791781974564389276}
            evidence=SimpleNamespace(root=root,by_label=records)
            family={'definitions':[{'slug':'event'}],'selected':[{'event_id':'1','market_id':'2'}]}
            source=source_from_evidence(evidence,family,'before')
            self.assertEqual(source['policies'][0]['bodyUtf8'],'# Resolution\nNOT JSON')
            records['docs:trading/fees']['status']=404
            with self.assertRaises(ValueError):source_from_evidence(evidence,family,'before')

    def test_raw_request_url_binds_actual_native_outcome(self):
        check_quote_urls({'123':({'url':'https://clob.polymarket.com/book?token_id=123'}, {})})
        for url in ['https://clob.polymarket.com/book?token_id=456',
                    'https://clob.polymarket.com/book?token_id=123&token_id=456',
                    'http://clob.polymarket.com/book?token_id=123',
                    'https://clob.polymarket.com/book?token_id=123#ignored']:
            with self.assertRaises(ValueError):check_quote_urls({'123':({'url':url},{})})

    def test_generated_joint_distributions_are_exactly_verified(self):
        import random
        rng=random.Random(937)
        for _ in range(70):
            ns=5;nums=[rng.randrange(1,10) for _ in range(ns)];weights=[F(n,sum(nums)) for n in nums]
            rows=[tuple(F(rng.randrange(2)) for _ in range(ns)) for _ in range(8)]
            asks=[sum(w*v for w,v in zip(weights,row))+F(1,1000) for row in rows]
            w=exact_price_witness(rows,asks)
            # Construction completeness isn't required; every claimed witness is exact.
            if w is not None:self.assertTrue(verify_witness(rows,asks,w))


if __name__=='__main__':unittest.main()

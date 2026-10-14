import unittest,json,tempfile
from pathlib import Path
from fractions import Fraction as F
from campaign import config,evaluate,witness,analyze

class Campaign(unittest.TestCase):
    def test_exact_price_witness(self):
        self.assertEqual(witness([(F(1),F(0)),(F(0),F(1))],[F(1,2),F(1,2)]),['1/2','1/2'])
        self.assertIsNone(witness([(F(1),F(0)),(F(0),F(1))],[F(2,5),F(2,5)]))
    def test_highorder_information_not_solver_gain(self):
        members=[];quotes={};markets=[]
        for i,(a,b) in enumerate([(0,10),(2,12),(4,14)]):
            tokens=[str(2*i+1),str(2*i+2)];condition='0x'+str(i+1)*64
            members.append({'marketId':str(i),'conditionId':condition,'tokens':tokens,'startNS':str(a),'endNS':str(b),'endMinuteNS':str(b)})
            markets.append({'feesEnabled':False})
            for yes,t in enumerate(tokens):
                cheap=(i in (0,2) and yes==0) or (i==1 and yes==1)
                quotes[t]=({'url':'https://clob.polymarket.com/book?token_id='+t,'method':'GET','status':200,'error':None,'started_ns':1000000000000,'received_ns':1000000000001,'duration_ns':1},
                  {'asset_id':t,'market':condition,'hash':'test','timestamp':'1000000','min_order_size':'1','tick_size':'0.01','asks':[{'price':'0.20' if cheap else '1','size':'2'}],'bids':[]})
        data={'schema':'s5.temporal-source.v1','eventId':'test','sourceHash':'synthetic','reviewScopeHash':'synthetic','members':members,'unknowns':['SYNTHETIC'],'certificateAuthority':False,'executionAuthority':False}
        out=evaluate(data,quotes,markets)
        self.assertGreater(out['semantic_increment'],0);self.assertEqual(out['algorithm_increment'],0)
        self.assertEqual(out['pairwise_only_control']['lower_floor'],0);self.assertEqual(out['independent_settlement_stress']['lower_floor'],0)
        self.assertIsNone(out['gross_witness'])
        with self.assertRaises(ValueError):evaluate(data,{**quotes,'999':quotes['1']},markets)
    def test_fixed_protocol_no_caller_redefinition(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);c=config();c['cycles']=3;(p/'config.json').write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,'configuration'):analyze(p)
    def test_absent_all_observations_preserves_denominator(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'config.json').write_text(json.dumps(config()));(p/'requests.jsonl').write_text('');(p/'raw').mkdir()
            out=analyze(p);self.assertEqual(out['summary']['attempted'],12);self.assertEqual(out['summary']['excluded'],12);self.assertEqual(out['summary']['admitted'],0);self.assertFalse(out['protocol_completed'])
if __name__=='__main__':unittest.main()

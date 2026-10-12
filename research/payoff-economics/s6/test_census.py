import json,copy,hashlib,tempfile,unittest,zipfile
from pathlib import Path
from census import census,blocks,load_catalog,projection

CLAUSE='A qualifying condition is determined by the exact same official metric, observation point and interval; all exceptions and source revisions remain part of this complete definition.'
def event(eid,title,desc=CLAUSE):
 return {'id':eid,'title':title,'description':desc,'markets':[{'id':eid+'01','question':title,'description':desc,
 'active':True,'closed':False,'archived':False,'acceptingOrders':True,'enableOrderBook':True}]}
class CensusTests(unittest.TestCase):
 def test_shared_rule_candidates_never_certify(self):
  r=census([event('1','Alpha A'),event('2','Beta B')]);self.assertEqual(r['summary']['shared_block_candidate_pairs'],1)
  c=r['block_candidates'][0];self.assertFalse(c['semantic_certificate']);self.assertFalse(c['execution_authority'])
 def test_price_fields_do_not_change_routing_or_identity(self):
  es=[event('1','Alpha A'),event('2','Alpha B')];before=census(es)
  for e in es:e['liquidity']=999;e['markets'][0].update(bestAsk='0.01',outcomePrices='[0.99,0.01]',volume=99999)
  self.assertEqual(before,census(es))
 def test_order_invariance(self):
  es=[event(str(i),'Alpha '+str(i)) for i in range(1,6)];self.assertEqual(census(es),census(es[::-1]))
 def test_raw_spans_are_original_text(self):
  body='  Intro\n\n'+CLAUSE+'\n\n'+CLAUSE.replace('metric','measure')+'\n'
  for norm,span in blocks(body):
   raw=body[span['start']:span['end']];self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),span['raw_sha256']);self.assertEqual(' '.join(raw.split()),norm)
 def test_numbers_negation_units_are_not_erased(self):
  for changed in [CLAUSE.replace('same','different'),CLAUSE+' Threshold 25 C.',CLAUSE+' NOT.']:
   self.assertEqual(census([event('1','A',CLAUSE),event('2','B',changed)])['summary']['shared_block_candidate_pairs'],0)
 def test_identical_texts_not_independent_rules(self):
  r=census([event('1','A'),event('2','B')]);self.assertEqual(r['summary']['unique_market_ids'],2);self.assertEqual(r['summary']['distinct_market_rule_texts'],1)
 def test_duplicates_and_budget_rejected(self):
  with self.assertRaises(ValueError):census([event('1','A'),event('1','B')])
  with self.assertRaises(ValueError):census([event('1','A')],True)
 def test_market_order_and_identity(self):
  e=event('1','A');e['markets']*=2
  with self.assertRaises(ValueError):projection(e)
 def archive(self,root,pages):
  path=root/'synthetic.zip';rs=[]
  with zipfile.ZipFile(path,'w') as z:
   for i,page in enumerate(pages):
    raw=json.dumps(page).encode();h=hashlib.sha256(raw).hexdigest();z.writestr(f'public-evidence/raw/{h}.bin',raw)
    rs.append({'label':f'catalog:{i}','url':f'https://gamma-api.polymarket.com/events?limit=10&offset={i*10}','method':'GET','status':200,'error':None,'body_sha256':h,'bytes':len(raw),'started_ns':1,'received_ns':2})
   z.writestr('public-evidence/requests.jsonl','\n'.join(map(json.dumps,rs)))
  return path,hashlib.sha256(path.read_bytes()).hexdigest()
 def test_raw_catalog_and_conflict_exclusion(self):
  changed=event('1','A');changed['description']+=' A changed policy.'
  with tempfile.TemporaryDirectory() as t:
   p,h=self.archive(Path(t),[[event('1','A'),event('2','B')],[changed]])
   es,meta=load_catalog(p,h);self.assertEqual([e['id'] for e in es],['2']);self.assertEqual(meta['conflicting_event_ids'],['1'])
 def test_original_zip_digest_required(self):
  with tempfile.TemporaryDirectory() as t:
   p,h=self.archive(Path(t),[[event('1','A')]])
   with self.assertRaises(ValueError):load_catalog(p,'0'*64)
if __name__=='__main__':unittest.main()

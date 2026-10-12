"""Synthetic IO tests isolate chronology/population; not semantic-review evidence."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import campaign as c
from factor import truth_states

class CampaignTests(unittest.TestCase):
 def setup_input(self,root):
  events=[];members=[]
  for s in c.REVIEW['scope']:
   e=copy.deepcopy(s);e['markets']=copy.deepcopy(e.pop('members'))
   for m in e['markets']:
    m.update(description=s['description'],active=True,closed=False,archived=False,acceptingOrders=True,enableOrderBook=True,feesEnabled=False)
    members.append({'marketId':m['id'],'eventId':e['id'],'conditionId':m['conditionId'],'tokens':json.loads(m['clobTokenIds']),'endNS':'9999999999999999999'})
   events.append(e)
  def rec(label,url,started,received):return {'label':label,'url':url,'started_ns':started,'received_ns':received,'duration_ns':received-started,'status':200,'error':None,'method':'GET'}
  store={}
  for phase,start in [('before',1_000_000_000),('after',9_000_000_000)]:
   for e in events:
    label=phase+':'+e['id'];store[label]=(rec(label,c.GAMMA+'/events/'+e['id'],start,start+1),e)
  for p in ['concepts/resolution','trading/fees']:
   label='docs:'+p;store[label]=(rec(label,'https://docs.polymarket.com/'+p+'.md',100,101),None)
  for cycle in range(4):
   for m in members:
    for t in m['tokens']:
     label=f'book:{cycle}:{t}';stamp=2_000_000_000+cycle*1_000_000_000
     r=rec(label,c.CLOB+'/book?token_id='+t,stamp,stamp+10_000_000)
     idx=c.TOKENS.index(t);ask=['0.40','0.75','0.40','0.75','0.20','0.95','0.20','0.95'][idx]
     book={'market':m['conditionId'],'asset_id':t,'hash':'synthetic','timestamp':str(stamp//1_000_000),'min_order_size':'5','tick_size':'0.01',
           'asks':[{'price':ask,'size':'10'}],'bids':[]}
     store[label]=(r,book)
  class EV:
   def __init__(self,unused):self.records=[r for r,_ in store.values()];self.by_label={k:r for k,(r,_) in store.items()};self.digest='SYNTHETIC_IO_NOT_CAPTURE'
   def read(self,k):return store[k]
  data={'schema':'s6.factor-source.v1','certificateAuthority':False,'executionAuthority':False,'sourceHash':'synthetic',
    'reviewScopeHash':'TEST_ONLY','members':members,'states':[{'truth':list(s)} for s in truth_states()],'unknowns':['SYNTHETIC_TEST']}
  (root/'config.json').write_text(json.dumps(c.config()));(root/'completion.json').write_text(json.dumps({'config':c.config(),'requests':len(store),'finished_ns':10_000_000_000}))
  return store,EV,data
 def run_case(self,mutate=None):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);store,ev,data=self.setup_input(root)
   if mutate:mutate(store,root)
   with patch.object(c,'Evidence',ev),patch.object(c,'compile_source',lambda x:copy.deepcopy(data)):
    return c.analyze(root)
 def test_complete_zero_edge_control(self):
  r=self.run_case();self.assertTrue(r['protocol_completed']);self.assertEqual(r['summary'],{'attempted':4,'admitted':4,'excluded':0,'positive_gross':0,'algorithm_improvements':0,'semantic_improvements':0,'gross_witnesses':4})
 def test_missing_round_keeps_denominator(self):
  def change(s,r):
   for k in list(s):
    if k.startswith('book:3:'):del s[k]
  r=self.run_case(change);self.assertEqual(r['summary']['attempted'],4);self.assertEqual(r['summary']['admitted'],3);self.assertFalse(r['protocol_completed'])
 def test_unavailable_source_excludes_all(self):
  r=self.run_case(lambda s,p:s.pop('before:'+c.EIDS[0]));self.assertEqual(r['summary']['excluded'],4)
 def test_future_policy_not_used(self):
  def change(s,p):s['docs:trading/fees'][0]['received_ns']=20_000_000_000
  self.assertEqual(self.run_case(change)['summary']['excluded'],4)
 def test_bad_native_url(self):
  def change(s,p):s['book:0:'+c.TOKENS[0]][0]['url']=c.CLOB+'/book?token_id=1'
  r=self.run_case(change);self.assertEqual(r['summary']['admitted'],3)
 def test_unplanned_observation_rejected(self):
  def change(s,p):s['other:0']=next(iter(s.values()))
  with self.assertRaises(ValueError):self.run_case(change)
 def test_missing_completion_never_claimed_complete(self):
  r=self.run_case(lambda s,p:(p/'completion.json').unlink());self.assertFalse(r['protocol_completed']);self.assertEqual(r['summary']['attempted'],4)
 def test_changed_config_rejected(self):
  def change(s,p):(p/'config.json').write_text('{}')
  with self.assertRaises(ValueError):self.run_case(change)
if __name__=='__main__':unittest.main()

"""One preregistered joint/marginal experiment. Anonymous capture, offline replay.

Catalogs select source identities, never prices. Complete source is recompiled by
TypeScript. Normal composition is conditional; independent resolutions stay stress.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from fractions import Fraction as F
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess,sys,tempfile,time
from urllib.parse import urlencode
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
for part in ('s5','s3','s2'):sys.path.insert(0,str(HERE.parent/part))
from capture import Capture,GAMMA,CLOB,market_tokens
from analyze import Evidence
from economics import alignment,parse_book,model_from_books,solve_maximin,equal_size_depth_frontier,nominal_rate,verify_witness,partial_fill_floor
from bridge import check_quote_urls
from factor import rows,pairwise_relaxation,truth_states
REVIEW=json.loads((HERE/'reviewed-factor.json').read_text())
EIDS=[e['id'] for e in REVIEW['scope']]
TOKENS=[t for e in REVIEW['scope'] for m in e['members'] for t in json.loads(m['clobTokenIds'])]
PLAN=ROOT/'plans/relation-coverage-census.md'

def config():
 return {'schema':'s6.factor-capture.v1','cycles':4,'target_interval_seconds':2,'event_ids':EIDS,'tokens':TOKENS,
 'plan_sha256':sha256(PLAN.read_bytes()).hexdigest(),'review_sha256':sha256((HERE/'reviewed-factor.json').read_bytes()).hexdigest(),
 'authority':'READ_ONLY_RESEARCH','selection_replaces_missing':False,'live_execution':False}

def compile_source(events):
 with tempfile.TemporaryDirectory(prefix='s6-factor-') as td:
  src,out=Path(td)/'input.json',Path(td)/'output.json';src.write_text(json.dumps(events))
  p=subprocess.run([str(ROOT/'packages/control-plane/node_modules/.bin/tsx'),str(HERE/'export.ts'),str(src),str(out)],
   cwd=ROOT,text=True,capture_output=True,timeout=60)
  if p.returncode:raise ValueError('source compiler rejected: '+p.stderr[-1200:])
  return json.loads(out.read_text())

def capture(root):
 cap=Capture(root);cap.save('config.json',config());events=[];records=[]
 for path in ('concepts/resolution','trading/fees'):cap.get('https://docs.polymarket.com/'+path+'.md','docs:'+path)
 for eid in EIDS:
  r,e=cap.get(GAMMA+'/events/'+eid,'before:'+eid);records.append(r);events.append(e)
 tokens=[];blocker=None
 try:
  if any(r['status']!=200 or r['error']is not None for r in records):raise ValueError('source GET failed')
  data=compile_source(events)
  if any(int(m['endNS'])<=max(r['received_ns'] for r in records) for m in data['members']):raise ValueError('expired fixed member')
  tokens=TOKENS
 except (ValueError,KeyError,TypeError) as exc:blocker=str(exc)
 for cycle in range(4):
  start=time.monotonic()
  with ThreadPoolExecutor(max_workers=4) as pool:
   list(pool.map(lambda t:cap.get(CLOB+'/book?'+urlencode({'token_id':t}),f'book:{cycle}:{t}'),tokens))
  if cycle<3:time.sleep(max(0,2-(time.monotonic()-start)))
 for eid in EIDS:cap.get(GAMMA+'/events/'+eid,'after:'+eid)
 cap.save('completion.json',{'config':config(),'finished_ns':time.time_ns(),'requests':len(cap.records),'source_blocker':blocker})

def witness(payoffs,asks):
 from scipy.optimize import linprog
 p=linprog([0.0]*len(payoffs[0]),A_ub=[[float(x) for x in r] for r in payoffs],b_ub=list(map(float,asks)),
  A_eq=[[1.0]*len(payoffs[0])],b_eq=[1.0],bounds=(0,None),method='highs')
 if not p.success:return None
 weights=[F(float(x)).limit_denominator(10**8) for x in p.x]
 if sum(weights)<=0:return None
 weights=[w/sum(weights) for w in weights]
 return list(map(str,weights)) if verify_witness(payoffs,asks,weights) else None

def evaluate(data,quotes,markets):
 if (data.get('schema')!='s6.factor-source.v1' or data.get('certificateAuthority')is not False
  or data.get('executionAuthority')is not False or [s['truth'] for s in data['states']]!=[list(s) for s in truth_states()]):
  raise ValueError('source export mismatch')
 if set(quotes)!=set(TOKENS) or len(markets)!=4:raise ValueError('quote/market population')
 if [t for m in markets for t in market_tokens(m)]!=TOKENS:raise ValueError('fee market native identity')
 check_quote_urls(quotes);records=[quotes[t][0] for t in TOKENS]
 books=[parse_book(quotes[t][1],t,m['conditionId']) for m in data['members'] for t in m['tokens']]
 span=alignment(records,books);states=[s['truth'] for s in data['states']];payoffs=rows(states)
 def solve(p,name):
  model=model_from_books(data['reviewScopeHash']+name,[str(i) for i in range(len(p[0]))],TOKENS,p,books)
  return model,solve_maximin(model)
 model,s1=solve(payoffs,':joint');base=equal_size_depth_frontier(model)
 relax=pairwise_relaxation(states);_,pair=solve(rows(relax),':pairwise')
 _,stress=solve(rows(list(product((F(0),F(1,2),F(1)),repeat=4))),':independent')
 asks=[b['asks'][0][0] for b in books];rates=[nominal_rate(m) for m in markets]
 fw=None if any(r is None for r in rates) else witness(payoffs,[p+rates[i//2]*p*(1-p) for i,p in enumerate(asks)])
 idx=[TOKENS.index(b.asset_id) for b in s1.buys]
 return {'s1':asdict(s1),'same_depth_baseline':asdict(base),'pairwise_control':asdict(pair),
 'algorithm_increment':s1.lower_floor-base.lower_floor,'semantic_increment':s1.lower_floor-pair.lower_floor,
 'gross_witness':witness(payoffs,asks),'nominal_fee_witness':fw,'best_asks':list(map(str,asks)),
 'normal_states':states,'pairwise_states':relax,'independent_stress':asdict(stress),'acquisition_span_ns':span,
 'partial_fill_stress':None if not idx else partial_fill_floor([payoffs[i] for i in idx],[b.quantity for b in s1.buys],[F(b.conservative_debit,model.scale) for b in s1.buys]),
 'scale':model.scale,'source_identity':data['reviewScopeHash'],'unknowns':data['unknowns'],'actual_fee_qualified':False,
 'cashflow':'UNDISCOUNTED_TERMINAL_EXCLUDING_FINANCING','realized_profit':None}

def analyze(root):
 root=Path(root)
 if json.loads((root/'config.json').read_text())!=config():raise ValueError('unexpected experiment')
 ev=Evidence(root);allowed={f'{p}:{eid}' for p in ('before','after') for eid in EIDS}|{'docs:concepts/resolution','docs:trading/fees'}
 allowed|={f'book:{c}:{t}' for c in range(4) for t in TOKENS}
 if set(ev.by_label)-allowed:raise ValueError('unplanned observation')
 done=json.loads((root/'completion.json').read_text()) if (root/'completion.json').exists() else None
 complete=isinstance(done,dict) and done.get('config')==config() and done.get('requests')==len(ev.records) and type(done.get('finished_ns'))is int and bool(ev.records) and done['finished_ns']>=max(r['received_ns'] for r in ev.records)
 results=[];exclusions=[];source=None
 try:
  pairs={p:[ev.read(f'{p}:{eid}') for eid in EIDS] for p in ('before','after')}
  for p in pairs:
   if any(r['url']!=GAMMA+'/events/'+eid for (r,_),eid in zip(pairs[p],EIDS)):raise ValueError('rule URL mismatch')
  data=compile_source([e for _,e in pairs['before']]);later=compile_source([e for _,e in pairs['after']])
  if {k:v for k,v in data.items() if k!='sourceHash'}!={k:v for k,v in later.items() if k!='sourceHash'}:raise ValueError('reviewed source changed')
  selected=lambda p:[next(m for r,e in pairs[p] if e['id']==d['eventId'] for m in e['markets'] if m['id']==d['marketId']) for d in data['members']]
  markets=selected('before');after=selected('after')
  if [(m.get('feesEnabled'),m.get('feeSchedule')) for m in markets]!=[(m.get('feesEnabled'),m.get('feeSchedule')) for m in after]:raise ValueError('fees changed')
  policies=[ev.by_label['docs:'+p] for p in ('concepts/resolution','trading/fees')]
  for rec,p in zip(policies,('concepts/resolution','trading/fees')):
   if rec['url']!='https://docs.polymarket.com/'+p+'.md' or rec['status']!=200 or rec['error']is not None:raise ValueError('policy unavailable')
  source=data;previous=0
  for c in range(4):
   try:
    quotes={t:ev.read(f'book:{c}:{t}') for t in TOKENS};start=min(r['started_ns'] for r,_ in quotes.values());decision=max(r['received_ns'] for r,_ in quotes.values())
    if start<previous:raise ValueError('overlapping rounds')
    previous=decision
    for r in policies+[r for r,_ in pairs['before']]:
     if not r['received_ns']<=start or not 0<=decision-r['received_ns']<=900_000_000_000:raise ValueError('source/policy not available then')
    if decision>min(r['started_ns'] for r,_ in pairs['after']) or any(int(m['endNS'])<=decision for m in data['members']):raise ValueError('post-source or expired quote')
    row=evaluate(data,quotes,markets);row['cycle']=c;results.append(row)
   except (ValueError,KeyError,TypeError) as exc:exclusions.append({'cycle':c,'reason':str(exc)})
 except (ValueError,KeyError,TypeError,StopIteration) as exc:
  exclusions=[{'cycle':c,'reason':str(exc)} for c in range(4)]
 return {'schema':'s6.factor-results.v1','config':config(),'evidence_digest':ev.digest,'protocol_completed':complete,
 'source':source,'summary':{'attempted':4,'admitted':len(results),'excluded':len(exclusions),
 'positive_gross':sum(r['s1']['lower_floor']>0 for r in results),'algorithm_improvements':sum(r['algorithm_increment']>0 for r in results),
 'semantic_improvements':sum(r['semantic_increment']>0 for r in results),'gross_witnesses':sum(r['gross_witness']is not None for r in results)},
 'results':results,'exclusions':exclusions,'live_execution':False,'realized_profit':None,
 'authority':'CONDITIONAL_RESEARCH_ONLY_NOT_INDEPENDENT_SEMANTIC_REVIEW'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['capture','analyze']);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path)
 a=p.parse_args()
 if a.action=='capture':capture(a.root)
 else:
  if a.output is None:raise ValueError('output required')
  if a.output.exists():raise FileExistsError(a.output)
  r=analyze(a.root)
  with a.output.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
  print(json.dumps(r['summary']))
if __name__=='__main__':main()

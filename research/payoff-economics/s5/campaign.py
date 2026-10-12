"""Fixed source-reviewed temporal specimens. Capture is explicit; analyze is offline.

No trading, probability prediction, exact-semantic certification or provider API.
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
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'s2'))
sys.path.insert(0,str(HERE.parent/'s3'))
from capture import Capture, GAMMA, CLOB
from analyze import Evidence
from economics import (alignment, parse_book, model_from_books, solve_maximin,
    equal_size_depth_frontier, verify_witness, nominal_rate, partial_fill_floor, SCALE)
from bridge import check_quote_urls
from temporal import robust_histories,relation_report,payout_rows

SCOPES=json.loads((HERE/'reviewed-scopes.json').read_text())['scopes']
PLAN=ROOT/'plans/temporal-relation-discovery.md'

def config():
    return {'schema':'s5.temporal-capture.v1','families':[{ 'event_id':s['eventId'],'market_ids':[m['id'] for m in s['members']]} for s in SCOPES],
            'cycles':4,'interval_seconds':2,'plan_sha256':sha256(PLAN.read_bytes()).hexdigest(),
            'scope_sha256':sha256((HERE/'reviewed-scopes.json').read_bytes()).hexdigest(),
            'authority':'READ_ONLY_RESEARCH','selection_uses_prices':False,'live_execution':False}

def compile_source(event,eid):
    with tempfile.TemporaryDirectory(prefix='s5-source-') as td:
        inp,out=Path(td)/'input.json',Path(td)/'output.json'
        inp.write_text(json.dumps(event))
        tsx=ROOT/'packages/control-plane/node_modules/.bin/tsx'
        p=subprocess.run([str(tsx),str(HERE/'export.ts'),str(inp),eid,str(out)],cwd=ROOT,text=True,capture_output=True,timeout=60)
        if p.returncode:raise ValueError('source compiler rejected: '+p.stderr[-1800:])
        return json.loads(out.read_text())

def capture(root):
    cap=Capture(root);cap.save('config.json',config())
    for path in ('concepts/resolution','trading/fees'):cap.get('https://docs.polymarket.com/'+path+'.md','docs:'+path)
    tokens=set();exclusions=[]
    for s in SCOPES:
        eid=s['eventId'];rec,event=cap.get(GAMMA+'/events/'+eid,'before:'+eid)
        try:
            data=compile_source(event,eid)
            if any(int(m['endNS'])<=rec['received_ns'] for m in data['members']):raise ValueError('past deadline at capture')
            tokens.update(t for m in data['members'] for t in m['tokens'])
        except (ValueError,KeyError,TypeError) as exc:exclusions.append({'event_id':eid,'reason':str(exc)})
    if len(tokens)>18:raise ValueError('capture token bound')
    for cycle in range(4):
        start=time.monotonic()
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda t:cap.get(CLOB+'/book?'+urlencode({'token_id':t}),f'book:{cycle}:{t}'),sorted(tokens)))
        if cycle<3:time.sleep(max(0,2-(time.monotonic()-start)))
    for s in SCOPES:cap.get(GAMMA+'/events/'+s['eventId'],'after:'+s['eventId'])
    cap.save('completion.json',{'config':config(),'finished_ns':time.time_ns(),'requests':len(cap.records),'tokens':len(tokens),'source_exclusions':exclusions})

def witness(rows,asks):
    """Floating proposer; accept only exact Fraction verification by S2."""
    from scipy.optimize import linprog
    ans=linprog([0.0]*len(rows[0]),A_ub=[[float(x) for x in row] for row in rows],b_ub=[float(a) for a in asks],A_eq=[[1.0]*len(rows[0])],b_eq=[1.0],bounds=(0,None),method='highs')
    if not ans.success:return None
    weights=[F(float(x)).limit_denominator(10**8) for x in ans.x]
    if sum(weights)<=0:return None
    weights=[w/sum(weights) for w in weights]
    return [str(w) for w in weights] if verify_witness(rows,asks,weights) else None

def evaluate(data,quotes,markets):
    if data.get('schema')!='s5.temporal-source.v1' or data.get('certificateAuthority')is not False or data.get('executionAuthority')is not False:raise ValueError('invalid research export')
    members=data['members'];tokens=[t for m in members for t in m['tokens']]
    if set(quotes)!=set(tokens):raise ValueError('missing/extra quotes')
    check_quote_urls(quotes)
    records=[quotes[t][0] for t in tokens]
    books=[parse_book(quotes[t][1],t,m['conditionId']) for m in members for t in m['tokens']]
    span=alignment(records,books);states=robust_histories(members);relations=relation_report(members,states)
    masks=list(states);rows=payout_rows(masks,len(members))
    def solve(rows,name):
        model=model_from_books(data['reviewScopeHash']+name,[str(i) for i in range(len(rows[0]))],tokens,rows,books)
        return model,solve_maximin(model)
    model,s1=solve(rows,':history');baseline=equal_size_depth_frontier(model)
    pair_rows=payout_rows(relations['pairwise_masks'],len(members));_,pair=solve(pair_rows,':pairwise')
    stress_truth=list(product((F(0),F(1,2),F(1)),repeat=len(members)))
    stress_rows=[tuple(s[i] if yes else 1-s[i] for s in stress_truth) for i in range(len(members)) for yes in (True,False)]
    _,stress=solve(stress_rows,':independent')
    asks=[b['asks'][0][0] for b in books]
    rates=[nominal_rate(m) for m in markets]
    fee_witness=None if any(r is None for r in rates) else witness(rows,[p+rates[i//2]*p*(1-p) for i,p in enumerate(asks)])
    selected=[tokens.index(b.asset_id) for b in s1.buys]
    partial=None if not selected else partial_fill_floor([rows[i] for i in selected],[b.quantity for b in s1.buys],[F(b.conservative_debit,model.scale) for b in s1.buys])
    return {'event_id':data['eventId'],'source_hash':data['sourceHash'],'review_scope_hash':data['reviewScopeHash'],
        'scale':model.scale,'members':members,'normal_masks':masks,'normal_state_count':len(states),'relations':relations,
        's1':asdict(s1),'same_depth_baseline':asdict(baseline),'pairwise_only_control':asdict(pair),
        'algorithm_increment':s1.lower_floor-baseline.lower_floor,'semantic_increment':s1.lower_floor-pair.lower_floor,
        'gross_witness':witness(rows,asks),'nominal_fee_witness':fee_witness,'fee_status':'UNQUALIFIED_ACTUAL_DEBITS',
        'independent_settlement_stress':asdict(stress),'partial_fill_stress':partial,'acquisition_span_ns':span,
        'quote_decision_ns':max(r['received_ns'] for r in records),'unknowns':data['unknowns'],
        'cashflow_model':'UNDISCOUNTED_TERMINAL_PAYMENT_AFTER_LAST_DEADLINE_EXCLUDING_FINANCING',
        'latest_deadline_ns':max(int(m['endMinuteNS']) for m in members)}

def analyze(root):
    root=Path(root)
    if json.loads((root/'config.json').read_text())!=config():raise ValueError('untrusted experiment configuration')
    evidence=Evidence(root)
    completion=json.loads((root/'completion.json').read_text()) if (root/'completion.json').exists() else None
    complete=isinstance(completion,dict) and completion.get('config')==config() and completion.get('requests')==len(evidence.records) and type(completion.get('finished_ns'))is int and bool(evidence.records) and completion['finished_ns']>=max(r['received_ns'] for r in evidence.records)
    allowed={f'{phase}:{s["eventId"]}' for s in SCOPES for phase in ('before','after')}|{'docs:concepts/resolution','docs:trading/fees'}
    allowed|={f'book:{c}:{t}' for s in SCOPES for m in s['members'] for t in json.loads(m['clobTokenIds']) for c in range(4)}
    if set(evidence.by_label)-allowed:raise ValueError('unplanned observation')
    results=[];excluded=[];reviews=[]
    for scope in SCOPES:
        eid=scope['eventId']
        try:
            rb,event=evidence.read('before:'+eid);ra,after=evidence.read('after:'+eid)
            if rb['url']!=GAMMA+'/events/'+eid or ra['url']!=rb['url']:raise ValueError('source URL identity')
            data=compile_source(event,eid);later=compile_source(after,eid)
            if {k:v for k,v in data.items() if k!='sourceHash'}!={k:v for k,v in later.items() if k!='sourceHash'}:raise ValueError('changed reviewed interpretation')
            members=[next(m for m in event['markets'] if str(m['id'])==i['marketId']) for i in data['members']]
            am=[next(m for m in after['markets'] if str(m['id'])==i['marketId']) for i in data['members']]
            if [(m.get('feesEnabled'),m.get('feeSchedule')) for m in members]!=[(m.get('feesEnabled'),m.get('feeSchedule')) for m in am]:raise ValueError('changed fee metadata')
            reviews.append({'event_id':eid,'conditional_source_accepted':True,'source_received_ns':rb['received_ns'],'relation_report':relation_report(data['members'],robust_histories(data['members']))})
        except (ValueError,KeyError,TypeError,StopIteration) as exc:
            excluded +=[{'event_id':eid,'cycle':c,'reason':str(exc)} for c in range(4)];continue
        last_round_end=0
        for c in range(4):
            try:
                quotes={t:evidence.read(f'book:{c}:{t}') for m in data['members'] for t in m['tokens']}
                decision=max(r['received_ns'] for r,_ in quotes.values());started=min(r['started_ns'] for r,_ in quotes.values())
                if started<last_round_end:raise ValueError('overlapping or duplicated quote round')
                last_round_end=decision
                if not rb['received_ns']<=started<=decision<=ra['started_ns'] or decision-rb['received_ns']>900_000_000_000:raise ValueError('rules not available at decision')
                if any(int(m['endNS'])<=decision for m in data['members']):raise ValueError('past deadline')
                for path in ('concepts/resolution','trading/fees'):
                    rec=evidence.by_label['docs:'+path]
                    if rec['url']!='https://docs.polymarket.com/'+path+'.md' or rec['status']!=200 or rec['error']is not None or not 0<=decision-rec['received_ns']<=900_000_000_000:raise ValueError('policy unavailable at decision')
                result=evaluate(data,quotes,members);result['cycle']=c;results.append(result)
            except (ValueError,KeyError,TypeError) as exc:excluded.append({'event_id':eid,'cycle':c,'reason':str(exc)})
    return {'schema':'s5.temporal-results.v1','expected_protocol':config(),'evidence_digest':evidence.digest,'protocol_completed':complete,
        'summary':{'attempted':12,'admitted':len(results),'excluded':len(excluded),'source_families':len(reviews),
          'positive_gross':sum(r['s1']['lower_floor']>0 for r in results),'algorithm_improvements':sum(r['algorithm_increment']>0 for r in results),
          'semantic_improvements':sum(r['semantic_increment']>0 for r in results),'exact_gross_witnesses':sum(r['gross_witness']is not None for r in results)},
        'reviews':reviews,'results':results,'exclusions':excluded,'realized_profit':None,'live_execution':False,
        'authority':'CONDITIONAL_RESEARCH_ONLY','review_provenance':'IN_SESSION_ASSISTANT_NOT_INDEPENDENT_OR_FULL_LLM_AUTOMATION'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['capture','analyze']);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.action=='capture':capture(a.root)
    else:
        if a.output is None:raise ValueError('output required')
        result=analyze(a.root)
        with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps(result['summary']))
if __name__=='__main__':main()

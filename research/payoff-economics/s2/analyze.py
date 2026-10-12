"""Offline validation of captured bytes, price witnesses and gross S1 controls."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import re
from time import perf_counter_ns
from urllib.parse import parse_qs, urlparse

from capture import allowed_url, json_array, market_tokens
from economics import (SCALE, SampledLedger, alignment, canonical_hash, fee_posture,
    model_from_books, parse_book, partial_fill_floor, partition_witness, rational,
    rule_identity, nominal_rate, solve_maximin, equal_size_frontier, equal_size_depth_frontier, nominal_fees_for_buys, verify_witness)


class Evidence:
    def __init__(self, root):
        self.root = Path(root)
        self.records = [json.loads(line) for line in (self.root/'requests.jsonl').read_text().splitlines()]
        self.by_label = {}
        for r in self.records:
            digest = r['body_sha256']
            if not re.fullmatch('[0-9a-f]{64}', digest): raise ValueError('invalid digest path')
            raw = (self.root/'raw'/f'{digest}.bin').read_bytes()
            if sha256(raw).hexdigest() != digest or len(raw) != r['bytes']:
                raise ValueError('raw response integrity mismatch')
            if r['label'] in self.by_label or r['method'] != 'GET' or not allowed_url(r['url']):
                raise ValueError('duplicate request identity or non-public request')
            if type(r['received_ns']) is not int or type(r['started_ns']) is not int or r['received_ns'] < r['started_ns']:
                raise ValueError('request time order invalid')
            self.by_label[r['label']] = r
        self.digest = canonical_hash(self.records)

    def read(self, label):
        r = self.by_label[label]
        if r['status'] != 200 or r['error'] is not None:
            raise ValueError(f"HTTP_EVIDENCE_UNAVAILABLE:{r['status']}:{r['error']}")
        return r, json.loads((self.root/'raw'/f"{r['body_sha256']}.bin").read_bytes(), parse_float=str)

    def selection(self):
        selected = json.loads((self.root/'selection.json').read_text())
        catalog_events = {}
        for r in self.records:
            if r['label'].startswith('catalog:') and r['status'] == 200 and r['error'] is None:
                _, page = self.read(r['label'])
                if not isinstance(page,list): raise ValueError('catalog schema unsupported')
                for event in page: catalog_events.setdefault(str(event['id']), event)
        if selected['catalog_events'] != len(catalog_events): raise ValueError('catalog count not evidence-bound')
        for f in selected['families']:
            eid = str(f['event']['id'])
            if canonical_hash(f['event']) != canonical_hash(catalog_events.get(eid)):
                raise ValueError('selection event not in raw catalog')
            raw_members = f['event']['markets']
            raw_by_id = {str(m['id']):m for m in raw_members}
            selected_ids = [str(m['id']) for m in f['markets']]
            if (not selected_ids or len(set(selected_ids)) != len(selected_ids) or
                    len(raw_by_id) != len(raw_members)):
                raise ValueError('duplicate/empty event members')
            tokens = [t for m in f['markets'] for t in market_tokens(m)]
            if len(set(tokens)) != len(tokens):
                raise ValueError('duplicate native token')
            if any(canonical_hash(m) != canonical_hash(raw_by_id.get(str(m['id']))) for m in f['markets']):
                raise ValueError('selection market not evidence-bound')
            if f['kind'] == 'NEG_RISK_ASSUMED_EXHAUSTIVE':
                if set(selected_ids) != set(raw_by_id) or f['event'].get('negRiskAugmented') is True:
                    raise ValueError('incomplete or augmented group admitted')
                if f['event'].get('negRisk') is not True and f['event'].get('enableNegRisk') is not True:
                    raise ValueError('group not explicitly negative-risk')
            elif f['kind'] != 'BINARY_COMPLEMENT' or len(f['markets']) != 1:
                raise ValueError('unknown research family')
        return selected


def payoff_matrix(family):
    n = len(family['markets'])
    if not 1 <= n <= 6:
        raise ValueError("invalid payment-family size")
    if n == 1:
        return ['YES','NO'], [(F(1),F(0)),(F(0),F(1))]
    return [f'WIN_{i}' for i in range(n)], [tuple(F(int((k==i)==yes)) for k in range(n)) for i in range(n) for yes in (True,False)]


def nominal_fee_asks(markets, asks):
    if not markets or len(asks) != 2*len(markets) or any(not isinstance(p,F) or not 0 <= p <= 1 for p in asks):
        raise ValueError("nominal fee dimensions or prices invalid")
    rates = [nominal_rate(m) for m in markets]
    if any(rate is None for rate in rates): return None
    return [p + rates[i//2]*p*(1-p) for i,p in enumerate(asks)]


def process_replays(queue):
    """Chronological accounts with at most one pending sample per strategy.

    Data after the decision is used only for its later execution observation.
    Pending capital is unavailable to intervening decisions; no fake settlement.
    """
    ledgers = {k: SampledLedger() for k in ('s1','baseline','depth_baseline')}
    available_at = {k: 0 for k in ledgers}
    for item in sorted(queue, key=lambda x:(x['decision_ns'],x['family_id'],x['name'])):
        name = item['name']
        if item['execution_ns'] <= item['decision_ns']:
            raise ValueError('execution sample is not later than decision')
        if item['decision_ns'] < available_at[name]:
            result = {'status':'PRIOR_ORDER_IN_FLIGHT'}
        else:
            result = ledgers[name].apply(item['family_id'],item['proposal'],item['books'])
            if result['status'] in ('ALL_FILLED','PARTIAL','NO_FILL'):
                available_at[name] = item['execution_ns']
        item['row'][name+'_sampled_account'] = result
    return ledgers


def analyze(root):
    ev = Evidence(root); selected = ev.selection()
    counters, details, family_stats = Counter(), [], []
    # Defer account updates until observations can be processed in time order.
    replay_queue = []
    cycles = json.loads((Path(root)/'config.json').read_text())['cycles']
    for f in selected['families']:
        eid = str(f['event']['id']); mids = [str(m['id']) for m in f['markets']]
        family_id = eid + ':' + ','.join(mids)
        fs = {'family_id':family_id,'kind':f['kind'],'title':f['event']['title'],
              'market_titles':[m['question'] for m in f['markets']], 'assumptions':f['semantic_admission']}
        try:
            ids_scope = mids if f['kind']=='BINARY_COMPLEMENT' else None
            signatures = [rule_identity(f['event'],ids_scope)]
            for phase in ('before','after'):
                record, event = ev.read(f'rules-{phase}:{eid}')
                if urlparse(record['url']).path != '/events/' + eid or str(event.get('id')) != eid:
                    raise ValueError('rule request/event identity mismatch')
                signatures.append(rule_identity(event,ids_scope))
            if len(set(signatures)) != 1: raise ValueError('RULES_OR_FEE_METADATA_CHANGED')
            fs['rules_identity'] = signatures[0]
            fs['fees'] = fee_posture(f['markets'])
        except (KeyError,ValueError,TypeError) as exc:
            fs['blocker'] = str(exc); counters['families_rule_blocked'] += 1; family_stats.append(fs); continue
        tokens = [t for m in f['markets'] for t in market_tokens(m)]
        conditions = [m['conditionId'] for m in f['markets'] for _ in (0,1)]
        states,payoffs = payoff_matrix(f)
        for cycle in range(cycles):
            counters['attempted_family_snapshots'] += 1
            row = {'family_id':family_id,'cycle':cycle,'title':f['event']['title'], 'rules_identity':fs['rules_identity']}
            try:
                pairs = [ev.read(f'book:{cycle}:{t}') for t in tokens]
                records = [r for r,_ in pairs]
                for r,t in zip(records,tokens):
                    if parse_qs(urlparse(r['url']).query).get('token_id') != [t]:
                        raise ValueError('request token identity mismatch')
                books = [parse_book(b,t,c) for (_,b),t,c in zip(pairs,tokens,conditions)]
                row['acquisition_span_ns'] = alignment(records,books)
                row['decision_observed_ns'] = max(r['received_ns'] for r in records)
                row['book_body_sha256s'] = [r['body_sha256'] for r in records]
                row['economic_state_key']=canonical_hash({'family':family_id,'rules':fs['rules_identity'],'asks':[[[str(p),str(q)] for p,q in b['asks']] for b in books]})
                asks = [b['asks'][0][0] for b in books]
                row['best_asks'] = list(map(str, asks))
                w = partition_witness(asks[::2], asks[1::2], binary=len(f['markets'])==1)
                if w is not None and not verify_witness(payoffs, asks, w): raise AssertionError('invalid price witness')
                row['gross_no_arbitrage_witness'] = None if w is None else list(map(str,w))
                nominal = nominal_fee_asks(f['markets'], asks)
                fw = None if nominal is None else partition_witness(nominal[::2],nominal[1::2],binary=len(f['markets'])==1)
                if fw is not None and not verify_witness(payoffs,nominal,fw): raise AssertionError('invalid fee-scenario witness')
                row['nominal_curve_model_no_arbitrage_witness'] = None if fw is None else list(map(str,fw))
                row['fee_qualification'] = fs['fees']['status']
                evidence_id = canonical_hash({'rules':fs['rules_identity'],'quotes':row['book_body_sha256s']})
                model = model_from_books(evidence_id,states,tokens,payoffs,books)
                compute_started=perf_counter_ns()
                t=perf_counter_ns(); s1=solve_maximin(model); row['s1_ns']=perf_counter_ns()-t
                t=perf_counter_ns(); base=equal_size_frontier(model); row['baseline_ns']=perf_counter_ns()-t
                t=perf_counter_ns(); deep=equal_size_depth_frontier(model); row['depth_baseline_ns']=perf_counter_ns()-t
                if s1.lower_floor < deep.lower_floor or deep.lower_floor < base.lower_floor: raise AssertionError('S1 weaker on same model')
                if w is not None and (s1.lower_floor>0 or base.lower_floor>0): raise AssertionError('solver contradicts exact dual witness')
                alignment(records,books, max_age_ns=120_000_000_000-(perf_counter_ns()-compute_started))
                row['s1'] = asdict(s1); row['baseline'] = asdict(base); row['depth_baseline']=asdict(deep)
                decision_done = row['decision_observed_ns'] + (perf_counter_ns()-compute_started)
                row['status']='ANALYZED_GROSS_ONLY'
                for name,prop in (('s1',s1),('baseline',base),('depth_baseline',deep)):
                    if prop.lower_floor <= 0: continue
                    row[name+'_nominal_fees']=nominal_fees_for_buys(prop,tokens,f['markets'],books,payoffs)
                    idx = [tokens.index(b.asset_id) for b in prop.buys]
                    row[name+'_partial_stress'] = partial_fill_floor([payoffs[i] for i in idx],
                        [b.quantity for b in prop.buys], [F(b.conservative_debit,SCALE) for b in prop.buys])
                    minimums={t:rational(b['min_order_size']) for (_,b),t in zip(pairs,tokens)}
                    if any(b.quantity<minimums[b.asset_id] for b in prop.buys):
                        row[name+'_execution_blocker']='MINIMUM_ORDER_SIZE'
                    elif cycle+1 >= cycles: row[name+'_execution_blocker']='NO_LATER_OBSERVATION'
                    else:
                        try:
                            later=[ev.read(f'book:{cycle+1}:{t}') for t in tokens]
                            later_books=[parse_book(b,t,c) for (_,b),t,c in zip(later,tokens,conditions)]
                            alignment([r for r,_ in later],later_books)
                            if min(r['started_ns'] for r,_ in later) <= decision_done:
                                raise ValueError('later books were not acquired after decision')
                            if any(b['timestamp_ns']<row['decision_observed_ns'] for b in later_books):
                                raise ValueError('later book generation predates decision')
                            row[name+'_sampled_later_ms']=(max(r['received_ns'] for r,_ in later)-row['decision_observed_ns'])//1_000_000
                            replay_queue.append({'name':name,'family_id':family_id,'proposal':prop,
                                'books':dict(zip(tokens,later_books)),'row':row,'decision_ns':decision_done,
                                'execution_ns':max(r['received_ns'] for r,_ in later)})
                        except (KeyError,ValueError) as exc: row[name+'_execution_blocker']=str(exc)
                counters['analyzed']+=1
                counters['gross_witnesses']+=w is not None
                counters['nominal_curve_witnesses']+=fw is not None
                counters['gross_s1_positive']+=s1.lower_floor>0
                counters['gross_baseline_positive']+=base.lower_floor>0
                counters['s1_improved_gross']+=s1.lower_floor>base.lower_floor
                counters['s1_improved_vs_depth_baseline']+=s1.lower_floor>deep.lower_floor
            except (KeyError,ValueError,TypeError,RuntimeError) as exc:
                row['status']='EXCLUDED';row['reason']=str(exc);counters['excluded:'+str(exc)]+=1
            details.append(row)
        family_stats.append(fs)
    ledgers=process_replays(replay_queue)
    starts=[r['started_ns'] for r in ev.records if r['label'].startswith('book:')]
    ends=[r['received_ns'] for r in ev.records if r['label'].startswith('book:')]
    return {'schema':'s2.market-economic-report.v1','evidence_manifest_sha256':ev.digest,
        'catalog_events':selected['catalog_events'],'families':family_stats,
        'capture_request_count':len(ev.records),'request_statuses':dict(Counter(str(r['status'])+':'+str(r['error']) for r in ev.records)),
        'capture_from_utc':datetime.fromtimestamp(min(starts)/1e9,timezone.utc).isoformat() if starts else None,
        'capture_until_utc':datetime.fromtimestamp(max(ends)/1e9,timezone.utc).isoformat() if ends else None,
        'counts':dict(counters),'snapshots':details,
        'unique_analyzed_economic_states':len({r['economic_state_key'] for r in details if r['status']=='ANALYZED_GROSS_ONLY'}),
        'unique_gross_positive_families':len({r['family_id'] for r in details if r.get('s1',{}).get('lower_floor',0)>0}),
        'gross_only_sampled_accounts':{k:{'cash':str(v.cash),'locked_inventory':v.inventory,'realized_profit':None} for k,v in ledgers.items()},
        'scope':'BUY_ONLY, DECLARED_FINITE_STATES, <=8 retained price levels and 10000 whole shares/token, budget 1000 units',
        'fee_statement':'Nominal curve model is an exact-arithmetic scenario, not a match-rounding/debit-asset certificate.',
        'capture_statement':'Repeated public GET acquisition is NOT an atomic or complete streaming order book.',
        'decision':'HOLD','live_execution_enabled':False,'profitability_verified':False,
        'statistical_conclusion':'Short selected sample only; no estimate of persistent profit, CAGR or capture probability.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=analyze(args.capture);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['counts'],indent=2))

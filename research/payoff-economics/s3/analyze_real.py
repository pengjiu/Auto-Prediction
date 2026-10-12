"""Recompile complete real Binance rules and replay a retained bounded capture.

This is conditional, retrospective research, never an exact settlement or trade
certificate. No network, model invocation or money movement occurs here.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
from fractions import Fraction as F
from pathlib import Path
import json
import tempfile
import subprocess
from bridge import Evidence, analyze_compiled, recompile, check_quote_urls
from capture_real import experiment_config, select_from_definitions, checked_protocol
from economics import parse_book, verify_witness, nominal_rate, SCALE


def utc_millis(ns):
    if type(ns) is not int or ns < 0:
        raise ValueError('invalid source clock')
    whole, millis = divmod(ns // 1_000_000, 1000)
    return datetime.fromtimestamp(whole, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f'{millis:03d}Z'


def source_from_evidence(evidence, family, phase):
    if phase not in ('before', 'after'):
        raise ValueError('unknown source phase')
    def wrap(label):
        # Documentation is Markdown, not JSON. Preserve the actual original bytes.
        record = evidence.by_label[label]
        if record['status'] != 200 or record['error'] is not None:
            raise ValueError(f"HTTP_EVIDENCE_UNAVAILABLE:{record['status']}:{record['error']}")
        return {'url': record['url'], 'sha256': record['body_sha256'],
            'bodyUtf8': (evidence.root/'raw'/f"{record['body_sha256']}.bin").read_text(),
            'receivedAt': utc_millis(record['received_ns'])}
    return {'schemaVersion': 'pmh.polymarket-binance-close-source.v1',
        'definitions': [wrap(phase + ':' + d['slug']) for d in family['definitions']],
        'selected': [{'eventId': s['event_id'], 'marketId': s['market_id']} for s in family['selected']],
        'policies': [wrap('docs:concepts/resolution'), wrap('docs:trading/fees')]}


def exact_price_witness(payoffs, asks):
    """Floating search, exact rational verification; None means NOT PROVED."""
    if (not asks or len(asks) != len(payoffs) or not payoffs[0] or
        any(not isinstance(a, F) or a < 0 for a in asks) or
        any(len(row) != len(payoffs[0]) or any(not isinstance(v, F) or not 0 <= v <= 1 for v in row) for row in payoffs)):
        raise ValueError('witness dimensions/units invalid')
    from scipy.optimize import linprog
    result = linprog([0]*len(payoffs[0]), A_ub=[[float(v) for v in row] for row in payoffs],
        b_ub=list(map(float, asks)), A_eq=[[1]*len(payoffs[0])], b_eq=[1], bounds=(0, None), method='highs')
    if not result.success or result.x is None:
        return None
    for denominator in (10_000, 1_000_000, 1_000_000_000):
        weights = [F(float(v)).limit_denominator(denominator) for v in result.x]
        index = max(range(len(weights)), key=weights.__getitem__)
        weights[index] += 1 - sum(weights)
        if verify_witness(payoffs, asks, weights):
            return weights
    return None


def same_rules(before, after):
    if (not before.get('familyRuleIdentity') or
            before.get('familyRuleIdentity') != after.get('familyRuleIdentity')):
        raise ValueError('rule definitions changed during captured window')
    def policies(data):
        rows = data.get('policySources')
        if not isinstance(rows, list) or not rows or any(
                not isinstance(x, dict) or not x.get('url') or not x.get('hash') for x in rows):
            raise ValueError('policy evidence missing')
        identities = {(x['url'], x['hash']) for x in rows}
        if len(identities) != len(rows):
            raise ValueError('duplicate policy evidence')
        return identities
    if policies(before) != policies(after):
        raise ValueError('policy evidence changed')
    # A price-only raw-body revision may change source hashes, not rule identity.
    # One policy receipt is not proof of continuous rule invariance.
    return True


def checked_capture(evidence, *, expected_config=None):
    """Reconstruct the declared population. Recorded metadata is NOT authority.

    A new experiment must pass its separately preregistered expected_config.
    Omitting it deliberately selects the original experiment, not the manifest.
    """
    config = json.loads((evidence.root/'config.json').read_text())
    expected = (experiment_config(config.get('cycles')) if expected_config is None
                else checked_protocol(expected_config))
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
    if canonical(config) != canonical(expected):
        raise ValueError('capture configuration differs from the predeclared experiment')
    def retained(url, label):
        record = evidence.by_label.get(label)
        if record is None or record['url'] != url:
            raise ValueError('fixed definition request missing or URL mismatch: ' + label)
        if record['status'] != 200 or record['error'] is not None:
            return record, None
        return evidence.read(label)
    dates = tuple(date.fromisoformat(d) for d in expected['dates'])
    selected, tokens = select_from_definitions(retained, dates=dates)
    supplied = json.loads((evidence.root/'selection.json').read_text())
    if canonical(supplied) != canonical(selected):
        raise ValueError('selection differs from fixed titles/native tokens in original definitions')
    allowed_books = {f'book:{i}:{t}' for i in range(expected['cycles']) for t in tokens}
    observed_books = {k for k in evidence.by_label if k.startswith('book:')}
    if not observed_books <= allowed_books:
        raise ValueError('undeclared cycle/token observation')
    return selected, expected['cycles']


def analyze_capture(root: Path, *, expected_config=None):
    evidence = Evidence(root)
    selection, cycles = checked_capture(evidence, expected_config=expected_config)
    result = {'authority':'RESEARCH_PROPOSAL_ONLY', 'evidence_identity':evidence.digest,
        'scope':'RETROSPECTIVE_BOUNDED_CAPTURE_NOT_CONTINUOUS_OR_EXECUTED',
        'realized_profit':None, 'model_calls':0, 'families':[], 'selection_exclusions':selection['exclusions']}
    with tempfile.TemporaryDirectory(prefix='pmh-real-close-') as tmp:
        for index, family in enumerate(selection['families']):
            report = {'date':family['date'], 'selected':len(family['selected']),
                'rows':[{'cycle':i,'admitted':False,'excluded':'SOURCE_NOT_ADMITTED'} for i in range(cycles)], 'blocker':None}
            result['families'].append(report)
            if len(family['selected']) != 4 or len({s['event_id'] for s in family['selected']}) != 2:
                report['blocker']='PREDECLARED_CROSS_GROUP_SET_INCOMPLETE';continue
            try:
                exports=[]
                for phase in ('before','after'):
                    src=Path(tmp)/f'{index}-{phase}.json';out=Path(tmp)/f'{index}-{phase}-export.json'
                    src.write_text(json.dumps(source_from_evidence(evidence,family,phase)))
                    exports.append(recompile(src,out))
                exported, later=exports;same_rules(exported,later)
                if any(s['observation']['date'] != family['date'] for s in exported['sources']):
                    raise ValueError('selection date disagrees with parsed original rules')
            except (ValueError,KeyError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                report['blocker']=str(exc);continue
            report.update({'export_id':exported['exportId'],'family_rule_identity':exported['familyRuleIdentity'],
                'states':len(exported['states']),'stress_states':len(exported['stressStates']),
                'unknowns':exported['sources'][0]['unknowns'],'fetched_rule_identities_equal_at_window_end':True,
                'rule_observation_limitations':'HTTP_CACHE_AND_SAMPLED_RECHECK_NOT_CONTINUOUS_RULE_OR_POLICY_MONITOR',
                'rule_response_cache_age_seconds': {
                    phase+':'+d['slug']: evidence.by_label[phase+':'+d['slug']].get('headers',{}).get('age')
                    for phase in ('before','after') for d in family['definitions']}})
            tokens=[a['id'] for a in exported['assets']]
            markets={}
            for d in family['definitions']:
                _, page=evidence.read('before:'+d['slug'])
                for m in page[0]['markets']:markets[str(m['id'])]=m
            selected_markets=[markets[s['marketId']] for s in exported['sources']]
            rates=[nominal_rate(m) for m in selected_markets]
            report['nominal_rates']=[str(r) if r is not None else None for r in rates]
            for cycle in range(cycles):
                row=report['rows'][cycle]
                row.pop('excluded',None)
                try:
                    quotes={t:evidence.read(f'book:{cycle}:'+t) for t in tokens}
                    check_quote_urls(quotes)
                    analysis=analyze_compiled(exported,quotes)
                    books=[parse_book(quotes[a['id']][1],a['id'],a['instrumentId']) for a in exported['assets']]
                    pays=[tuple(F(a['payoffs'][s]) for s in exported['states']) for a in exported['assets']]
                    asks=[b['asks'][0][0] for b in books]
                    witness=exact_price_witness(pays,asks)
                    nominal=None
                    if all(r is not None for r in rates):
                        nominal=exact_price_witness(pays,[p+rates[i//2]*p*(1-p) for i,p in enumerate(asks)])
                    if witness is not None and analysis['s1']['lower_floor']>0:
                        raise AssertionError('numeric solver contradicts rational witness')
                    row.update({'admitted':True,'decision_ns':max(r['received_ns'] for r,_ in quotes.values()),
                        'analysis':analysis, 'gross_witness':None if witness is None else list(map(str,witness)),
                        'nominal_fee_witness':None if nominal is None else list(map(str,nominal)),
                        'nominal_fee_qualification':'UNROUNDED_CURVE_SCENARIO_NOT_DEBIT_CERTIFICATE'})
                except (ValueError,KeyError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                    row['excluded']=str(exc)
    rows=[r for f in result['families'] for r in f['rows']]
    admitted=[r for r in rows if r['admitted']]
    result['summary']={'families_attempted':len(result['families']),
        'families_source_admitted':sum(f['blocker'] is None for f in result['families']),
        'rounds_attempted':len(rows),'rounds_admitted':len(admitted),
        'gross_positive_rounds':sum(r['analysis']['s1']['lower_floor']>0 for r in admitted),
        'same_depth_improvement_rounds':sum(r['analysis']['incremental_gross_floor']>0 for r in admitted),
        'exact_gross_witness_rounds':sum(r['gross_witness'] is not None for r in admitted),
        'after_fee_certification':False,'live_execution':False}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=analyze_capture(a.evidence_root)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()

"""Predeclared out-of-window replication, not a scheduled trading process."""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 's3'))
from capture_real import experiment_config, checked_protocol, run as capture_window
from analyze_real import analyze_capture
from bridge import Evidence
from source_audit import capture as capture_source, audit as audit_source, write_json


def fixed_protocol():
    original = experiment_config(8)
    return checked_protocol({**original, 'dates': ['2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16'],
        'cycles': 12, 'interval_seconds': 5})


def campaign_config():
    return {'schema': 's4.source-evidence-campaign.v1', 'windows': 2,
        'gap_seconds': 60, 'protocol': fixed_protocol(),
        'selection_uses_quotes': False, 'capture_is_atomic': False,
        'statistical_independence_established': False, 'live_execution': False}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def capture(root: Path):
    root.mkdir(parents=True, exist_ok=False)
    config = campaign_config()
    write_json(root / 'campaign.json', config)
    plan = HERE.parents[2] / 'plans' / 'source-evidence-validation.md'
    write_json(root / 'provenance.json', {'plan_sha256': sha256(plan.read_bytes()).hexdigest(),
        'config_sha256': sha256(canonical(config).encode()).hexdigest(),
        'started_ns': time.time_ns(), 'authority': 'ANONYMOUS_PUBLIC_OBSERVATION_ONLY'})
    capture_source(root / 'source')
    for window in range(config['windows']):
        start = time.time_ns()
        try:
            capture_window(root / f'window-{window}', protocol=fixed_protocol())
        except (ValueError, OSError) as exc:
            # An unsuccessful window is retained, not replaced with a chosen one.
            write_json(root / f'window-{window}-failure.json', {'started_ns': start,
                'received_ns': time.time_ns(), 'reason': type(exc).__name__ + ': ' + str(exc)})
        if window + 1 < config['windows']:
            time.sleep(config['gap_seconds'])
    write_json(root / 'capture-complete.json', {'finished_ns': time.time_ns(), 'attempted_windows': config['windows']})


def analyze(root: Path):
    supplied = json.loads((root / 'campaign.json').read_text())
    if canonical(supplied) != canonical(campaign_config()):
        raise ValueError('campaign differs from independently predeclared population')
    config, reports, windows = campaign_config(), [], []
    for window in range(config['windows']):
        folder = root / f'window-{window}'
        timing = None
        try:
            evidence = Evidence(folder)
            records = list(evidence.by_label.values())
            if not records:
                raise ValueError('empty observation window')
            timing = {'first_request_ns': min(r['started_ns'] for r in records),
                'last_receipt_ns': max(r['received_ns'] for r in records),
                'responses': len(records), 'http_or_capture_failures': sum(r['status'] != 200 or r['error'] is not None for r in records)}
            report = analyze_capture(folder, expected_config=fixed_protocol())
        except (ValueError, OSError, KeyError) as exc:
            report = {'families': [{'date': day, 'blocker': 'WINDOW_EVIDENCE_UNAVAILABLE',
                'rows': [{'cycle': i, 'admitted': False, 'excluded': str(exc)} for i in range(config['protocol']['cycles'])]}
                for day in config['protocol']['dates']], 'invalid_window': type(exc).__name__ + ': ' + str(exc)}
        reports.append({'window': window, 'timing': timing, 'report': report})
        windows.append(timing)
    rows = [r for w in reports for f in w['report']['families'] for r in f['rows']]
    expected_count = config['windows'] * len(config['protocol']['dates']) * config['protocol']['cycles']
    if len(rows) != expected_count:
        raise ValueError('analysis silently changed the predeclared denominator')
    admitted = [r for r in rows if r['admitted']]
    source = audit_source(root / 'source')
    gap = None if any(w is None for w in windows) else windows[1]['first_request_ns'] - windows[0]['last_receipt_ns']
    summary = {'windows_attempted': config['windows'], 'distinct_observation_dates': len(config['protocol']['dates']),
        'group_rounds_attempted': expected_count, 'group_rounds_admitted': len(admitted),
        'group_rounds_excluded': len(rows) - len(admitted),
        'gross_positive_rounds': sum(r['analysis']['s1']['lower_floor'] > 0 for r in admitted),
        'same_depth_improvement_rounds': sum(r['analysis']['incremental_gross_floor'] > 0 for r in admitted),
        'exact_gross_witness_rounds': sum(r['gross_witness'] is not None for r in admitted),
        'between_window_gap_ns': gap, 'planned_window_gap_met': gap is not None and gap >= 60_000_000_000,
        'statistical_independence_established': False,
        'source_probe_status': source['candle_probe']['status'],
        'no_trade_global_claim': False, 'fee_debit_certified': False,
        'realized_profit': None, 'model_calls': 0, 'live_execution': False}
    return {'schema': 's4.replication-result.v1', 'summary': summary,
        'source_audit': source, 'windows': reports,
        'exclusion_reasons': dict(Counter(str(r.get('excluded', 'SOURCE_NOT_ADMITTED')) for r in rows if not r['admitted'])),
        'interpretation': 'FINITE_CONDITIONAL_BUY_MODELS_ONLY; repeated snapshots are not independent opportunities; no PnL summation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('capture', 'analyze'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'capture':
        capture(args.root)
    else:
        if args.output is None:
            parser.error('analysis requires a new output file')
        result = analyze(args.root)
        write_json(args.output, result)
        print('S4_RESULT ' + json.dumps(result['summary'], sort_keys=True))
        print('S4_EXCLUSIONS ' + json.dumps(result['exclusion_reasons'], sort_keys=True))
        print('S4_SOURCE ' + json.dumps(result['source_audit'], sort_keys=True))
        print('S4_WINDOWS ' + json.dumps([{'window': w['window'], 'timing': w['timing'],
            'families': [{'date': f['date'], 'blocker': f.get('blocker'),
                'admitted': sum(r['admitted'] for r in f['rows'])} for f in w['report']['families']]}
            for w in result['windows']], sort_keys=True))


if __name__ == '__main__':
    main()

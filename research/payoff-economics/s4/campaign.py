"""Predeclared out-of-window replication, not a scheduled trading process."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 's3'))
from capture_real import experiment_config, checked_protocol, require_future_dates, run as capture_window
from analyze_real import analyze_capture
from bridge import Evidence
from source_audit import capture as capture_source, audit as audit_source, write_json, UNRESOLVED_ASSUMPTIONS


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


# Fixed byte identity of the plan committed before the original S4 observation.
# This is not proof of authorship; retain the enclosing GitHub artifact digest.
PREREGISTRATION_SHA256 = 'a7b7654f16e913081f1d26319f96245cd22ba21a473af6940b17a8d7d37e3ed5'


def checked_provenance(root: Path, config):
    try:
        data = json.loads((root / 'provenance.json').read_text())
    except FileNotFoundError:
        return None, None
    if (not isinstance(data, dict) or set(data) != {'plan_sha256', 'config_sha256', 'started_ns', 'authority'}
        or data['plan_sha256'] != PREREGISTRATION_SHA256
        or data['config_sha256'] != sha256(canonical(config).encode()).hexdigest()
        or data['authority'] != 'ANONYMOUS_PUBLIC_OBSERVATION_ONLY'
        or type(data['started_ns']) is not int or data['started_ns'] <= 0):
        raise ValueError('invalid campaign provenance or preregistration binding')
    require_future_dates(config['protocol'], datetime.fromtimestamp(data['started_ns'] // 1_000_000_000, timezone.utc))
    try:
        end = json.loads((root / 'capture-complete.json').read_text())
    except FileNotFoundError:
        return data, None
    if (not isinstance(end, dict) or set(end) != {'finished_ns', 'attempted_windows'}
        or type(end['attempted_windows']) is not int or end['attempted_windows'] != config['windows']
        or type(end['finished_ns']) is not int or end['finished_ns'] < data['started_ns']):
        raise ValueError('invalid campaign completion envelope')
    return data, end


def checked_window_timing(records, config, provenance, completion):
    if not records:
        raise ValueError('empty observation window')
    for r in records:
        if (type(r.get('started_ns')) is not int or type(r.get('received_ns')) is not int
            or r['received_ns'] < r['started_ns'] or r['started_ns'] < 0):
            raise ValueError('invalid window request clocks')
    timing = {'first_request_ns': min(r['started_ns'] for r in records),
        'last_receipt_ns': max(r['received_ns'] for r in records),
        'responses': len(records),
        'http_or_capture_failures': sum(r['status'] != 200 or r['error'] is not None for r in records)}
    if provenance is None:
        raise ValueError('campaign provenance unavailable')
    if (timing['first_request_ns'] < provenance['started_ns'] or
        completion is not None and timing['last_receipt_ns'] > completion['finished_ns']):
        raise ValueError('window outside declared campaign time envelope')
    rounds = []
    for cycle in range(config['protocol']['cycles']):
        group = [r for r in records if r['label'].startswith(f'book:{cycle}:')]
        if group:
            rounds.append((min(r['started_ns'] for r in group), max(r['received_ns'] for r in group)))
    if any(b[0] < a[1] for a, b in zip(rounds, rounds[1:])):
        raise ValueError('round request envelopes overlap or run backward')
    # Worker dispatch and wall-clock timestamps do not attest the monotonic
    # scheduler's exact 5-second cadence. Report it, do not calibrate a new
    # acceptance tolerance against these observed data.
    timing['minimum_round_start_gap_ns'] = min((b[0] - a[0] for a, b in zip(rounds, rounds[1:])), default=None)
    timing['exact_scheduler_cadence_certified'] = False
    return timing


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
    provenance, completion = checked_provenance(root, config)
    for window in range(config['windows']):
        folder = root / f'window-{window}'
        timing = None
        try:
            evidence = Evidence(folder)
            records = list(evidence.by_label.values())
            timing = checked_window_timing(records, config, provenance, completion)
            previous = windows[-1] if windows else None
            if previous is not None and timing['first_request_ns'] - previous['last_receipt_ns'] < config['gap_seconds'] * 1_000_000_000:
                raise ValueError('window overlaps or violates predeclared separation')
            report = analyze_capture(folder, expected_config=fixed_protocol())
        except (ValueError, OSError, KeyError, TypeError) as exc:
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
    try:
        source = audit_source(root / 'source')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Source failure is not zero price, and must not erase the fixed market
        # population. No source assumptions are cleared by this diagnostic.
        source = {'schema': 's4.source-audit.v1', 'authority': 'SOURCE_OBSERVATION_ONLY',
            'candle_probe': {'status': 'NOT_ESTABLISHED', 'selected_contract_value': None},
            'error': type(exc).__name__ + ': ' + str(exc),
            'contract_final_value': None, 'realized_profit': None,
            'unresolved': list(UNRESOLVED_ASSUMPTIONS),
            'certificate_authority': False, 'live_execution': False}

    gap = None if any(w is None for w in windows) else windows[1]['first_request_ns'] - windows[0]['last_receipt_ns']
    summary = {'windows_attempted': config['windows'], 'distinct_observation_dates': len(config['protocol']['dates']),
        'group_rounds_attempted': expected_count, 'group_rounds_admitted': len(admitted),
        'group_rounds_excluded': len(rows) - len(admitted),
        'gross_positive_rounds': sum(r['analysis']['s1']['lower_floor'] > 0 for r in admitted),
        'same_depth_improvement_rounds': sum(r['analysis']['incremental_gross_floor'] > 0 for r in admitted),
        'exact_gross_witness_rounds': sum(r['gross_witness'] is not None for r in admitted),
        'between_window_gap_ns': gap, 'planned_window_gap_met': gap is not None and gap >= 60_000_000_000,
        'replication_protocol_conformant': provenance is not None and completion is not None
            and gap is not None and gap >= config['gap_seconds'] * 1_000_000_000
            and all('invalid_window' not in w['report'] for w in reports) and len(admitted) == expected_count,
        'provenance_bound': provenance is not None, 'completion_recorded': completion is not None,
        'statistical_independence_established': False,
        'source_probe_status': source['candle_probe']['status'],
        'no_trade_global_claim': False, 'fee_debit_certified': False,
        'realized_profit': None, 'model_calls': 0, 'live_execution': False}
    return {'schema': 's4.replication-result.v2', 'summary': summary,
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

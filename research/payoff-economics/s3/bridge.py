"""Source-recompiled numeric payoff -> same-book S1/S2 experiment.

No network, LLM call, trade, fee certification or semantic certificate authority.
CLI recompiles source with the first-party TS compiler, not a Python text parser.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 's2'))
from analyze import Evidence
from economics import (alignment, parse_book, model_from_books, equal_size_depth_frontier,
    solve_maximin, partial_fill_floor, SCALE)


def validate_export(data):
    if not isinstance(data, dict) or data.get('schemaVersion') != 'pmh.numeric-payoff-research.v1':
        raise ValueError('unsupported export')
    if (data.get('authority') != 'RESEARCH_EXPORT_ONLY' or data.get('coverage') != 'ASSUMED_STATES_ONLY'
        or data.get('certificateAuthority') is not False or data.get('executionAuthority') is not False
        or data.get('assumption') != 'SHARED_OBSERVATION_AND_CONSISTENT_RESOLUTION'):
        raise ValueError('export authority mismatch')
    assets, sources = data['assets'], data['sources']
    if (not 4 <= len(assets) <= 12 or len(assets) != 2 * len(sources)
        or len({a['id'] for a in assets}) != len(assets)
        or len({s['listingRef'] for s in sources}) != len(sources)):
        raise ValueError('duplicate or incomplete assets/sources')
    refs = {s['listingRef'] for s in sources}
    for field, payoff in [('states', 'payoffs'), ('stressStates', 'stressPayoffs')]:
        states = data[field]
        if not 1 <= len(states) <= 128 or len(states) != len(set(states)):
            raise ValueError('invalid states')
        for a in assets:
            if (a['listingRef'] not in refs or set(a[payoff]) != set(states)
                or any(v not in ('0', '1', '0.5') for v in a[payoff].values())):
                raise ValueError('invalid payment matrix')
    for ref in refs:
        if sorted(a['outcome'] for a in assets if a['listingRef'] == ref) != ['NO', 'YES']:
            raise ValueError('missing native complementary outcome')
    # Hashes bind bytes; they are not an independent semantic proof. Public CLI
    # never relies on validating a caller-rehashed export instead of recompiling.
    return data


def analyze_compiled(data, quote_records, *, budget=1000*SCALE):
    data = validate_export(data)
    assets = data['assets']; tokens = [a['id'] for a in assets]
    if set(quote_records) != set(tokens):
        raise ValueError('missing or extra quote tokens')
    records, books = [], []
    for asset in assets:
        record, body = quote_records[asset['id']]
        records.append(record)
        books.append(parse_book(body, asset['id'], asset['instrumentId']))
    alignment(records, books)
    decision = max(r['received_ns'] for r in records)
    for source in data['sources']:
        parsed = datetime.fromisoformat(source['sourceReceivedAt'].replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('source evidence time lacks timezone')
        delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
        source_ns = ((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds) * 1000
        if not 0 <= decision - source_ns <= 900_000_000_000:
            raise ValueError('source evidence unavailable or stale at quote decision')
    rows = [tuple(F(a['payoffs'][s]) for s in data['states']) for a in assets]
    model = model_from_books(data['exportId'], data['states'], tokens, rows, books, budget)
    # Same quotes/depth/budget/states, both sides use full-quantity-at-limit cost.
    s1, baseline = solve_maximin(model), equal_size_depth_frontier(model)
    stress_rows = [tuple(F(a['stressPayoffs'][s]) for s in data['stressStates']) for a in assets]
    stress = model_from_books(data['exportId'] + ':stress', data['stressStates'], tokens, stress_rows, books, budget)
    stress_proposal = solve_maximin(stress)
    selected = [tokens.index(b.asset_id) for b in s1.buys]
    partial = None if not selected else partial_fill_floor([rows[i] for i in selected],
        [b.quantity for b in s1.buys], [F(b.conservative_debit, model.scale) for b in s1.buys])
    return {
        'authority': 'RESEARCH_PROPOSAL_ONLY', 'coverage': 'ASSUMED_STATES_ONLY',
        'export_id': data['exportId'], 'scale': model.scale,
        'quote_clock_span_ns': alignment(records, books),
        's1': asdict(s1), 'same_depth_baseline': asdict(baseline),
        'incremental_gross_floor': s1.lower_floor - baseline.lower_floor,
        'independent_resolution_stress': asdict(stress_proposal), 'partial_fill_stress': partial,
        'net_qualification': 'BLOCKED_UNQUALIFIED_FEES', 'realized_profit': None,
        'execution': 'NOT_EXECUTED_NOT_ATOMIC',
    }


def check_quote_urls(quotes):
    # Native response fields are not proof of which URL was actually requested.
    from urllib.parse import parse_qs, urlparse
    for token, (record, _) in quotes.items():
        url = urlparse(record['url'])
        if (url.scheme != 'https' or url.netloc != 'clob.polymarket.com' or url.fragment or
                url.path != '/book' or parse_qs(url.query) != {'token_id': [token]}):
            raise ValueError('quote URL does not bind requested token')


def recompile(source: Path, output: Path):
    tsx = ROOT / 'packages/control-plane/node_modules/.bin/tsx'
    if not tsx.exists():
        raise RuntimeError('install frozen pnpm dependencies before source recompilation')
    subprocess.run([str(tsx), str(Path(__file__).with_name('export.ts')), str(source), str(output)],
                   cwd=ROOT, check=True, timeout=60)
    return json.loads(output.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--evidence-root', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path, help='token -> retained GET label')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    evidence = Evidence(args.evidence_root)  # verifies every retained response byte
    labels = json.loads(args.labels.read_text())
    with tempfile.TemporaryDirectory(prefix='pmh-semantic-export-') as tmp:
        export = recompile(args.source, Path(tmp) / 'export.json')
    quotes = {a['id']: evidence.read(labels[a['id']]) for a in export['assets']}
    check_quote_urls(quotes)
    result = analyze_compiled(export, quotes)
    result['source_bytes_sha256'] = sha256(args.source.read_bytes()).hexdigest()
    result['quote_evidence_identity'] = evidence.digest
    # Exclusive: existing raw files/reports are never overwritten.
    with args.output.open('x') as out:
        json.dump(result, out, indent=2); out.write('\n')


if __name__ == '__main__':
    main()

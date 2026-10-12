"""One bounded GET-only experiment; selection fixed before quotes, no trading."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 's2'))
from capture import Capture, GAMMA, CLOB, market_tokens

DATES = (date(2026, 10, 12), date(2026, 10, 13))


def event_request(day, kind):
    stamp = day.strftime('%B').lower() + '-' + str(day.day) + '-' + str(day.year)
    slug = 'bitcoin-' + kind + '-on-' + stamp
    return GAMMA + '/events?' + urlencode({'slug': slug}), slug


def experiment_config(cycles):
    if type(cycles) is not int or not 2 <= cycles <= 8:
        raise ValueError('bounded experiment requires 2..8 rounds')
    return {'schema': 's3.real-binance-capture.v1',
        'dates': [d.isoformat() for d in DATES], 'cycles': cycles, 'interval_seconds': 1,
        'fixed_above': ['82,000', '84,000'],
        'fixed_ranges': [['80,000', '82,000'], ['82,000', '84,000']],
        'authority': 'READ_ONLY_RESEARCH', 'no_live_actions': True,
        'selection_uses_prices': False}


def select_from_definitions(read):
    """Replay the fixed population from raw definitions, not observed returns."""
    families, exclusions, selected_tokens = [], [], set()
    for day in DATES:
        chosen, definitions = [], []
        for kind in ('above', 'price'):
            url, slug = event_request(day, kind)
            record, body = read(url, 'before:' + slug)
            definitions.append({'slug': slug, 'label': record['label'], 'url': url})
            if not isinstance(body, list) or len(body) != 1 or body[0].get('slug') != slug:
                exclusions.append({'date': day.isoformat(), 'slug': slug, 'reason': 'event_missing_or_bad_schema'})
                continue
            event = body[0]
            suffix = day.strftime('%B') + ' ' + str(day.day) + '?'
            titles = (['Will the price of Bitcoin be above $' + p + ' on ' + suffix for p in ('82,000', '84,000')]
                if kind == 'above' else ['Will the price of Bitcoin be between $' + a + ' and $' + b + ' on ' + suffix
                    for a, b in (('80,000', '82,000'), ('82,000', '84,000'))])
            for title in titles:
                hits = [m for m in event.get('markets', []) if m.get('question') == title]
                if len(hits) != 1:
                    exclusions.append({'date': day.isoformat(), 'title': title, 'reason': 'missing_or_duplicate_fixed_member'})
                    continue
                market = hits[0]
                try:
                    tokens = market_tokens(market)
                    if selected_tokens.intersection(tokens):
                        raise ValueError('duplicate token')
                except (ValueError, TypeError) as exc:
                    exclusions.append({'date': day.isoformat(), 'title': title, 'reason': str(exc)})
                    continue
                selected_tokens.update(tokens)
                chosen.append({'event_id': str(event['id']), 'market_id': str(market['id']),
                    'event_label': record['label'], 'tokens': tokens})
        families.append({'date': day.isoformat(), 'definitions': definitions, 'selected': chosen})
    return {'families': families, 'exclusions': exclusions}, selected_tokens


def run(output: Path, *, cycles: int = 8):
    config = experiment_config(cycles)
    cap = Capture(output)
    cap.save('config.json', config)
    for path in ('concepts/resolution', 'trading/fees'):
        cap.get('https://docs.polymarket.com/' + path + '.md', 'docs:' + path)
    selected, selected_tokens = select_from_definitions(cap.get)
    cap.save('selection.json', selected)
    for cycle in range(cycles):
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda t: cap.get(CLOB + '/book?' + urlencode({'token_id': t}),
                'book:' + str(cycle) + ':' + t), sorted(selected_tokens)))
        if cycle + 1 < cycles:
            time.sleep(max(0, 1 - (time.monotonic() - started)))
    for day in DATES:
        for kind in ('above', 'price'):
            url, slug = event_request(day, kind)
            cap.get(url, 'after:' + slug)
    cap.save('summary.json', {'requests': len(cap.records), 'tokens': len(selected_tokens),
        'cycles': cycles, 'errors': [r['label'] for r in cap.records if r['error'] is not None or r['status'] != 200],
        'started_ns': min(r['started_ns'] for r in cap.records),
        'finished_ns': max(r['received_ns'] for r in cap.records)})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output)

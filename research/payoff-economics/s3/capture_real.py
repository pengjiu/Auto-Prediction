"""Bounded GET-only experiments; population fixed before quotes, no trading."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 's2'))
from capture import Capture, GAMMA, CLOB, market_tokens

DATES = (date(2026, 10, 12), date(2026, 10, 13))


def event_request(day, kind):
    if type(day) is not date or kind not in ('above', 'price'):
        raise ValueError('invalid fixed event request')
    stamp = day.strftime('%B').lower() + '-' + str(day.day) + '-' + str(day.year)
    slug = 'bitcoin-' + kind + '-on-' + stamp
    return GAMMA + '/events?' + urlencode({'slug': slug}), slug


def experiment_config(cycles):
    """Original preregistered experiment; historical bytes remain reproducible."""
    if type(cycles) is not int or not 2 <= cycles <= 8:
        raise ValueError('bounded original experiment requires 2..8 rounds')
    return {'schema': 's3.real-binance-capture.v1',
        'dates': [d.isoformat() for d in DATES], 'cycles': cycles, 'interval_seconds': 1,
        'fixed_above': ['82,000', '84,000'],
        'fixed_ranges': [['80,000', '82,000'], ['82,000', '84,000']],
        'authority': 'READ_ONLY_RESEARCH', 'no_live_actions': True,
        'selection_uses_prices': False}


def checked_protocol(config):
    """Validate a caller-selected protocol, NOT infer one from captured prices.

    Replay additionally requires exact equality to its trusted expected protocol.
    This function alone does not attest that a protocol was preregistered.
    """
    if not isinstance(config, dict) or set(config) != set(experiment_config(8)):
        raise ValueError('unknown capture protocol fields')
    template = experiment_config(8)
    for key in ('schema', 'fixed_above', 'fixed_ranges', 'authority'):
        if config[key] != template[key]:
            raise ValueError('unsupported capture protocol: ' + key)
    if config['no_live_actions'] is not True or config['selection_uses_prices'] is not False:
        raise ValueError('invalid capture authority')
    cycles, interval, dates = config['cycles'], config['interval_seconds'], config['dates']
    if type(cycles) is not int or not 2 <= cycles <= 12 or type(interval) is not int or not 1 <= interval <= 30:
        raise ValueError('capture rate/round bound exceeded')
    if not isinstance(dates, list) or not 1 <= len(dates) <= 4 or any(type(d) is not str for d in dates):
        raise ValueError('invalid date population')
    parsed = [date.fromisoformat(d) for d in dates]
    if [d.isoformat() for d in parsed] != dates or dates != sorted(set(dates)):
        raise ValueError('duplicate/noncanonical date population')
    return {**template, 'dates': list(dates), 'cycles': cycles, 'interval_seconds': interval}


def require_future_dates(config, now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('capture requires an aware current clock')
    for d in checked_protocol(config)['dates']:
        deadline = datetime.fromisoformat(d + 'T12:00:00').replace(tzinfo=ZoneInfo('America/New_York'))
        if now >= deadline:
            raise ValueError('observation date is not future at capture start: ' + d)


def select_from_definitions(read, *, dates=DATES):
    """Replay the fixed population from raw definitions, not observed returns."""
    if not isinstance(dates, tuple) or not 1 <= len(dates) <= 4 or any(type(d) is not date for d in dates) or tuple(sorted(set(dates))) != dates:
        raise ValueError('invalid fixed date population')
    families, exclusions, selected_tokens = [], [], set()
    for day in dates:
        chosen, definitions = [], []
        for kind in ('above', 'price'):
            url, slug = event_request(day, kind)
            record, body = read(url, 'before:' + slug)
            definitions.append({'slug': slug, 'label': record['label'], 'url': url})
            if not isinstance(body, list) or len(body) != 1 or not isinstance(body[0], dict) or body[0].get('slug') != slug:
                exclusions.append({'date': day.isoformat(), 'slug': slug, 'reason': 'event_missing_or_bad_schema'})
                continue
            event = body[0]
            suffix = day.strftime('%B') + ' ' + str(day.day) + '?'
            titles = (['Will the price of Bitcoin be above $' + p + ' on ' + suffix for p in ('82,000', '84,000')]
                if kind == 'above' else ['Will the price of Bitcoin be between $' + a + ' and $' + b + ' on ' + suffix
                    for a, b in (('80,000', '82,000'), ('82,000', '84,000'))])
            members = event.get('markets', [])
            if not isinstance(members, list) or any(not isinstance(m, dict) for m in members):
                exclusions.append({'date': day.isoformat(), 'slug': slug, 'reason': 'invalid_member_schema'})
                continue
            for title in titles:
                hits = [m for m in members if m.get('question') == title]
                if len(hits) != 1:
                    exclusions.append({'date': day.isoformat(), 'title': title, 'reason': 'missing_or_duplicate_fixed_member'})
                    continue
                market = hits[0]
                try:
                    tokens = market_tokens(market)
                    if selected_tokens.intersection(tokens):
                        raise ValueError('duplicate token')
                    if 'id' not in event or 'id' not in market:
                        raise ValueError('missing native identity')
                except (ValueError, TypeError) as exc:
                    exclusions.append({'date': day.isoformat(), 'title': title, 'reason': str(exc)})
                    continue
                selected_tokens.update(tokens)
                chosen.append({'event_id': str(event['id']), 'market_id': str(market['id']),
                    'event_label': record['label'], 'tokens': tokens})
        families.append({'date': day.isoformat(), 'definitions': definitions, 'selected': chosen})
    return {'families': families, 'exclusions': exclusions}, selected_tokens


def run(output: Path, *, cycles: int = 8, protocol=None):
    config = checked_protocol(experiment_config(cycles) if protocol is None else protocol)
    require_future_dates(config, datetime.now(timezone.utc))
    dates = tuple(date.fromisoformat(d) for d in config['dates'])
    cap = Capture(output)
    cap.save('config.json', config)
    for path in ('concepts/resolution', 'trading/fees'):
        cap.get('https://docs.polymarket.com/' + path + '.md', 'docs:' + path)
    selected, selected_tokens = select_from_definitions(cap.get, dates=dates)
    cap.save('selection.json', selected)
    for cycle in range(config['cycles']):
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda t: cap.get(CLOB + '/book?' + urlencode({'token_id': t}),
                'book:' + str(cycle) + ':' + t), sorted(selected_tokens)))
        if cycle + 1 < config['cycles']:
            time.sleep(max(0, config['interval_seconds'] - (time.monotonic() - started)))
    for day in dates:
        for kind in ('above', 'price'):
            url, slug = event_request(day, kind)
            cap.get(url, 'after:' + slug)
    cap.save('summary.json', {'requests': len(cap.records), 'tokens': len(selected_tokens),
        'cycles': config['cycles'], 'errors': [r['label'] for r in cap.records if r['error'] is not None or r['status'] != 200],
        'started_ns': min(r['started_ns'] for r in cap.records),
        'finished_ns': max(r['received_ns'] for r in cap.records)})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output)

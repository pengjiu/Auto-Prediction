"""Small source-evidence probe; never a contract oracle or a trading client.

Only the four exact anonymous URLs declared below can be read. Redirects,
credentials, alternative endpoints and retries are intentionally unsupported.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

MAX_BYTES = 3_000_000
PROBE_DAY = date(2026, 10, 11)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
UNRESOLVED_ASSUMPTIONS = ('CONTRACT_UI_TO_API_CANDLE_MAPPING', 'FINAL_VALUE_REVISION_CUTOFF',
    'UNAVAILABLE_SOURCE_FALLBACK', 'ONCHAIN_ANCILLARY_AND_CLARIFICATION_MATCH',
    'INDEPENDENT_ORACLE_OUTCOMES', 'COLLATERAL_REDEMPTION_TIMING', 'MATCH_LEVEL_FEE_DEBIT')
DOC_URLS = {
    'binance-rest': 'https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/rest-api.md',
    'polymarket-resolution': 'https://docs.polymarket.com/concepts/resolution.md',
    'uma-yes-no': 'https://docs.uma.xyz/verification-guide/yes_or_no.md',
}


def noon_ms(day: date) -> int:
    if type(day) is not date:
        raise ValueError('expected a date, not a timestamp')
    dt = datetime.combine(day, datetime.min.time()).replace(hour=12, tzinfo=ZoneInfo('America/New_York'))
    delta = dt.astimezone(timezone.utc) - EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000


def candle_url() -> str:
    boundary = noon_ms(PROBE_DAY)
    return 'https://api.binance.com/api/v3/klines?' + urlencode({
        'symbol': 'BTCUSDT', 'interval': '1m', 'startTime': boundary - 60_000,
        'endTime': boundary + 59_999, 'timeZone': '0', 'limit': 2})


def requests_by_label():
    return {**DOC_URLS, 'binance-candles': candle_url()}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('source probe redirects are not authorized')


def exact_decimal(value):
    if type(value) is not str or not re.fullmatch(r'(?:0|[1-9]\d{0,19})(?:\.\d{1,16})?', value):
        raise ValueError('source number must be a bounded plain decimal string')
    return Fraction(value)


def validate_candles(body, boundary_ms: int, observed_ms: int):
    if (type(boundary_ms) is not int or boundary_ms <= 0 or boundary_ms % 60_000 or
            type(observed_ms) is not int or observed_ms <= boundary_ms + 59_999):
        raise ValueError('future or noncanonical observation boundary')
    if not isinstance(body, list) or len(body) != 2:
        raise ValueError('both candidate candles are required')
    result = []
    for index, row in enumerate(body):
        opened = boundary_ms - 60_000 + index * 60_000
        if not isinstance(row, list) or len(row) != 12:
            raise ValueError('unsupported kline tuple')
        if type(row[0]) is not int or type(row[6]) is not int or row[0] != opened or row[6] != opened + 59_999:
            raise ValueError('kline interval identity mismatch')
        prices = [exact_decimal(row[i]) for i in (1, 2, 3, 4)]
        op, high, low, close = prices
        if low <= 0 or not low <= op <= high or not low <= close <= high:
            raise ValueError('inconsistent OHLC values')
        for i in (5, 7, 9, 10, 11):
            exact_decimal(row[i])
        if type(row[8]) is not int or row[8] < 0:
            raise ValueError('invalid trade count')
        result.append({'open_ms': row[0], 'close_ms': row[6], 'close_decimal': row[4],
            'candidate': 'MINUTE_ENDING_AT_NOON_EXCLUSIVE' if index == 0 else 'MINUTE_OPENING_AT_NOON'})
    return {'status': 'TWO_CLOSED_API_INTERVALS_OBSERVED', 'candles': result,
        'equal_close_values': Fraction(result[0]['close_decimal']) == Fraction(result[1]['close_decimal']),
        'selected_contract_value': None, 'contract_candle_choice_certified': False,
        'revision_finality_certified': False, 'execution_authority': False}


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def capture(root: Path):
    root.mkdir(parents=True, exist_ok=False)
    (root / 'raw').mkdir()
    records = []
    for label, url in requests_by_label().items():
        started = time.time_ns()
        status, body, headers, error = 0, b'', {}, None
        try:
            request = Request(url, method='GET', headers={
                'User-Agent': 'AutoPrediction-PublicSourceResearch/0.1.2',
                'Accept': 'application/json, text/markdown;q=0.9', 'Cache-Control': 'no-cache'})
            with build_opener(NoRedirect()).open(request, timeout=15) as response:
                status, headers = response.status, dict(response.headers)
                body = response.read(MAX_BYTES + 1)
        except HTTPError as exc:
            status, headers = exc.code, dict(exc.headers)
            body, error = exc.read(MAX_BYTES + 1), 'HTTP_' + str(exc.code)
        except (OSError, URLError, ValueError) as exc:
            error = type(exc).__name__ + ': ' + str(exc)[:300]
        received = time.time_ns()
        if len(body) > MAX_BYTES:
            error = 'BODY_LIMIT_EXCEEDED'
        digest = sha256(body).hexdigest()
        path = root / 'raw' / (digest + '.bin')
        if path.exists():
            if path.read_bytes() != body:
                raise ValueError('raw source collision')
        else:
            path.write_bytes(body)
        records.append({'label': label, 'url': url, 'method': 'GET', 'status': status,
            'started_ns': started, 'received_ns': received, 'bytes': len(body),
            'body_sha256': digest, 'error': error,
            'headers': {k.lower(): v for k, v in headers.items()
                        if k.lower() in ('date', 'age', 'content-type', 'cache-control')}})
    write_json(root / 'requests.json', records)
    write_json(root / 'result.json', audit(root))


def audit(root: Path):
    """Recompute from raw bytes. A rehashed manifest is not authenticity proof.

    Retain the enclosing GitHub artifact digest as an independent byte anchor.
    The result never upgrades the production adapter's unknown assumptions.
    """
    records = json.loads((root / 'requests.json').read_text())
    if not isinstance(records, list) or len(records) != len(requests_by_label()):
        raise ValueError('source evidence population mismatch')
    expected, by_label = requests_by_label(), {}
    for record in records:
        if (not isinstance(record, dict) or 'error' not in record or
                record['error'] is not None and not isinstance(record['error'], str)):
            raise ValueError('source receipt schema/error status missing')
        label, digest = record.get('label'), record.get('body_sha256')
        if label not in expected or label in by_label or record.get('url') != expected[label] or record.get('method') != 'GET':
            raise ValueError('source request identity mismatch')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('invalid source digest')
        if (type(record.get('status')) is not int or not 0 <= record['status'] <= 599 or
                type(record.get('started_ns')) is not int or record['started_ns'] < 0 or
                type(record.get('received_ns')) is not int or record['received_ns'] < record['started_ns']):
            raise ValueError('source receipt clock/status invalid')
        body = (root / 'raw' / (digest + '.bin')).read_bytes()
        if (len(body) > MAX_BYTES + 1 or type(record.get('bytes')) is not int or len(body) != record['bytes'] or
                sha256(body).hexdigest() != digest):
            raise ValueError('source raw bytes mismatch')
        if record['status'] == 200 and record.get('error') is None and len(body) > MAX_BYTES:
            raise ValueError('oversize response cannot be admitted')
        by_label[label] = (record, body)
    result = {'schema': 's4.source-audit.v1', 'authority': 'SOURCE_OBSERVATION_ONLY',
        'documents': [{**by_label[label][0], 'interpretation': 'RETAINED_DOCUMENT_NOT_SEMANTIC_AUTHORITY'} for label in DOC_URLS],
        'probe_day': PROBE_DAY.isoformat(), 'candle_probe': None,
        'contract_final_value': None, 'realized_profit': None,
        'unresolved': list(UNRESOLVED_ASSUMPTIONS),
        'certificate_authority': False, 'live_execution': False}
    record, body = by_label['binance-candles']
    result['probe_receipt'] = record
    try:
        if record['status'] != 200 or record.get('error') is not None:
            raise ValueError('source API unavailable: ' + str(record['status']) + ':' + str(record.get('error')))
        parsed = json.loads(body, parse_float=str, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        # A response can arrive after candle close even when the server read an
        # unfinished interval. Both intervals must have ended before the request.
        # This still does NOT prove that historical values can never be revised.
        result['candle_probe'] = validate_candles(parsed, noon_ms(PROBE_DAY), record['started_ns'] // 1_000_000)
    except (ValueError, UnicodeDecodeError) as exc:
        result['candle_probe'] = {'status': 'NOT_ESTABLISHED', 'reason': str(exc), 'selected_contract_value': None}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    capture(args.output)
    print(json.dumps(audit(args.output), sort_keys=True))

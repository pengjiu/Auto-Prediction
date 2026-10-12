"""Offline replay of pinned original temporal capture bytes; never recaptures.

The small ZIP is a repackaging of the capture subtree, not the complete GitHub
artifact. Its index records both digests. Source-bound TypeScript compilation and
all economic controls are rerun; a process exiting zero with no admitted rows is
not an acceptance criterion. This is historical conditional evidence, not PnL.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import zipfile
from campaign import analyze

HERE = Path(__file__).resolve().parent
MAX_BYTES = 2_000_000
NAME = re.compile(r"capture/(?:config\.json|completion\.json|requests\.jsonl|raw/[0-9a-f]{64}\.bin)")


def unpack_capture(archive: Path, target: Path, index: dict) -> None:
    """Validate every entry before writing. The public CLI uses the pinned index."""
    if (index.get('schema') != 's5.raw-fixture-index.v1' or
            sha256(archive.read_bytes()).hexdigest() != index.get('archive_sha256')):
        raise ValueError('capture fixture checksum/index mismatch')
    expected = index.get('files')
    if not isinstance(expected, dict) or not 3 <= len(expected) <= 128:
        raise ValueError('invalid capture inventory')
    root = target.resolve()
    payloads = []
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        names = [i.filename for i in entries]
        if (len(set(names)) != len(names) or set(names) != set(expected) or
                sum(i.file_size for i in entries) > MAX_BYTES):
            raise ValueError('invalid capture inventory or size')
        for i in entries:
            mode = (i.external_attr >> 16) & 0o170000
            if (not NAME.fullmatch(i.filename) or mode not in (0, 0o100000) or
                    i.flag_bits & 1 or not (root / i.filename).resolve().is_relative_to(root)):
                raise ValueError('unsafe capture entry')
            raw = z.read(i)
            want = expected[i.filename]
            if (len(raw) != want['bytes'] or sha256(raw).hexdigest() != want['sha256']):
                raise ValueError('capture byte inventory mismatch')
            payloads.append((root / i.filename, raw))
    if any(path.exists() for path, _ in payloads):
        raise FileExistsError('capture extraction destination is not empty')
    for path, raw in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(raw)


def replay() -> dict:
    index = json.loads((HERE / 'fixtures/index.json').read_text())
    # Do not accept a caller-supplied filename, summary, rule table or trust root.
    archive = HERE / 'fixtures/temporal-capture-2026-10-12.zip'
    with TemporaryDirectory(prefix='pmh-temporal-replay-') as tmp:
        unpack_capture(archive, Path(tmp), index)
        report = analyze(Path(tmp) / 'capture')
    if (report['summary'] != index['expected_summary'] or
            report['protocol_completed'] is not True or report['live_execution'] is not False or
            report['realized_profit'] is not None):
        raise AssertionError('historical temporal replay changed: ' + json.dumps(report['summary']))
    return report


def write_report(output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    result = replay()
    with output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_report(args.output)['summary'], indent=2))

"""Offline CLI smoke of the original complete real capture; never recaptures."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import json
import zipfile
from analyze_real import analyze_capture

DIGEST = 'fac0590be30054a37d85775764d75bfe1fe59c6cc9d6ad533d02f307536f6e7a'


def replay():
    archive = Path(__file__).with_name('fixtures')/'real-binance'/'capture-2026-10-12.zip'
    if sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('original capture artifact checksum mismatch')
    with TemporaryDirectory(prefix='pmh-real-capture-') as tmp:
        root = Path(tmp).resolve()
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist()) > 5_000_000:
                raise ValueError('fixture exceeds bounded uncompressed size')
            for i in z.infolist():
                path = (root/i.filename).resolve()
                if not path.is_relative_to(root) or ((i.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('unsafe fixture archive path')
            z.extractall(root)
        report = analyze_capture(root/'real-family-evidence')
    summary = report['summary']
    if summary['families_source_admitted'] != 2 or summary['rounds_admitted'] != 16:
        raise AssertionError('real CLI silently lost expected evidence: '+json.dumps(report))
    if (summary['gross_positive_rounds'] != 0 or summary['same_depth_improvement_rounds'] != 0 or
            summary['exact_gross_witness_rounds'] != 16 or report['realized_profit'] is not None):
        raise AssertionError('recomputed historical fixture disagrees with exact bounded findings')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    result=replay()
    with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result['summary'],indent=2))

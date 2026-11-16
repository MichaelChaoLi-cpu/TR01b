#!/usr/bin/env python3
"""Cache official administrative polygons solely for source-coverage diagnosis.

Does not write data/raw or modify the analytical panel. Existing files are
validated and reused, never replaced. Fetch with --download.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/pilot/coverage-investigation/reference'
PAGE = 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html'
PREFECTURES = ['35', '40', '41', '42', '43', '44']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    html = urlopen(PAGE, timeout=45).read().decode('utf8') if args.download else None

    def one(code):
        name = f'N03-20240101_{code}_GML.zip'
        path = OUT / name
        if html:
            match = re.search(r"DownLd\('[^']+','" + re.escape(name) + r"','([^']+)'", html)
            if match is None:
                raise ValueError(f'Official page does not advertise {name}')
            url = urljoin(PAGE, match.group(1))
        else:
            url = f'https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2024/{name}'
        if not path.exists():
            if not args.download:
                raise FileNotFoundError(path)
            payload = urlopen(url, timeout=90).read()
            import io
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                assert archive.testzip() is None
            with path.open('xb') as stream:
                stream.write(payload)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            members = archive.namelist()
        return dict(prefecture_code=code, source_page=PAGE, url=url,
                    path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), members=members,
                    source_date='2024-01-01', role='diagnostic geographic reference, not an analytical source variable')

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, PREFECTURES))
    (OUT / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps([dict(prefecture_code=r['prefecture_code'], bytes=r['bytes'], sha256=r['sha256']) for r in records], indent=2))


if __name__ == '__main__':
    main()

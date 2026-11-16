#!/usr/bin/env python3
"""Cache official N03 references for the confirmed regional mesh classification.

Existing pilot reference archives are reused. No data/raw files are written.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/regional/reference'
PILOT = ROOT / 'data/exp/data-preprocessing/pilot/coverage-investigation/reference'
PAGE = 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    html = urlopen(PAGE, timeout=60).read().decode('utf8')
    page = OUT / 'official_source_page.html'
    if not page.exists():
        page.write_text(html)

    def one(code):
        name = f'N03-20240101_{code}_GML.zip'
        match = re.search(r"DownLd\('[^']+','" + re.escape(name) + r"','([^']+)'", html)
        assert match is not None, name
        url = urljoin(PAGE, match.group(1))
        existing = PILOT / name
        path = existing if existing.exists() else OUT / name
        if not path.exists():
            temporary = OUT / (name + '.part')
            with urlopen(url, timeout=120) as response, temporary.open('wb') as target:
                while payload := response.read(1024 * 1024):
                    target.write(payload)
            with zipfile.ZipFile(temporary) as archive:
                assert archive.testzip() is None
            temporary.rename(path)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            members = archive.namelist()
        return dict(prefecture_code=code, source_page=PAGE, url=url,
                    path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), members=members,
                    boundary_date='2024-01-01',
                    role='Fixed administrative polygon reference for regional classification; not a historical land mask')

    records = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = [pool.submit(one, f'{i:02d}') for i in range(1, 48)]
        for task in as_completed(tasks):
            records.append(task.result())
            if len(records) % 5 == 0 or len(records) == 47:
                print(f'Validated prefecture archives: {len(records)}/47', flush=True)
    records.sort(key=lambda row: row['prefecture_code'])
    (OUT / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Saved: {OUT.relative_to(ROOT)}/manifest.json', flush=True)


if __name__ == '__main__':
    main()

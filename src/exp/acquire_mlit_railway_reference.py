"""Acquire the official 2024 passenger-rail inventory without overwriting raw data.

This is candidate acquisition, not a selected explanatory-variable construction.
"""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin, urlparse
import hashlib
import json
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PAGE = 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2024.html'
NAME = 'N02-24_GML.zip'
RAW = ROOT / 'data/raw/railway/n02/2024'
OUT = ROOT / 'data/exp/data-augmentation-screening/mlit-facilities'


def main():
    html = urlopen(PAGE, timeout=45).read().decode('utf-8-sig')
    match = re.search(r"DownLd\('[^']+','" + re.escape(NAME) + r"','([^']+)'", html)
    assert match is not None, 'Official archive link missing'
    url = urljoin(PAGE, match.group(1))
    assert urlparse(url).hostname == 'nlftp.mlit.go.jp'
    path = RAW / NAME
    if not path.exists():
        with tempfile.TemporaryDirectory(prefix='tr01b-railway-') as scratch:
            temporary = Path(scratch) / NAME
            with urlopen(url, timeout=60) as response, temporary.open('wb') as target:
                expected = response.headers.get('Content-Length')
                while block := response.read(2**20): target.write(block)
            assert expected is None or temporary.stat().st_size == int(expected)
            with zipfile.ZipFile(temporary) as archive: assert archive.testzip() is None
            RAW.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as target, temporary.open('rb') as source:
                while block := source.read(2**20): target.write(block)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        members = archive.namelist()
    assert any('Station' in name and name.endswith('.shp') for name in members)
    OUT.mkdir(parents=True, exist_ok=True)
    record = dict(status='downloaded_and_zip_validated', source_page=PAGE, url=url,
                  path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                  sha256=hashlib.sha256(path.read_bytes()).hexdigest(), members=members,
                  reference_date='2024-12-31', candidate_year=2024, scientific_variable_selection='pending',
                  geometry='Passenger railway and station sections represented as lines',
                  no_existing_raw_file_overwritten=True, no_regression_or_processed_data_changed=True)
    (OUT / 'railway_download_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    (OUT / 'railway_source_page.html').write_text(html)
    print(json.dumps({k:v for k,v in record.items() if k != 'members'},indent=2),flush=True)


if __name__ == '__main__': main()

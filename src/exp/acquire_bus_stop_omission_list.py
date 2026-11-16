"""Acquire the P11 catalogue-linked omitted-stop list without overwriting originals."""
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/exp/data-augmentation-screening/bus-terminal-candidates'
PAGE = 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html'
URL = 'https://nlftp.mlit.go.jp/ksj/gml/codelist/P11-v3_0.xlsx'


def main():
    html = urlopen(PAGE, timeout=30).read()
    assert b'P11-v3_0.xlsx' in html
    path=ROOT/'data/raw/poi/p11/2022/auxiliary/P11-v3_0.xlsx'
    existed=path.exists()
    if not existed:
        payload=urlopen(URL,timeout=30).read()
        assert payload.startswith(b'PK')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream: stream.write(payload)
    with zipfile.ZipFile(path) as archive: assert archive.testzip() is None
    table=pd.read_excel(path,engine='openpyxl',dtype=str)
    assert list(table.columns)==['都道府県CD','都道府県','事業者名','バス停留所の名称']
    OUT.mkdir(parents=True,exist_ok=True)
    table.to_csv(OUT/'unlocated_stop_source_list.csv',index=False)
    with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest=dict(decision_id='MILI-D-20261010-015',url=URL,path=str(path.relative_to(ROOT)),
                  sha256=digest,bytes=path.stat().st_size,zip_crc_passed=True,
                  source_page=PAGE,reused_existing_file=existed,no_existing_raw_file_overwritten=True,
                  omitted_stop_records=len(table),coordinates_available=False,
                  scope='Source-linked P11 omitted-stop list; exact observation dates unverified; not geolocated stops')
    (OUT/'source_notes_download_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()

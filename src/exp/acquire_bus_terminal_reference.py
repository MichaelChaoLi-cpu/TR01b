"""Archive an official terminal reference and report limits without constructing exposure."""
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
import csv
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/exp/data-augmentation-screening/bus-terminals'
RAW = ROOT/'data/raw/bus_terminals/mlit_general/2026'
PAGE = 'https://www.mlit.go.jp/jidosha/jidosha_fr1_000004.html'
PDF = 'https://www.mlit.go.jp/jidosha/content/001999724.pdf'
CSV_RESOURCE = 'https://data.e-gov.go.jp/data/ja/dataset/mlit_20160325_0033/resource/4ec88266-ad82-4a69-9274-079d6a1b66d0'
DOCUMENT_RESOURCE = 'https://data.e-gov.go.jp/data/ja/dataset/mlit_20160325_0033/resource/e8b7d016-7607-4894-a193-458c2ac1cc1c'
TERMINAL_CSV = 'https://www.hokoukukan.go.jp/download/mlit_bus_terminal.csv'


def extract_rows(content):
    rows, preceding_phase = [], []
    for line in content.splitlines():
        match = re.match(r'^\s*(\d{1,2})\s+', line)
        if match:
            index = int(match.group(1))
            assert index == len(rows)+1
            rows.append(dict(source_row_number=index, source_row_text=line.strip()))
            if preceding_phase:
                rows[-1]['source_row_text'] += '\n'+'\n'.join(preceding_phase)
                preceding_phase = []
        elif '（第1期エリア）' in line:
            # The merged Yaesu row's first phase precedes its row-number baseline.
            preceding_phase.append(line.strip())
        elif rows and line.strip() and not re.search(r'小計|合計', line):
            rows[-1]['source_row_text'] += '\n'+line.strip()
    assert len(rows) == 26 and not preceding_phase
    assert '第1期' in rows[11]['source_row_text'] and '第2期' in rows[11]['source_row_text']
    assert '第1期' not in rows[10]['source_row_text']
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    html = urlopen(PAGE, timeout=30).read()
    assert PDF.split('/')[-1].encode() in html
    (OUT/'mlit_terminal_source_page.html').write_bytes(html)
    for name, url in [('egov_terminal_csv', CSV_RESOURCE), ('egov_terminal_explanation', DOCUMENT_RESOURCE)]:
        payload = urlopen(url, timeout=30).read()
        (OUT/(name+'_source_page.html')).write_bytes(payload)
    raw = RAW/'mlit_general_bus_terminals_2026-04-01.pdf'
    existed = raw.exists()
    if existed: payload = raw.read_bytes()
    else:
        payload = urlopen(PDF, timeout=30).read()
        assert payload.startswith(b'%PDF-')
        RAW.mkdir(parents=True, exist_ok=True)
        with raw.open('xb') as stream: stream.write(payload)
    assert payload.startswith(b'%PDF-')
    text_path = OUT/'general_terminal_reference_text.txt'
    subprocess.run(['pdftotext','-layout',str(raw),str(text_path)], check=True)
    content = text_path.read_text()
    assert re.search(r'令和\s*８\s*年\s*４\s*月\s*１\s*日', content)
    rows = extract_rows(content)
    with (OUT/'general_terminal_source_rows.csv').open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    attempts=[]
    try:
        with urlopen(TERMINAL_CSV, timeout=30) as response:
            available=response.read()
            attempts.append(dict(url=TERMINAL_CSV,status=response.status,bytes=len(available),
                                 observation_year='unverified', archived=False))
            # A newly available alternative still requires reference-date review.
            (OUT/'terminal_csv_candidate_response.bin').write_bytes(available)
    except HTTPError as error:
        attempts.append(dict(url=TERMINAL_CSV,status=error.code,archived=False))
    except Exception as error:
        attempts.append(dict(url=TERMINAL_CSV,status='unavailable',error=str(error),archived=False))
    subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','2400','-png',str(raw),str(OUT/'general_terminal_reference_preview')],check=True)
    manifest=dict(decision_id='MILI-D-20261010-014',status='partial reference acquired',
                  source_page=PAGE,download_url=PDF,path=str(raw.relative_to(ROOT)),
                  reference_date='2026-04-01',bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                  source_rows=26,declared_berths=326,reused_existing_file=existed,
                  no_existing_raw_file_overwritten=True,ordinary_bus_stop_substitution=False,
                  coverage='Statutory general bus terminals only; dedicated and other terminal hubs are not fully covered',
                  coordinates_in_source=False,operational_status_verified=False,
                  represents_2024=False,nearest_terminal_variable_constructed=False,
                  egov_metadata_updated='2023-04-17 (catalogue update, not verified observation date)',
                  alternate_csv_attempts=attempts)
    (OUT/'download_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__': main()

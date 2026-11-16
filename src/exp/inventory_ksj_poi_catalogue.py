"""Inventory KSJ facility/transport/tourism product pages, without GIS downloads."""
import csv
import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-augmentation-screening/ksj-poi-catalogue-20261010'
BASE = 'https://nlftp.mlit.go.jp/ksj/gml/datalist/'
PRODUCTS = [
    ('national_prefectural_offices', 'P28-2022'),
    ('municipal_offices_meeting_facilities', 'P05-2022'),
    ('municipal_offices_legacy', 'P34'), ('public_facilities_legacy', 'P02-2006'),
    ('police', 'P18'), ('fire_services', 'P17'), ('post_offices', 'P30'),
    ('welfare', 'P14-2023'), ('culture', 'P27'), ('water_supply', 'P21'),
    ('sewerage', 'P22'), ('waste_treatment', 'P15'), ('power_generation', 'P03'),
    ('fuel_stations', 'P07-2016'), ('new_towns', 'P26'),
    ('industrial_land_area_not_poi', 'L05'), ('research_institutions', 'P16'),
    ('local_industry', 'P24'), ('roadside_stations', 'P35'),
    ('prefectural_cultural_properties', 'P32'), ('world_cultural_heritage', 'A34-2022'),
    ('tourism_resources', 'P12-2014'), ('regional_resources', 'P19'),
    ('heliports', 'N11'), ('ports', 'C02-2014'), ('fishing_ports', 'C09'),
    ('scheduled_passenger_routes_nodes', 'N09'), ('expressway_nodes', 'N06-2025'),
    ('urban_parks_legacy', 'P13'), ('evacuation_facilities', 'P20'),
]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.rows = []
        self.row = None
        self.cell = None
        self.href = None
        self.anchor = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
        elif tag == 'a':
            self.href = dict(attrs).get('href')
            self.anchor = []

    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)
        if self.href is not None:
            self.anchor.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'a' and self.href is not None:
            self.links.append((' '.join(' '.join(self.anchor).split()), self.href))
            self.href = None


def acquire(product):
    key, template = product
    url = BASE + 'KsjTmplt-' + template + '.html'
    path = OUT / 'source-pages' / (key + '.html')
    if path.exists():
        raw = path.read_bytes()
    else:
        raw = urllib.request.urlopen(url, timeout=45).read()
        path.write_bytes(raw)
    page = Page()
    page.feed(raw.decode('utf-8-sig'))
    text = ' '.join(' '.join(page.text).split())
    headline = re.search(r'最新のデータは.{0,100}?(?:です。|。)', text)
    metadata = {}
    for row in page.rows:
        if len(row) >= 2 and row[0] in ('内容', 'データ基準年月日', 'データ基準年度', 'データ作成年度', 'データ形状', '識別子', 'その他の情報'):
            metadata[row[0]] = ' | '.join(row[1:])
    attribute_pattern = r'(?:P\d{2}|N\d{2}|C\d{2}|A\d{2}|L\d{2})[A-Za-z*※]*_\d{3,4}'
    attributes = [row for row in page.rows if len(row) >= 2 and re.search(attribute_pattern, ' '.join(row[:3]))
                  and not any('.zip' in item for item in row)]
    download_rows = [row for row in page.rows if len(row) >= 4 and any('.zip' in item for item in row)]
    years = sorted({y for row in download_rows for item in row[:4] for y in re.findall(r'(?:19|20)\d{2}(?=年)', item)})
    code_links = [{'label': label, 'url': urljoin(url, href)} for label, href in page.links if 'codelist/' in href]
    record = {'key': key, 'template': template, 'url': url, 'retrieved_date': '2026-10-10', 'sha256': hashlib.sha256(raw).hexdigest(),
              'latest_statement': headline.group() if headline else '', 'metadata': metadata,
              'download_table_years': years, 'attribute_rows': attributes, 'classification_links': code_links,
              'download_row_count': len(download_rows)}
    return record


def codebook(link):
    url = link['url']
    filename = url.rsplit('/', 1)[1]
    path = OUT / 'codebooks' / filename
    if path.exists():
        raw = path.read_bytes()
    else:
        raw = urllib.request.urlopen(url, timeout=45).read()
        path.write_bytes(raw)
    page = Page()
    page.feed(raw.decode('utf-8-sig'))
    return {'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'rows': page.rows}


def main():
    (OUT / 'source-pages').mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(acquire, PRODUCTS))
    (OUT / 'inventory.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    selected = ['CultureFacCd.html', 'PoliceStationCd.html', 'PubOfficeCd.html', 'HighwayConCd.html',
                'welfareInstitution_welfareFacilityMinorClassificationCode.html',
                'welfareInstitution_welfareFacilityMiddleClassificationCode.html',
                'welfareInstitution_welfareFacilityMajorClassificationCode.html',
                'PubFacMiclassCd.html', 'tourismResourceCategoryCd.html', 'postOfficeCd.html',
                'ResearchInstitutionCd.html', 'FacClassCd-v2_0.html', 'CityParkCd.html']
    links = {link['url']: link for r in records for link in r['classification_links']
             if link['url'].rsplit('/', 1)[1] in selected}
    (OUT / 'codebooks').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(codebook, links.values()))
    (OUT / 'classifications.json').write_text(json.dumps(codes, ensure_ascii=False, indent=2) + '\n')
    fields = ['key', 'template', 'url', 'latest_statement', 'download_table_years', 'geometry', 'scope', 'attribute_names']
    with (OUT / 'catalogue.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({'key': r['key'], 'template': r['template'], 'url': r['url'], 'latest_statement': r['latest_statement'],
                             'download_table_years': ';'.join(r['download_table_years']), 'geometry': r['metadata'].get('データ形状', ''),
                             'scope': r['metadata'].get('内容', ''), 'attribute_names': ';'.join(' | '.join(row[:2]) for row in r['attribute_rows'])})
            print(r['key'], r['latest_statement'], ','.join(r['download_table_years']), len(r['attribute_rows']))
    assert len(records) == 30 and len({r['url'] for r in records}) == 30
    assert all(r['latest_statement'] and r['metadata'].get('データ形状') and r['download_row_count'] for r in records)
    assert all(r['attribute_rows'] for r in records)
    print('Validated 30 product pages and', len(codes), 'classification pages; no GIS archives downloaded.')


if __name__ == '__main__':
    main()

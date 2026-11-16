"""Acquire the eighteen selected KSJ snapshots; preserve all existing raw files."""
import argparse
import hashlib
import io
import json
import re
import struct
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / 'data/exp/data-augmentation-screening/ksj-poi-catalogue-20261010'
OUT = ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities'
SELECTION = [
    ('fuel_stations', 'P07', 2015, 2016), ('roadside_stations', 'P35', 2018, 2018),
    ('expressway_nodes', 'N06', 2025, 2025), ('ports', 'C02', 2014, 2014),
    ('fishing_ports', 'C09', 2006, 2006), ('scheduled_passenger_routes_nodes', 'N09', 2012, 2012),
    ('heliports', 'N11', 2013, 2013), ('welfare', 'P14', 2023, 2023),
    ('culture', 'P27', 2013, 2013), ('municipal_offices_meeting_facilities', 'P05', 2022, 2022),
    ('national_prefectural_offices', 'P28', 2022, 2022), ('police', 'P18', 2012, 2012),
    ('fire_services', 'P17', 2012, 2012), ('post_offices', 'P30', 2013, 2013),
    ('research_institutions', 'P16', 2012, 2012), ('local_industry', 'P24', 2012, 2012),
    ('urban_parks_legacy', 'P13', 2011, 2011), ('tourism_resources', 'P12', 2014, 2014),
]


def archive_parts(archive, prefix=''):
    """Yield GIS-containing archives, including official national ZIP bundles."""
    assert archive.testzip() is None, 'ZIP CRC failure'
    members = archive.namelist()
    if any(name.lower().endswith('.shp') for name in members):
        yield archive, prefix
    else:
        nested = [name for name in members if name.lower().endswith('.zip')]
        assert nested, 'No shapefile or nested ZIP found'
        for name in nested:
            with zipfile.ZipFile(io.BytesIO(archive.read(name))) as child:
                yield from archive_parts(child, prefix + name + '::')


def inspect(path):
    tables, metadata, nested_archives = [], [], []
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        for part, prefix in archive_parts(archive):
            if prefix:
                nested_archives.append(prefix)
            for name in part.namelist():
                if name.lower().endswith('.dbf'):
                    with part.open(name) as stream:
                        header = stream.read(32)
                        count = struct.unpack('<I', header[4:8])[0]
                        header_length = struct.unpack('<H', header[8:10])[0]
                        fields = []
                        for _ in range((header_length - 33) // 32):
                            descriptor = stream.read(32)
                            raw_name = descriptor[:11].split(b'\0')[0]
                            try:
                                field = raw_name.decode('ascii')
                            except UnicodeDecodeError:
                                field = raw_name.decode('cp932')
                            fields.append(field)
                    tables.append(dict(member=prefix + name, records=count, fields=fields))
                if 'meta' in name.lower() and name.lower().endswith(('.xml', '.html', '.htm')):
                    raw = part.read(name)
                    for encoding in ('utf-8-sig', 'cp932'):
                        try:
                            text = raw.decode(encoding)
                            metadata.append(dict(member=prefix + name, dates_seen=sorted(set(re.findall(r'20\d{2}[-/]\d{2}[-/]\d{2}', text)))))
                            break
                        except UnicodeDecodeError:
                            pass
    assert tables, 'No attribute tables found'
    return members, tables, metadata, nested_archives


def download(job):
    path = ROOT / 'data/raw/poi' / job['code'].lower() / str(job['year']) / job['name']
    reused = path.exists()
    if not reused:
        with tempfile.TemporaryDirectory(prefix='tr01b-ksj-18-') as scratch:
            temporary = Path(scratch) / job['name']
            for attempt in range(3):
                try:
                    with urlopen(job['url'], timeout=60) as response, temporary.open('wb') as target:
                        length = response.headers.get('Content-Length')
                        while block := response.read(2**20):
                            target.write(block)
                    assert length is None or temporary.stat().st_size == int(length), 'Content-Length mismatch'
                    inspect(temporary)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('rb') as source, path.open('xb') as target:
                while block := source.read(2**20):
                    target.write(block)
    members, tables, metadata, nested = inspect(path)
    with path.open('rb') as stream:
        sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(**job, path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha256,
                reused_existing_archive=reused, zip_crc_passed=True, nested_archives=nested,
                members=members, attribute_tables=tables, metadata_date_inventory=metadata)


def prepare():
    catalogue = {r['key']: r for r in json.loads((CATALOGUE / 'inventory.json').read_text())}
    jobs = []
    coverage = []
    for kind, code, year, reference_year in SELECTION:
        page = catalogue[kind]['url']
        html = (CATALOGUE / 'source-pages' / (kind + '.html')).read_text(encoding='utf-8-sig')
        pattern = re.compile(r'^' + code + '-' + str(year)[2:] + r'(?:_\d{2})?(?:_GML)?\.zip$')
        links = {}
        for size, name, href in re.findall(r"DownLd\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'", html):
            if not pattern.fullmatch(name):
                continue
            url = urljoin(page, href)
            assert urlparse(url).hostname == 'nlftp.mlit.go.jp'
            links[name] = (url, size)
        national = [name for name in links if re.fullmatch(code + '-' + str(year)[2:] + r'(?:_GML)?\.zip', name)]
        if national:
            assert len(national) == 1
            selected = national
            scope = 'national_archive'
        else:
            selected = [name for name in links if (m := re.search(r'_(\d{2})(?:_GML)?\.zip$', name)) and 1 <= int(m.group(1)) <= 47]
            assert {int(re.search(r'_(\d{2})(?:_GML)?\.zip$', name).group(1)) for name in selected} == set(range(1, 48)), kind
            assert len(selected) == 47
            scope = '47_disjoint_prefectural_archives'
        for name in sorted(selected):
            url, size = links[name]
            jobs.append(dict(kind=kind, code=code, year=year, reference=f'Archive edition {year}; official reference edition {reference_year}',
                             reference_year=reference_year, page=page, name=name, url=url, advertised_size=size,
                             archive_selection_scope=scope))
        coverage.append(dict(kind=kind, code=code, archive_year=year, reference_year=reference_year,
                             scope=scope, expected_archives=len(selected)))
    assert len(coverage) == 18
    OUT.mkdir(parents=True, exist_ok=True)
    plan = dict(decision_id='MILI-D-20261010-020', categories=coverage, jobs=jobs,
                temporal_assumption='One unchanged snapshot repeated across 2002, 2003, 2004, 2010, 2024; actual source editions retained',
                gis_archives_expected=len(jobs), total_advertised_mb=sum(float(j['advertised_size'].replace('MB', '').strip()) for j in jobs))
    (OUT / 'acquisition_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    plan = prepare()
    if not args.download:
        print(json.dumps({k: v for k, v in plan.items() if k != 'jobs'}, indent=2))
        return
    records, errors = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks = {pool.submit(download, j): j for j in plan['jobs']}
        for task in as_completed(tasks):
            try:
                records.append(task.result())
            except Exception as error:
                errors.append(dict(job=tasks[task], error=type(error).__name__ + ': ' + str(error)))
            if (len(records) + len(errors)) % 10 == 0 or len(records) + len(errors) == len(tasks):
                checkpoint = dict(status='in_progress', records=records, errors=errors)
                (OUT / 'acquisition_checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n')
                print(f'Validated {len(records)}/{len(tasks)} archives; errors {len(errors)}', flush=True)
    records.sort(key=lambda r: (r['kind'], r['name']))
    result = dict(status='passed' if not errors else 'incomplete', decision_id=plan['decision_id'],
                  categories=plan['categories'], expected_archives=len(plan['jobs']), validated_archives=len(records),
                  total_bytes=sum(r['bytes'] for r in records), errors=errors, records=records,
                  no_existing_raw_file_overwritten=True, scientific_variables_constructed=False, regressions_refitted=False)
    (OUT / 'acquisition_manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('records', 'categories')}, indent=2), flush=True)
    assert not errors


if __name__ == '__main__':
    main()

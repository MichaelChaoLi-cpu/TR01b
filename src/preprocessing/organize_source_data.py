#!/usr/bin/env python3
"""Catalogue public source files and acquire immutable archives; no variable construction.

Uses Python's standard library. Run from any terminal:
  python3 src/preprocessing/organize_source_data.py --catalog
  python3 src/preprocessing/organize_source_data.py --download pilot
  python3 src/preprocessing/organize_source_data.py --download road-mesh
  python3 src/preprocessing/organize_source_data.py --download population
Snapshots and archives are never overwritten. No Git or DVC commands are executed.
"""
import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-organization'
SNAPSHOT = OUT / 'source-metadata/2026-10-08'
POP_IDS = {1995: 'T000751', 2000: 'T000146', 2005: 'T000148',
           2010: 'T000608', 2020: 'T001100'}
ROAD_URLS = {
    'n04': 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N04.html',
    'n13': 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N13-2024.html',
    'n01': 'https://nlftp.mlit.go.jp/ksj/gmlold/datalist/gmlold_KsjTmplt-N01.html',
    'datacite': 'https://api.datacite.org/dois/10.7910/DVN/YGIVCD',
}
FIELDS = ['source', 'observation_year', 'region', 'filename', 'source_page',
          'download_url', 'listed_size_mb', 'local_path', 'status', 'bytes',
          'sha256', 'retrieved_at_utc', 'source_content_disposition', 'expected_md5',
          'dataset_version', 'publication_date', 'error']


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def csv_write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def save_snapshot(name, url):
    path = SNAPSHOT / name
    if path.exists():
        return path
    req = urllib.request.Request(url, headers={'User-Agent': 'TR01b-research-source-catalog/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = response.read()
    # Do not save a transient response as an official metadata snapshot.
    if name.endswith('.json'):
        json.loads(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(data)
    with (SNAPSHOT / 'retrievals.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'file': name, 'url': url, 'utc': utc(),
                            'sha256': hashlib.sha256(data).hexdigest()}) + '\n')
    return path


def population_params(year, page=1):
    params = dict(page=page, type=1, toukeiCode='00200521', toukeiYear=year,
                  aggregateUnit='S', serveyId=f'S00200511{year}',
                  statsId=POP_IDS[year], mesh_data_flg=1, download_disp_flg=1)
    if year == 2020:
        params['datum'] = 2000
    return params


def catalogue():
    for key, url in ROAD_URLS.items():
        save_snapshot(key + ('.json' if key == 'datacite' else '.html'), url)
    for year in POP_IDS:
        base = 'https://www.e-stat.go.jp/gis/statmap-search/search_detail?'
        first = save_snapshot(f'estat-{year}-files-1.json',
                              base + urllib.parse.urlencode(population_params(year)))
        pagination = json.loads(first.read_text())['paginate']
        match = re.search(r'1\s*/\s*(\d+)ページ', re.sub('<[^>]+>', '', pagination))
        if not match:
            raise ValueError(f'Cannot verify population pagination for {year}')
        pages = int(match[1])
        for page in range(2, pages + 1):
            save_snapshot(f'estat-{year}-files-{page}.json',
                          base + urllib.parse.urlencode(population_params(year, page)))
        print(f'population {year}: {pages} catalogue pages', flush=True)


def row(source, year, region, filename, page, url, mb='', folder=None):
    folder = folder or f'{source}/{year}'
    result = {k: '' for k in FIELDS}
    result.update(source=source, observation_year=year, region=region,
                  filename=filename, source_page=page, download_url=url,
                  listed_size_mb=mb, local_path=f'data/raw/{folder}/{filename}', status='catalogued')
    return result


def build_manifest():
    rows = []
    for code in ['n04', 'n13']:
        text = (SNAPSHOT / f'{code}.html').read_text(encoding='utf-8')
        links = re.findall(r"DownLd\('([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'", text)
        for size, name, link in links:
            if code == 'n04':
                match = re.fullmatch(r'N04-(02|03|04|10)_(\d{4})-jgd_GML.zip', name)
                if not match:
                    continue
                year, region = 2000 + int(match[1]), match[2]
                source = 'roads/n04_mesh'
            else:
                match = re.fullmatch(r'N13-24_(\d{4})_GEOJSON.zip', name)
                if not match:
                    continue
                year, region, source = 2024, match[1], 'roads/n13_lines'
            mb = re.search(r'[0-9.]+', size)[0]
            rows.append(row(source, year, region, name, ROAD_URLS[code],
                            urllib.parse.urljoin('https://nlftp.mlit.go.jp', link), mb))
    for region in ['40', '48']:
        name = f'N01-07L-{region}-01.0a_GML.zip'
        rows.append(row('roads/n01_lines', 1995, 'national' if region == '48' else 'Fukuoka-prefecture',
                        name, ROAD_URLS['n01'],
                        f'https://nlftp.mlit.go.jp/ksj/gmlold/data/N01/N01-07L/{name}'))
    for year, stats_id in POP_IDS.items():
        for path in sorted(SNAPSHOT.glob(f'estat-{year}-files-*.json')):
            detail = json.loads(path.read_text())['detail']
            for url in re.findall(r'href="([^\"]*?/gis/statmap-search/data[^\"]*)"', detail):
                url = html.unescape(url)
                params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                if params.get('statsId') != [stats_id] or params.get('downloadType') != ['2']:
                    continue
                region = params['code'][0]
                page = 'https://www.e-stat.go.jp/gis/statmap-search?' + urllib.parse.urlencode(population_params(year))
                rows.append(row('population/estat_1km', year, region,
                                f'{stats_id}_{region}.zip', page,
                                urllib.parse.urljoin('https://www.e-stat.go.jp', url)))
    # Download URLs and MD5 values read from each public file's Metadata tab.
    for year, file_id, size, md5 in [
            (1995,13295258,72.6,'9ccaf9e04ae0e77ad00d87bb8f791f7b'),
            (2002,13295249,137.9,'d9db2a4b3565564abd4a72df6377ff9d'),
            (2003,13295255,139.1,'4ffc276f22ef9842ebf3422bf54c5d08'),
            (2004,13295259,139.8,'be141cbc72966b42c5cb020cc6296fb1'),
            (2010,13295266,149.9,'c68bcd57d2fff2e5afca2c351f037d9f'),
            (2024,14085059,93.9,'42cd3ec905b58b097e24b5c44292e269')]:
        item = row('nighttime_lights/viirs_like_v2', year, 'global', f'{year}_Version2.zip',
                   f'https://dataverse.harvard.edu/file.xhtml?fileId={file_id}&version=10.1',
                   f'https://dataverse.harvard.edu/api/access/datafile/{file_id}', size,
                   f'nighttime_lights/viirs_like_v2/dataset_10.1/{year}')
        item.update(expected_md5=md5, dataset_version='10.1',
                    publication_date='2026-07-18' if year==2024 else '2025-12-31')
        rows.append(item)
    by_path = {r['local_path']: r for r in rows}
    old = OUT / 'tables/download_manifest.csv'
    if old.exists():
        with old.open(encoding='utf-8', newline='') as f:
            for prev in csv.DictReader(f):
                if prev['local_path'] in by_path:
                    for key in ['status','bytes','sha256','retrieved_at_utc','source_content_disposition','error']:
                        by_path[prev['local_path']][key] = prev[key]
    return sorted(by_path.values(), key=lambda r: (r['source'], int(r['observation_year']), r['region']))


def acquire(item, import_dir=None):
    item = dict(item)
    target = ROOT / item['local_path']
    temp = target.with_suffix(target.suffix + '.part')
    try:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            imported = Path(import_dir) / item['filename'] if import_dir else None
            if imported and imported.exists():
                shutil.copyfile(imported, temp)
                item['source_content_disposition'] = 'Imported byte-for-byte from previously downloaded official archive'
            else:
                if not item['download_url']:
                    raise ValueError('Use the verified public file page to download this archive')
                req = urllib.request.Request(item['download_url'], headers={'User-Agent':'TR01b-research-source-catalog/1.0'})
                with urllib.request.urlopen(req, timeout=90) as response, temp.open('wb') as f:
                    item['source_content_disposition'] = response.headers.get('Content-Disposition', '')
                    if 'text/html' in response.headers.get('Content-Type', ''):
                        raise ValueError('HTML response instead of source archive')
                    shutil.copyfileobj(response, f, length=1024 * 1024)
            with zipfile.ZipFile(temp) as archive:
                if archive.testzip() is not None:
                    raise ValueError('ZIP CRC verification failed')
            # Existing source material must never be replaced.
            if target.exists():
                raise FileExistsError(target)
            temp.rename(target)
            item['retrieved_at_utc'] = utc()
        else:
            with zipfile.ZipFile(target) as archive:
                if archive.testzip() is not None:
                    raise ValueError('Existing ZIP CRC verification failed; source preserved')
        digest = hashlib.sha256()
        md5 = hashlib.md5()
        with target.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''):
                digest.update(chunk)
                md5.update(chunk)
        current = digest.hexdigest()
        if item['sha256'] and current != item['sha256']:
            raise ValueError('Checksum changed since acquisition; source preserved')
        if item['expected_md5'] and md5.hexdigest() != item['expected_md5']:
            raise ValueError('Provider MD5 differs; do not use archive; source preserved')
        item.update(status='downloaded_verified', bytes=target.stat().st_size, sha256=current, error='')
    except Exception as exc:
        item.update(status='download_failed', error=str(exc))
        if temp.exists():
            temp.unlink()  # Only incomplete files created by this script are removed.
    return item


def outputs(rows):
    csv_write(OUT/'tables/download_manifest.csv', rows, FIELDS)
    periods = []
    # Human revision MILI-D-20261009-001 excludes 1995 from the analytical design.
    # Acquired historical archives remain in the acquisition manifest.
    for road, pop in [(2002,2000),(2003,2005),(2004,2005),(2010,2010),(2024,2020)]:
        periods.append(dict(panel_period=road, road_year=road, population_year=pop, ntl_year=road,
                            population_offset_years=pop-road, population_gap_years=abs(pop-road),
                            population_year_reused=int(pop==2005),
                            road_source='N13' if road==2024 else 'N04',
                            road_comparability='unresolved', panel_status='candidate_only'))
    csv_write(OUT/'tables/period_matching.csv',periods,list(periods[0]))
    groups = {}
    for r in rows:
        key = r['source'], r['observation_year']
        g = groups.setdefault(key,dict(source=key[0],year=key[1],catalogued_files=0,
                                       verified_files=0,verified_bytes=0,failed_files=0))
        g['catalogued_files'] += 1
        if r['status']=='downloaded_verified':
            g['verified_files'] += 1;g['verified_bytes'] += int(r['bytes'])
        if r['status']=='download_failed':g['failed_files'] += 1
    csv_write(OUT/'tables/acquisition_summary.csv',list(groups.values()),list(next(iter(groups.values()))))
    print(json.dumps({'manifest_files':len(rows),'statuses':dict(Counter(r['status'] for r in rows))}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',action='store_true')
    parser.add_argument('--download',nargs='+',choices=['pilot','road-mesh','population','road-lines','nighttime-lights'])
    parser.add_argument('--import-dir',help='Optional previously downloaded official road archives')
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if not 1 <= args.workers <= 4:parser.error('Use 1-4 workers')
    if args.catalog:catalogue()
    rows=build_manifest();outputs(rows)
    if not args.download:return
    sources={'road-mesh':'roads/n04_mesh','population':'population/estat_1km',
             'road-lines':'roads/n13_lines','nighttime-lights':'nighttime_lights/viirs_like_v2'}
    selected_sources={sources[mode] for mode in args.download if mode!='pilot'}
    selected=[r for r in rows if r['source'] in selected_sources or
              ('pilot' in args.download and r['region'] in ['5030','national','Fukuoka-prefecture']
               and not r['source'].startswith('nighttime'))]
    by_path={r['local_path']:r for r in rows}
    with ThreadPoolExecutor(args.workers) as pool:
        futures=[pool.submit(acquire,r,args.import_dir) for r in selected]
        for n,future in enumerate(as_completed(futures),1):
            result=future.result();by_path[result['local_path']]=result
            if result['status']=='download_failed':print(result['filename'],result['error'],flush=True)
            if n%25==0 or n==len(futures):
                print(f'Checked {n}/{len(futures)} archives',flush=True)
                outputs(list(by_path.values()))
    if any(r['status']=='download_failed' for r in by_path.values()):raise SystemExit(1)


if __name__=='__main__':main()

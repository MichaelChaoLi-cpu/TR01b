"""Download unmodified NASA ORNL MCD12Q1 pixel subsets, with resumable archives.

The public TESViS API supplies native sinusoidal pixels without resampling.
Original HTTP response bytes are gzip archived; existing files are never replaced.
The request plan is prepared from the complete national mesh extent, not population.
"""
from pathlib import Path
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
RAW = ROOT / 'data/raw/land_cover/modis/mcd12q1_061/ornl_subsets'
BASE = 'https://modis.ornl.gov/rst/api/v1/MCD12Q1/'
YEARS = ((2002, 2004), (2010, 2010), (2024, 2024))


def metadata():
    """Catalogue version evidence and small all-band source inventories."""
    folder = RAW.parent / 'metadata'
    folder.mkdir(parents=True, exist_ok=True)
    locations = [(33.61, 130.33), (43.1, 141.4), (35.65, 139.8), (27.1, 142.2)]
    urls = [(BASE + 'bands', 'bands.json.gz')]
    for j, (lat, lon) in enumerate(locations):
        query = dict(latitude=lat, longitude=lon, startDate='A2024001', endDate='A2024001',
                     kmAboveBelow=1, kmLeftRight=1)
        urls.append((BASE + 'subset?' + urllib.parse.urlencode(query), f'probe_{j}_2024_all_bands.json.gz'))
    for year in (2002, 2003, 2004, 2010, 2024):
        urls.append((f'https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/61/MCD12Q1/{year}/001/',
                     f'lads_catalogue_{year}.html.gz'))
    records = []
    for url, name in urls:
        dest = folder / name
        if not dest.exists():
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers={
                            'User-Agent': 'TR01b', 'Accept': 'application/json'}), timeout=60) as r:
                        body = r.read()
                    if name.endswith('json.gz'):
                        json.loads(body)
                    dest.open('xb').write(gzip.compress(body, mtime=0))
                    break
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(2 + 2 * attempt)
        records.append(dict(url=url, path=str(dest.relative_to(ROOT)),
                            sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
        print('Metadata archived:', name, flush=True)
    (OUT / 'metadata_manifest.json').write_text(json.dumps(dict(records=records), indent=2) + '\n')


def validate(body, band, start, end):
    value = json.loads(body)
    assert value['band'] == band
    assert abs(float(value['cellsize']) - 463.312716528) < 1e-6
    subsets = value['subset']
    dates = [int(s['calendar_date'][:4]) for s in subsets]
    assert dates == list(range(start, end + 1)), dates
    assert all(s['band'] == band for s in subsets)
    assert all(len(s['data']) == int(value['nrows']) * int(value['ncols']) for s in subsets)
    return value


def download(task):
    block, band, start, end, radius = task
    suffix = f"{block['block']}_{band}_{start}-{end}_radius{radius}.json.gz"
    dest = RAW / suffix
    query = dict(latitude=block['latitude'], longitude=block['longitude'],
                 band=band, startDate=f'A{start}001', endDate=f'A{end}001',
                 kmAboveBelow=radius, kmLeftRight=radius)
    url = BASE + 'subset?' + urllib.parse.urlencode(query)
    try:
        if dest.exists():
            body = gzip.decompress(dest.read_bytes())
            value = validate(body, band, start, end)
            assert abs(float(value['latitude']) - block['latitude']) < 1e-9
            assert abs(float(value['longitude']) - block['longitude']) < 1e-9
        else:
            for attempt in range(5):
                try:
                    request = urllib.request.Request(url, headers={
                        'Accept': 'application/json', 'User-Agent': 'TR01b MODIS research preprocessing'})
                    with urllib.request.urlopen(request, timeout=90) as response:
                        body = response.read()
                    value = validate(body, band, start, end)
                    with dest.open('xb') as stream:
                        stream.write(gzip.compress(body, mtime=0))
                    break
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(1 + attempt * 2)
        return dict(status='downloaded', block=block['block'], band=band,
                    years=list(range(start, end + 1)), request=url,
                    window_adjustment=block.get('window_adjustment'),
                    path=str(dest.relative_to(ROOT)), bytes=dest.stat().st_size,
                    sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                    response_sha256=hashlib.sha256(body).hexdigest(),
                    cellsize=value['cellsize'], xllcorner=value['xllcorner'],
                    yllcorner=value['yllcorner'], nrows=value['nrows'], ncols=value['ncols'],
                    granules=[{k: v for k, v in item.items() if k != 'data'}
                              for item in value['subset']])
    except Exception as exc:
        return dict(status='failed', block=block['block'], band=band,
                    years=list(range(start, end + 1)), request=url,
                    error=f'{type(exc).__name__}: {exc}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--limit-blocks', type=int)
    parser.add_argument('--metadata', action='store_true')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    if args.metadata:
        metadata()
        return
    plan = json.loads((OUT / 'subset_plan.json').read_text())
    blocks = plan['requests'][:args.limit_blocks]
    jobs = [(b, band, start, end, plan['request_radius_km'])
            for b in blocks for band in plan['bands'] for start, end in YEARS]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download, job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if result['status'] == 'failed' or len(results) % 12 == 0:
                print(f"Requests {len(results)}/{len(jobs)}; {result['block']} "
                      f"{result['band']} {result['years']} {result['status']}", flush=True)
            (OUT / 'download_manifest.json').write_text(json.dumps(dict(
                product='MCD12Q1', collection='6.1 (source processing identifiers require catalogue verification)',
                provider='NASA ORNL DAAC TESViS', raw_response_format='gzip-compressed original HTTP JSON',
                years=plan['years'], planned_requests=len(jobs), finished_requests=len(results),
                records=sorted(results, key=lambda r: (r['block'], r['band'], r['years'][0]))),
                indent=2) + '\n')
    failed = sum(r['status'] == 'failed' for r in results)
    print(json.dumps(dict(requests=len(results), failed=failed,
                         compressed_bytes=sum(r.get('bytes', 0) for r in results))), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Archive unmodified UMD subsets; reuse the approved national MODIS request grid."""
import argparse
import concurrent.futures
import json
from pathlib import Path
from acquire_modis_land_cover import download, YEARS, ROOT, RAW

OUT = ROOT / 'data/exp/data-preprocessing/modis-umd'
PLAN = ROOT / 'data/exp/data-preprocessing/modis-land-cover/subset_plan.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    jobs = [(b, 'LC_Type2', start, end, plan['request_radius_km'])
            for b in plan['requests'] for start, end in YEARS]
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download, job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            records.append(result)
            manifest = dict(product='MCD12Q1', collection='6.1', classification='UMD',
                            decision_id='MILI-D-20261011-019', years=plan['years'],
                            provider='NASA ORNL DAAC TESViS', planned_requests=len(jobs),
                            finished_requests=len(records), records=sorted(records,
                                key=lambda r: (r['block'], r['years'][0])))
            pending = OUT / 'download_manifest.pending.json'
            pending.write_text(json.dumps(manifest, indent=2) + '\n')
            pending.replace(OUT / 'download_manifest.json')
            if len(records) % 6 == 0 or result['status'] != 'downloaded':
                print(f"UMD requests {len(records)}/{len(jobs)}; {result['block']} {result['years']}: {result['status']}", flush=True)
    failed = sum(r['status'] != 'downloaded' for r in records)
    print(json.dumps({'requests':len(records), 'failed':failed,
                      'compressed_bytes':sum(r.get('bytes',0) for r in records)}), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

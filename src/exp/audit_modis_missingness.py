"""Explain MODIS mesh NaNs from native QC and saved area weights; no recoding.

Focused missingness diagnostic: annual processed files and original pixel
mosaics are read-only. Count mesh-period records, not independent pixels.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
OUT = ROOT / 'data/exp/data-briefing/modis-missingness-reasons'
YEARS = [2002, 2003, 2004, 2010, 2024]
TOL = 1e-9  # Ignore geometric roundoff, consistent with coverage validation.


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ids = np.load(SOURCE / 'native_pixel_ids.npy')
    coords = np.load(SOURCE / 'mesh_coordinates.npz')
    n = len(coords['codes'])
    totals, examples, pixel_tables, validations = [], [], [], []
    for year in YEARS:
        path = ROOT / f'data/processed/national/modis_land_cover/modis_land_cover_{year}_preprocessed.parquet'
        checksum = sha(path)
        d = pd.read_parquet(path)
        assert np.array_equal(d['Mesh Code'].to_numpy(), coords['codes'])
        pixels = np.load(SOURCE / f'native_pixels_{year}.npz')
        lc, qc = pixels['LC_Type1'], pixels['QC']
        present = pixels['published_tile'] & pixels['response_pixel_present']
        pairs, counts = np.unique(np.stack([lc, qc], axis=1), axis=0, return_counts=True)
        pixel_tables.extend(dict(year=year, LC_Type1=int(a), QC=int(b), native_pixels=int(c))
                            for (a, b), c in zip(pairs, counts, strict=True))
        assert not np.any(present & (qc == 3) & (lc != 17))
        assert not np.any(pixels['published_tile'] & ~pixels['response_pixel_present'])
        masks = {'qc3_water': present & (qc == 3),
                 'qc1_land': present & (qc == 1),
                 'raw_water': present & (lc == 17),
                 'other_excluded': present & ~np.isin(qc, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                 'source': present}
        area = {k: np.zeros(n) for k in masks}
        for weight_path in sorted((SOURCE / 'overlap-weights').glob('*.npz')):
            with np.load(weight_path) as w:
                start, end = int(w['start']), int(w['end'])
                pid = (w['row'].astype(np.int64) * 86400 + w['column']).astype(np.uint32)
                positions = np.searchsorted(ids, pid)
                assert np.array_equal(ids[positions], pid)
                local = w['mesh'] - start
                for key, mask in masks.items():
                    area[key][start:end] = np.bincount(
                        local, weights=w['weight'] * mask[positions], minlength=end-start)
        source_error = float(np.max(np.abs(area['source'] - d['Land Cover Source Coverage'])))
        unclassified_error = float(np.max(np.abs(area['qc3_water'] + area['qc1_land']
                                                - d['Land Cover Unclassified Share'])))
        assert max(source_error, unclassified_error) < TOL
        missing = d['Land Cover No Valid Pixels'].to_numpy()
        absent = area['source'] <= TOL
        water, land = area['qc3_water'] > TOL, area['qc1_land'] > TOL
        reason = np.full(n, 'other_or_roundoff', dtype='U40')
        reason[water & ~land] = 'unclassified_water_only'
        reason[land & ~water] = 'unclassified_land_only'
        reason[land & water] = 'mixed_unclassified_land_water'
        reason[absent] = 'source_entirely_absent'
        full_water = missing & (area['qc3_water'] >= 1 - TOL)
        item = dict(year=year, grid_meshes=n, missing_meshes=int(missing.sum()),
                    fully_qc3_water_meshes=int(full_water.sum()),
                    missing_with_any_qc1_land=int((missing & land).sum()),
                    missing_with_partial_source=int((missing & ~absent & (area['source'] < 1-TOL)).sum()),
                    published_pixels_not_downloaded=int((pixels['published_tile'] & ~pixels['response_pixel_present']).sum()))
        for key in ['unclassified_water_only', 'unclassified_land_only',
                    'mixed_unclassified_land_water', 'source_entirely_absent', 'other_or_roundoff']:
            select = missing & (reason == key)
            item[key] = int(select.sum())
            for index in np.flatnonzero(select)[:10]:
                examples.append(dict(year=year, mesh_code=str(coords['codes'][index]), reason=key,
                                     longitude=float(coords['lon'][index]), latitude=float(coords['lat'][index]),
                                     **{k: float(v[index]) for k, v in area.items()}))
        assert sum(item[k] for k in np.unique(reason[missing])) == item['missing_meshes']
        assert sha(path) == checksum
        validations.append(dict(year=year, source_sha256=checksum,
                                maximum_source_coverage_error=source_error,
                                maximum_unclassified_share_error=unclassified_error))
        totals.append(item)
        print(json.dumps(item), flush=True)
    pd.DataFrame(totals).to_csv(OUT / 'annual_reasons.csv', index=False)
    pd.DataFrame(examples).to_csv(OUT / 'example_meshes.csv', index=False)
    pd.DataFrame(pixel_tables).to_csv(OUT / 'native_class_quality_counts.csv', index=False)
    sums = {k: sum(r[k] for r in totals) for k in totals[0] if k != 'year'}
    assert sums['missing_meshes'] == 2209485
    report = dict(status='passed', totals=sums, years=totals, validations=validations,
                  count_unit='mesh-period record; five annual grids',
                  tolerance=TOL, source_or_processed_data_modified=False,
                  interpretation='QC3 identifies unclassified water using the product water mask; LC_Type1 is 17. '
                                 'This is not evidence that the annual reflectance classification is valid. '
                                 'Water includes ocean and inland water; no separate coastline mask is applied.',
                  official_guide='https://lpdaac.usgs.gov/documents/1409/MCD12_User_Guide_V61.pdf')
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# MODIS missingness: source and QC diagnosis', '',
             'Read-only reconstruction from native LC_Type1/QC pixels and existing mesh intersection weights. '
             'All five processed input checksums are unchanged. No recoding, sample deletion, regression or AnaSOP edit.', '',
             '| Cause among six-share NaN records | Five-period records |',
             '| --- | ---: |']
    for key in ['unclassified_water_only', 'unclassified_land_only', 'mixed_unclassified_land_water',
                'source_entirely_absent', 'other_or_roundoff']:
        lines.append(f'| {key} | {sums[key]:,} |')
    lines += ['', f"Total: {sums['missing_meshes']:,} out of {sums['grid_meshes']:,} mesh-period records. "
              f"{sums['fully_qc3_water_meshes']:,} records are entirely QC3 water within numeric tolerance. "
              f"{sums['missing_with_partial_source']:,} missing records have partial source coverage.", '',
              'QC3 means unclassified water based on the product water mask. All QC3 source pixels are LC_Type1=17. '
              'QC1 is unclassified land. The current construction excludes both, making all six shares NaN '
              'when accepted coverage is zero. This grid is a union of complete primary mesh tiles and includes water. '
              'These statistics do not measure the missing fraction of Japanese land. '
              'No missing download pixels were found within published tiles. Entirely missing source cells '
              'are in the previously documented unpublished h32v06 tile. Water type (ocean/inland) is not separately audited.', '',
              'Reproduce: `python3 src/exp/audit_modis_missingness.py`. See annual_reasons.csv, '
              'native_class_quality_counts.csv and example_meshes.csv for supporting counts.']
    (OUT / 'README.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(sums), flush=True)


if __name__ == '__main__':
    main()

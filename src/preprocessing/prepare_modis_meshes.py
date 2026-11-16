"""Construct annual mesh area shares only after the human rule confirmation.

Run after source_mosaic_validation and independent_geometry_validation pass.
The generated per-year preprocessing scripts then supply the readable outputs.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

from modis_mesh_overlap import CELL, WORLD_COLS, OUT, ROOT

DEST = ROOT / 'data/processed/national/modis_land_cover'
GROUPS = {
    'urban_share': ('Urban Land Cover Share', [13]),
    'forest_share': ('Forest Land Cover Share', [1, 2, 3, 4, 5]),
    'cropland_share': ('Cropland Land Cover Share', [12]),
    'cropland_mosaic_share': ('Cropland Mosaic Land Cover Share', [14]),
    'water_share': ('Water Land Cover Share', [17]),
    'other_share': ('Other Land Cover Share', [6, 7, 8, 9, 10, 11, 15, 16]),
}
REFERENCES = {
    'mesh_code': 'Mesh Code', 'land_cover_year': 'Land Cover Year',
    'source_coverage': 'Land Cover Source Coverage', 'valid_coverage': 'Land Cover Coverage',
    'unclassified_share': 'Land Cover Unclassified Share', 'no_data_share': 'Land Cover No Data Share',
    'adjusted_share': 'Land Cover Adjusted Share',
    'incomplete_coverage': 'Land Cover Incomplete Coverage',
    'no_valid_pixels': 'Land Cover No Valid Pixels', 'product': 'Land Cover Product',
    'mesh_area': 'Land Cover Mesh Area',
}


def main():
    contract = json.loads((OUT / 'proposed_construction.json').read_text())
    assert contract['confirmed'], 'Human variable-construction confirmation is still pending.'
    assert contract.get('construction_decision_id'), 'Require the recorded human construction decision.'
    for name in ['source_mosaic_validation.json', 'independent_geometry_validation.json']:
        assert json.loads((OUT / name).read_text())['status'] == 'passed'
    DEST.mkdir(parents=True, exist_ok=True)
    inputs = OUT / 'confirmed-inputs'; inputs.mkdir(exist_ok=True)
    coordinates = np.load(OUT / 'mesh_coordinates.npz')
    codes = coordinates['codes']; n = len(codes)
    pixel_ids = np.load(OUT / 'native_pixel_ids.npy')
    weights = sorted((OUT / 'overlap-weights').glob('*.npz'))
    datasets, audits, summaries = {}, [], []
    for year in contract['years']:
        pixels = np.load(OUT / f'native_pixels_{year}.npz')
        lc, qc = pixels['LC_Type1'], pixels['QC']
        source = pixels['published_tile'] & pixels['response_pixel_present']
        unclassified = source & np.isin(qc, [1, 3])
        valid = source & (lc >= 1) & (lc <= 17) & np.isin(qc, [0, 2, 4, 5, 6, 7, 8, 9])
        adjusted = valid & np.isin(qc, [4, 5, 6, 7, 8, 9])
        result = {key: np.zeros(n) for key in GROUPS}
        for key in ['source_coverage', 'valid_coverage', 'unclassified_share', 'adjusted_share', 'mesh_area']:
            result[key] = np.zeros(n)
        for path in weights:
            w = np.load(path)
            start, end = int(w['start']), int(w['end']); length = end - start
            identifiers = (w['row'].astype(np.int64) * WORLD_COLS + w['column']).astype(np.uint32)
            positions = np.searchsorted(pixel_ids, identifiers)
            assert np.array_equal(pixel_ids[positions], identifiers)
            local = w['mesh'] - start; share = w['weight']
            def aggregate(mask):
                return np.bincount(local, weights=share * mask, minlength=length)
            for key, (_, classes) in GROUPS.items():
                result[key][start:end] = aggregate(valid[positions] & np.isin(lc[positions], classes))
            for key, mask in [('source_coverage', source), ('valid_coverage', valid),
                              ('unclassified_share', unclassified), ('adjusted_share', adjusted)]:
                result[key][start:end] = aggregate(mask[positions])
            result['mesh_area'][start:end] = w['mesh_area_km2']
        sum_shares = sum(result[key] for key in GROUPS)
        assert np.max(np.abs(sum_shares - result['valid_coverage'])) < 1e-9
        assert (result['valid_coverage'] <= result['source_coverage'] + 1e-9).all()
        result['no_data_share'] = 1 - result['valid_coverage'] - result['unclassified_share']
        assert result['no_data_share'].min() > -1e-9
        # Repair floating-point roundoff only; no substantive filling or clipping.
        for key in ['source_coverage', 'valid_coverage', 'unclassified_share', 'adjusted_share', 'no_data_share']:
            assert result[key].min() >= -1e-9 and result[key].max() <= 1 + 1e-9
            result[key] = np.minimum(1., np.maximum(0., result[key]))
        result['no_valid_pixels'] = result['valid_coverage'] <= 1e-12
        result['incomplete_coverage'] = result['valid_coverage'] < 1 - 1e-9
        for key in GROUPS:
            result[key][result['no_valid_pixels']] = np.nan
        frame = pd.DataFrame(result)
        frame.insert(0, 'land_cover_year', year)
        frame.insert(0, 'mesh_code', codes)
        frame['product'] = 'MCD12Q1 Collection 6.1 IGBP'
        path = inputs / f'modis_{year}_mesh.parquet'
        frame.to_parquet(path, index=False)
        variables = []
        for name in frame:
            readable = GROUPS[name][0] if name in GROUPS else REFERENCES[name]
            variables.append(dict(original_name=name, readable_name=readable, full_name=readable,
                                  is_final_variable='yes' if name in GROUPS else 'no', preprocessing=[]))
        datasets[str(path.relative_to(ROOT))] = dict(
            output=f'data/processed/national/modis_land_cover/modis_land_cover_{year}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_modis_land_cover_{year}.py', variables=variables)
        audits.append(dict(year=year, rows=n, columns=len(frame.columns),
                           no_valid_coverage_meshes=int(result['no_valid_pixels'].sum()),
                           incomplete_coverage_meshes=int(result['incomplete_coverage'].sum()),
                           any_unclassified_meshes=int((result['unclassified_share'] > 1e-9).sum()),
                           source_coverage_incomplete_meshes=int((result['source_coverage'] < 1 - 1e-9).sum()),
                           share_partition_maximum_error=float(np.max(np.abs(sum_shares - result['valid_coverage'])))))
        for key, (label, _) in GROUPS.items():
            values = frame[key]
            summaries.append(dict(year=year, variable=label, missing=int(values.isna().sum()),
                                  minimum=float(values.min()), maximum=float(values.max()), mean=float(values.mean())))
        print('Confirmed annual mesh input:', year, len(frame), len(frame.columns), flush=True)
    (OUT / 'decisions.json').write_text(json.dumps(dict(
        confirmed=True, scope_decision_id=contract['scope_decision_id'],
        decision_id=contract['construction_decision_id'], datasets=datasets), indent=2) + '\n')
    pd.DataFrame(summaries).to_csv(OUT / 'mesh_variable_summary.csv', index=False)
    (OUT / 'mesh_construction_validation.json').write_text(json.dumps(dict(
        status='passed', years=audits, analytical_candidates=6,
        projection='Native MODIS spherical equal-area sinusoidal',
        missing_shares_are_nan=True, row_deletion=False, regression_refit=False), indent=2) + '\n')


if __name__ == '__main__':
    main()

"""Fit the 3 km candidate surface required for the exploratory mesh map.

Run: python3 src/analyses/run_gwpr_pooled_candidate_mesh_map.py
The final local fits include their focal mesh, unlike holdout validation.
Retain estimable coefficients below 30 observations with a support flag.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[_name] = '1'

from pathlib import Path
import hashlib
import json
import time

import numpy as np
import pandas as pd
from gwpr_pooled import PooledMoments, RadiusIndex, mesh_centroids, bisquare_weights

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/gwpr-pooled-population-zero-corrected/mesh-map-3km'
SEARCH = OUT.parent
INPUT = ROOT / 'data/processed/national/population_zero_corrected/balanced_historical_panel_preprocessed.parquet'
RADIUS = 3.


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def main():
    start = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    search = json.loads((SEARCH / 'search_validation.json').read_text())
    assert search['status'] == 'passed' and sha(INPUT) == search['source_sha256']
    assert search['search_minimum']['minimum']['radius_km'] == RADIUS
    protected = list((ROOT / 'data/processed').rglob('*.parquet'))
    protected += list((ROOT / 'data/results/tables').glob('*.xlsx'))
    protected += [ROOT / 'docs/AnaSOP.md', ROOT / 'src/analyses/gwpr_pooled.py',
                  ROOT / 'src/analyses/gwpr_twoways.py', Path(__file__)]
    protected += [p for p in SEARCH.iterdir() if p.is_file()]
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(protected))}
    contract = {'decision_id': 'MILI-D-20261010-004', 'purpose': 'Exploratory actual-mesh map',
                'model': 'local weighted pooled intercept, road density, population',
                'effects': [], 'bandwidth_km': RADIUS, 'bandwidth_status': 'Candidate used for requested preview, not separately finalized',
                'source': str(INPUT.relative_to(ROOT)), 'source_sha256': sha(INPUT),
                'kernel': 'fixed-distance bisquare; mesh-centroid great-circle distance',
                'periods': [2002, 2003, 2004, 2010], 'population_years': [2000, 2005, 2005, 2010],
                'original_units': True, 'genuine_zeros_retained': True, 'focal_mesh_included_in_final_fit': True,
                'sample_support_flag': 'Fewer than 30 observation records (four per positive-weight mesh)',
                'sample_support_is_not_coefficient_filter': True, 'failed_coefficients': 'NaN with reason',
                'no_regressor_dropping_or_radius_fallback': True, 'local_inference': False}
    dump(OUT / 'execution_contract.json', contract)
    panel = pd.read_parquet(INPUT).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = panel['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    n, t = len(codes), 4
    assert n == 228988 and len(panel) == n*t
    assert np.array_equal(panel['Road Year'].to_numpy().reshape(n, t), np.tile(contract['periods'], (n, 1)))
    assert np.array_equal(panel['Population Year'].to_numpy().reshape(n, t), np.tile(contract['population_years'], (n, 1)))
    assert np.array_equal(panel['Nighttime Light Year'].to_numpy(), panel['Road Year'].to_numpy())
    assert int((panel['Population'] == 0).sum()) == 274959
    values = panel[['Nighttime Radiance', 'Road Length Density', 'Population']].to_numpy().reshape(n, t, 3)
    assert np.isfinite(values).all() and np.array_equal(values[:, 1, 2], values[:, 2, 2])
    engine = PooledMoments(values)
    coordinates = mesh_centroids(codes)
    index = RadiusIndex(coordinates)
    coefficients = np.full((n, 3), np.nan)
    support = np.zeros(n, dtype=np.int32)
    effective = np.full(n, np.nan)
    rank = np.zeros(n, dtype=np.int8)
    condition = np.full(n, np.nan)
    statuses, reasons, references = [], [], []
    for i in range(n):
        ids, distances = index.query(coordinates[i], RADIUS)
        assert i in ids
        weights = bisquare_weights(distances, RADIUS)
        assert weights[ids == i][0] == 1.
        fit = engine.fit(ids, weights)
        coefficients[i] = fit.beta
        support[i], effective[i], rank[i], condition[i] = fit.positive_meshes, fit.effective_meshes, fit.rank, fit.scaled_condition
        statuses.append(fit.status); reasons.append(fit.reason)
        if i % 5000 == 0 and fit.status == 'ok':
            qr = engine.qr_reference(ids, weights)
            delta = float(abs(qr-fit.beta).max())
            assert np.allclose(qr, fit.beta, rtol=1e-7, atol=1e-8)
            references.append({'mesh': str(codes[i]), 'maximum_coefficient_difference': delta})
        if (i+1) % 10000 == 0 or i+1 == n:
            print(f'Local pooled 3 km: {i+1:,}/{n:,} meshes; {time.monotonic()-start:.1f}s', flush=True)
    data = pd.DataFrame({'Mesh Code': codes, 'Latitude': coordinates[:, 0], 'Longitude': coordinates[:, 1],
                         'Bandwidth km': RADIUS, 'Intercept': coefficients[:, 0],
                         'Road Density Coefficient': coefficients[:, 1], 'Population Coefficient': coefficients[:, 2],
                         'Positive Weight Meshes': support, 'Local Observations': support*t,
                         'Effective Weight Meshes': effective, 'Design Rank': rank,
                         'Scaled Design Condition': condition, 'Fit Status': statuses, 'Failure Reason': reasons,
                         'Below 30 Observations': support*t < 30,
                         'All Period Population Zero': (values[:, :, 2] == 0).all(1)})
    good = data['Fit Status'].eq('ok').to_numpy()
    assert data['Mesh Code'].is_unique and np.array_equal(data['Mesh Code'].to_numpy(), codes)
    assert np.isfinite(coefficients[good]).all() and np.isnan(coefficients[~good]).all()
    assert (support >= 1).all() and (rank[good] == 3).all()
    assert (data['Local Observations'] == data['Positive Weight Meshes']*4).all()
    assert (data['Below 30 Observations'] == (data['Local Observations'] < 30)).all()
    assert int(data['All Period Population Zero'].sum()) == 56144
    path = OUT / 'local_coefficients.parquet'
    data.to_parquet(path, index=False)
    assert pd.read_parquet(path).equals(data)
    after = {p: sha(ROOT / p) for p in before}
    assert before == after
    beta = coefficients[good, 1]
    report = {'status': 'passed', 'decision_id': contract['decision_id'], 'model': contract['model'],
              'effects': [], 'bandwidth_km': RADIUS, 'meshes': n, 'observations': len(panel),
              'estimable_meshes': int(good.sum()), 'failed_meshes': int((~good).sum()),
              'below_30_observation_meshes': int((support*t < 30).sum()),
              'estimable_below_30_observation_meshes': int((good & (support*t < 30)).sum()),
              'estimable_at_least_30_observation_meshes': int((good & (support*t >= 30)).sum()),
              'failure_reasons': data.loc[~good, 'Failure Reason'].value_counts().to_dict(),
              'road_coefficient_positive_meshes': int((beta > 0).sum()),
              'road_coefficient_negative_meshes': int((beta < 0).sum()),
              'road_coefficient_quantiles': dict(zip(['min', 'p01', 'p05', 'median', 'p95', 'p99', 'max'],
                                                    np.quantile(beta, [0, .01, .05, .5, .95, .99, 1]).tolist())),
              'median_positive_weight_meshes': float(np.median(support[good])),
              'median_effective_weight_meshes': float(np.median(effective[good])),
              'expanded_wls_reference_checks': references, 'all_mesh_ids_retained': True,
              'population_zeros_retained': True, 'below_30_estimates_retained_with_flag': True,
              'focal_mesh_included': True, 'no_local_significance_inference': True,
              'readback_verified': True, 'protected_hashes_unchanged': True, 'protected_sha256': before,
              'output_sha256': sha(path), 'seconds': time.monotonic()-start}
    dump(OUT / 'local_fit_validation.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ['protected_sha256', 'expanded_wls_reference_checks']}, indent=2), flush=True)


if __name__ == '__main__':
    main()

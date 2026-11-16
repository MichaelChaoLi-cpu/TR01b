"""Estimate the common-cohort five-period local pooled surface at the selected CV radius.

Run: python3 src/analyses/run_gwpr_current_local.py
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
OUT = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/local-fit'
SEARCH = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search'
AUDIT = ROOT / 'data/exp/data-preprocessing/current-common-cohort/panel_validation.json'
INPUT = ROOT / 'data/processed/national/current_common_cohort/baseline_panel_preprocessed.parquet'
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/current-common-cohort/estimation_decisions.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def main(contract_path=None, search_directory=None, output_directory=None):
    execution_path = Path(contract_path) if contract_path is not None else CONTRACT
    search = Path(search_directory) if search_directory is not None else SEARCH
    output = Path(output_directory) if output_directory is not None else OUT
    start = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    audit = json.loads(AUDIT.read_text())
    selection = json.loads((search / 'search_minimum.json').read_text())
    search_audit = json.loads((search / 'search_validation.json').read_text())
    baseline_contract = json.loads(execution_path.read_text())
    assert audit['status'] == search_audit['status'] == 'passed'
    assert sha(INPUT) == audit['panel_sha256'] == search_audit['source_sha256']
    assert selection['status'] == 'completed' and baseline_contract['full_national_local_fit_authorized']
    RADIUS = float(selection['minimum']['radius_km'])
    protected = [INPUT, execution_path, search / 'search_minimum.json', search / 'search_validation.json']
    protected += [ROOT / 'docs/AnaSOP.md', ROOT / 'src/analyses/gwpr_pooled.py',
                  ROOT / 'src/analyses/gwpr_twoways.py', Path(__file__)]
    protected += [AUDIT]
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(protected))}
    contract = {'decision_id': baseline_contract['decision_id'], 'cohort_decision_id': baseline_contract['cohort_decision_id'], 'bandwidth_decision_id': baseline_contract['bandwidth_decision_id'], 'local_fit_decision_id': baseline_contract.get('local_fit_decision_id'), 'purpose': 'Approved five-period GWPR rerun',
                'model': 'local weighted pooled intercept, road density, population',
                'effects': [], 'bandwidth_km': RADIUS, 'bandwidth_status': f"Minimum among {min(selection['candidate_radii_km']):g}-{max(selection['candidate_radii_km']):g} km candidates on identical estimable validation support; approximate conditional CV",
                'selection_at_search_boundary': selection['minimum']['at_search_boundary'],
                'source': str(INPUT.relative_to(ROOT)), 'source_sha256': sha(INPUT),
                'kernel': 'fixed-distance bisquare; mesh-centroid great-circle distance',
                'periods': audit['years'], 'population_years': audit['population_years'],
                'original_units': True, 'genuine_zeros_retained': True, 'focal_mesh_included_in_final_fit': True,
                'sample_support_flag': 'Fewer than 30 observation records (five per positive-weight mesh)',
                'sample_support_is_not_coefficient_filter': True,
                'common_validation_centers': selection['common_validation_centers'],
                'common_weight_coverage': selection['common_weight_coverage'],
                'conditional_selection_rmse': selection['minimum']['common_weighted_level_rmse'], 'failed_coefficients': 'NaN with reason',
                'no_regressor_dropping_or_radius_fallback': True, 'local_inference': False}
    dump(output / 'execution_contract.json', contract)
    panel = pd.read_parquet(INPUT).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = panel['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    n, t = len(codes), len(contract['periods'])
    assert n == audit['meshes'] and len(panel) == n*t == audit['observations']
    assert np.array_equal(panel['Road Year'].to_numpy().reshape(n, t), np.tile(contract['periods'], (n, 1)))
    assert np.array_equal(panel['Population Year'].to_numpy().reshape(n, t), np.tile(contract['population_years'], (n, 1)))
    assert np.array_equal(panel['Nighttime Light Year'].to_numpy(), panel['Road Year'].to_numpy())
    assert int((panel['Population'] == 0).sum()) == audit['zero_population_observations']
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
            print(f'Local pooled {RADIUS:g} km: {i+1:,}/{n:,} meshes; {time.monotonic()-start:.1f}s', flush=True)
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
    assert (data['Local Observations'] == data['Positive Weight Meshes']*t).all()
    assert (data['Below 30 Observations'] == (data['Local Observations'] < 30)).all()
    assert int(data['All Period Population Zero'].sum()) == audit['all_period_zero_population_meshes']
    path = output / 'local_coefficients.parquet'
    data.to_parquet(path, index=False)
    assert pd.read_parquet(path).equals(data)
    after = {p: sha(ROOT / p) for p in before}
    assert before == after
    beta = coefficients[good, 1]
    report = {'status': 'passed', 'decision_id': contract['decision_id'],
              'cohort_decision_id': contract['cohort_decision_id'], 'bandwidth_decision_id': contract['bandwidth_decision_id'],
              'local_fit_decision_id': contract['local_fit_decision_id'], 'model': contract['model'],
              'effects': [], 'bandwidth_km': RADIUS, 'meshes': n, 'observations': len(panel), 'periods': contract['periods'], 'population_years': contract['population_years'], 'bandwidth_reoptimized': True, 'approximate_conditional_bandwidth_selection': True,
              'common_weight_coverage': selection['common_weight_coverage'], 'source_comparability_established': False, 'source_calibration': False,
              'estimable_meshes': int(good.sum()), 'failed_meshes': int((~good).sum()),
              'below_30_observation_meshes': int((support*t < 30).sum()),
              'estimable_below_30_observation_meshes': int((good & (support*t < 30)).sum()),
              'estimable_at_least_30_observation_meshes': int((good & (support*t >= 30)).sum()),
              'failure_reasons': data.loc[~good, 'Failure Reason'].value_counts().to_dict(),
              'road_coefficient_positive_meshes': int((beta > 0).sum()),
              'road_coefficient_negative_meshes': int((beta < 0).sum()),
              'road_coefficient_zero_meshes': int((beta == 0).sum()),
              'road_coefficient_quantiles': dict(zip(['min', 'p01', 'p05', 'median', 'p95', 'p99', 'max'],
                                                    np.quantile(beta, [0, .01, .05, .5, .95, .99, 1]).tolist())),
              'median_positive_weight_meshes': float(np.median(support[good])),
              'median_effective_weight_meshes': float(np.median(effective[good])),
              'expanded_wls_reference_checks': references, 'all_mesh_ids_retained': True,
              'population_zeros_retained': True, 'below_30_estimates_retained_with_flag': True,
              'focal_mesh_included': True, 'no_local_significance_inference': True,
              'readback_verified': True, 'protected_hashes_unchanged': True, 'protected_sha256': before,
              'output_sha256': sha(path), 'seconds': time.monotonic()-start}
    dump(output / 'local_fit_validation.json', report)
    (output / 'README.md').write_text(
        '# Current common-cohort local pooled regression\n\n'
        f'{n:,} focal meshes, five periods, selected fixed bisquare radius {RADIUS:g} km. '
        'Intercept, road density and population in original units; no fixed effects. '
        'Final fits include the focal mesh, while validation excludes all five focal records. '
        f"Selection compares {min(selection['candidate_radii_km']):g}-{max(selection['candidate_radii_km']):g} km using identical estimable validation centers; its coverage is conditional. "
        'All focal mesh identifiers remain. Failed coefficients are NaN with reasons. '
        'Estimable fits below thirty records remain with a flag; no predictor deletion, radius fallback or local significance inference.\n\n'
        f"Reproduce `{baseline_contract.get('reproduce_command', 'python3 src/analyses/run_gwpr_current_local.py')}`. Outputs are exploratory.\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ['protected_sha256', 'expanded_wls_reference_checks']}, indent=2), flush=True)


if __name__ == '__main__':
    main()

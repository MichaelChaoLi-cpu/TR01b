"""Full focused GWPR surface with explicit constant-added-control omissions.

Run after the approved 3-50 km whole-mesh holdout search. Every focal mesh is
represented; omitted-control coefficients and all failed vectors retain NaN.
"""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
from gwpr_multivariate_pooled import MultivariateMoments, RadiusIndex, mesh_centroids, bisquare_weights
from run_gwpr_current_bandwidth_search import sha

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'data/exp/land-cover-poi-extension'
CONTRACT = PLAN / 'gwpr_execution_contract.json'
SEARCH = PLAN / 'gwpr-search-constant-controls-3-50km'


def main():
    started = time.monotonic()
    contract = json.loads(CONTRACT.read_text())
    selection = json.loads((SEARCH / 'search_minimum.json').read_text())
    search_audit = json.loads((SEARCH / 'search_validation.json').read_text())
    assert contract['decision_id'] == 'MILI-D-20261010-034' and contract['full_national_local_fit_authorized']
    assert contract['constant_control_rule'] == selection['constant_control_rule'] == 'omit_constant_added_controls'
    assert search_audit['status'] == 'passed' and selection['status'] == 'completed'
    radius = float(selection['minimum']['Bandwidth km'])
    output = PLAN / f'gwpr-local-constant-controls-{radius:g}km'
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / contract['input']
    assert sha(source) == contract['panel_sha256'] == search_audit['source_sha256']
    protected = [source, CONTRACT, SEARCH / 'search_minimum.json', SEARCH / 'search_validation.json',
        ROOT / 'docs/AnaSOP.md', ROOT / 'src/analyses/gwpr_multivariate_pooled.py', Path(__file__)]
    protected += [PLAN / 'pooled_land_cover_poi_extension.xlsx', ROOT / contract['baseline']]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    panel = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    meshes = panel.drop_duplicates('Mesh Code')[['Mesh Code', 'Region', 'Prefecture Code', 'Prefecture', 'No Land Overlap']].reset_index(drop=True)
    codes = meshes['Mesh Code'].astype(str).to_numpy()
    n, t, k = len(codes), len(contract['periods']), 1+len(contract['explanatory'])
    assert n == contract['meshes'] and len(panel) == n*t == contract['observations']
    assert np.array_equal(panel['Road Year'].to_numpy().reshape(n, t), np.tile(contract['periods'], (n, 1)))
    assert np.array_equal(panel['Population Year'].to_numpy().reshape(n, t), np.tile(contract['population_years'], (n, 1)))
    assert np.array_equal(panel['Nighttime Light Year'].to_numpy(), panel['Road Year'].to_numpy())
    values = panel[[contract['outcome']] + contract['explanatory']].to_numpy(float).reshape(n, t, k)
    assert np.isfinite(values).all()
    zeros = int(panel['Population'].eq(0).sum())
    assert zeros == contract['zero_population_observations']
    del panel
    engine = MultivariateMoments(values, contract['constant_control_rule'], precompute_features=False)
    coordinates = mesh_centroids(codes)
    index = RadiusIndex(coordinates)
    coefficients = np.full((n, k), np.nan)
    anchors, offsets = np.full((n, k-1), np.nan), np.full((n, k-1), np.nan)
    outcome_center = np.full(n, np.nan)
    support, rank = np.zeros(n, dtype=np.int32), np.zeros(n, dtype=np.int8)
    retained = np.zeros(n, dtype=np.int8)
    mask = np.zeros(n, dtype=np.uint16)
    effective, condition, local_r2 = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    statuses, reasons, omitted_names, constant_names, references = [], [], [], [], []
    predictor_names = np.array(contract['explanatory'])
    execution = dict(**contract, bandwidth_km=radius, bandwidth_status='Approximate minimum on identical estimable validation support',
        search_directory=str(SEARCH.relative_to(ROOT)), common_cv_centers=selection['common_validation_centers'],
        common_cv_weight_coverage=selection['common_weight_coverage'], national_optimum_established=False,
        focal_mesh_included=True, below_30_retained_with_flag=True, coefficient_reporting='NaN for omitted controls or failed vectors',
        intercept_interpretation='Includes the contribution of locally constant omitted controls; local intercepts may condition on different constant values.')
    (output / 'execution_contract.json').write_text(json.dumps(execution, indent=2) + '\n')
    print(f'Full GWPR: {n:,} meshes; radius={radius:g} km; constants omitted only among added controls.', flush=True)
    for i in range(n):
        ids, distances = index.query(coordinates[i], radius)
        assert i in ids
        weights = bisquare_weights(distances, radius)
        assert weights[ids == i][0] == 1.
        fitted = engine.qr_fit(ids, weights)
        coefficients[i] = fitted.beta
        support[i], effective[i], rank[i], condition[i] = fitted.positive_meshes, fitted.effective_meshes, fitted.rank, fitted.condition
        retained[i] = len(fitted.active)+1
        omitted = np.setdiff1d(fitted.constant, fitted.active)
        assert not np.isin([0, 1], omitted).any()
        mask[i] = sum(1 << int(column) for column in omitted)
        omitted_names.append('; '.join(predictor_names[omitted]))
        constant_names.append('; '.join(predictor_names[fitted.constant]))
        statuses.append(fitted.status); reasons.append(fitted.reason)
        if fitted.status == 'ok':
            assert np.isfinite(fitted.beta[np.r_[0, fitted.active+1]]).all()
            assert np.isnan(fitted.beta[omitted+1]).all()
            assert engine.predict(i, fitted) is not None
            raw = values[ids].reshape(-1, k)
            anchors[i], offsets[i], outcome_center[i] = fitted.center_anchor, fitted.center_offset, fitted.center_y
            prediction = fitted.center_y + ((raw[:, 1:][:, fitted.active]-fitted.center_anchor[fitted.active])-fitted.center_offset[fitted.active]) @ fitted.beta[fitted.active+1]
            w = np.repeat(weights, t)
            mu_y = np.average(raw[:, 0], weights=w)
            rss = float(w @ ((raw[:, 0]-prediction)**2))
            tss = float(w @ ((raw[:, 0]-mu_y)**2))
            if tss > 0:
                local_r2[i] = 1-rss/tss
                assert -1e-8 <= local_r2[i] <= 1+1e-8
            if i % 5000 == 0 or len(references) < 10:
                reference, reference_anchor, reference_offset, reference_intercept = engine.qr_reference(ids, weights, fitted.active, return_center=True)
                columns = np.r_[0, fitted.active+1]
                np.testing.assert_allclose(reference[columns], fitted.beta[columns], rtol=1e-5, atol=1e-7)
                reference_prediction = reference_intercept + ((raw[:, 1:][:, fitted.active]-reference_anchor)-reference_offset) @ reference[fitted.active+1]
                np.testing.assert_allclose(reference_prediction, prediction, rtol=1e-6, atol=1e-7)
                references.append({'Mesh Code': str(codes[i]), 'Estimated Parameters': len(columns),
                    'Omitted Controls': predictor_names[omitted].tolist(),
                    'Maximum Coefficient Difference': float(abs(reference[columns]-fitted.beta[columns]).max()),
                    'Maximum Prediction Difference': float(abs(reference_prediction-prediction).max())})
        else:
            assert np.isnan(fitted.beta).all()
        if (i+1) % 10000 == 0 or i+1 == n:
            print(f'Completed {i+1:,}/{n:,} meshes in {time.monotonic()-started:.1f}s.', flush=True)
    data = meshes.copy()
    data['Latitude'], data['Longitude'], data['Bandwidth km'] = coordinates[:, 0], coordinates[:, 1], radius
    column_names = ['Intercept', 'Road Density Coefficient', 'Population Coefficient'] + [name+' Coefficient' for name in contract['explanatory'][2:]]
    for j, name in enumerate(column_names): data[name] = coefficients[:, j]
    data['Local Outcome Mean'] = outcome_center
    for j, name in enumerate(contract['explanatory']):
        data[name+' Center Anchor'] = anchors[:, j]
        data[name+' Center Offset'] = offsets[:, j]
    data['Positive Weight Meshes'], data['Local Observations'] = support, support*t
    data['Effective Weight Meshes'], data['Design Rank'], data['Scaled Design Condition'] = effective, rank, condition
    data['Retained Parameters'], data['Omitted Control Mask'] = retained, mask
    data['Omitted Constant Controls'], data['Constant Predictors'] = omitted_names, constant_names
    data['Fit Status'], data['Failure Reason'], data['Below 30 Observations'] = statuses, reasons, support*t < 30
    data['Weighted Local Training R Squared'] = local_r2
    data['All Period Population Zero'] = (values[:, :, 2] == 0).all(1)
    good = data['Fit Status'].eq('ok').to_numpy()
    assert data['Mesh Code'].is_unique and np.array_equal(data['Mesh Code'].to_numpy(), codes)
    assert np.isfinite(coefficients[good, :3]).all() and np.isnan(coefficients[~good]).all()
    assert np.array_equal(rank[good], retained[good]) and (support >= 1).all()
    assert len(references) >= 10
    path = output / 'local_coefficients.parquet'
    data.to_parquet(path, index=False)
    pd.testing.assert_frame_equal(data, pd.read_parquet(path))
    omitted_summary = []
    for j, name in enumerate(contract['explanatory'][2:], start=2):
        omitted_flag = (mask & (1 << j)) != 0
        omitted_summary.append({'Control': name, 'Omitted In Estimable Meshes': int((omitted_flag & good).sum()),
            'Estimated In Estimable Meshes': int((~omitted_flag & good).sum())})
    pd.DataFrame(omitted_summary).to_csv(output / 'omitted_control_summary.csv', index=False)
    data.loc[~good].groupby('Failure Reason').size().rename('Meshes').reset_index().to_csv(output / 'failure_reasons.csv', index=False)
    road = coefficients[good, 1]
    report = dict(status='passed', decision_id=contract['decision_id'], model='Multivariate geographically weighted pooled regression',
        effects=[], constant_control_rule=contract['constant_control_rule'], bandwidth_km=radius, meshes=n, observations=n*t,
        estimable_meshes=int(good.sum()), failed_meshes=int((~good).sum()), estimable_fraction=float(good.mean()),
        estimable_with_omitted_controls=int((good & (mask > 0)).sum()),
        below_30_meshes=int((support*t < 30).sum()), estimable_below_30_meshes=int((good & (support*t < 30)).sum()),
        failure_reasons=data.loc[~good, 'Failure Reason'].value_counts().to_dict(),
        road_positive_meshes=int((road > 0).sum()), road_negative_meshes=int((road < 0).sum()), road_zero_meshes=int((road == 0).sum()),
        road_coefficient_quantiles=dict(zip(['min','p01','p05','median','p95','p99','max'], np.quantile(road,[0,.01,.05,.5,.95,.99,1]).tolist())) if len(road) else {},
        median_positive_weight_meshes=float(np.median(support[good])) if good.any() else None,
        median_effective_weight_meshes=float(np.median(effective[good])) if good.any() else None,
        median_local_training_r_squared=float(np.nanmedian(local_r2[good])) if np.isfinite(local_r2[good]).any() else None,
        common_cv_centers=selection['common_validation_centers'], common_cv_weight_coverage=selection['common_weight_coverage'],
        conditional_cv_rmse=selection['minimum']['Common Weighted Level RMSE'], national_optimum_established=False,
        all_mesh_ids_retained=True, population_zeros_retained=True, zero_population_observations=zeros,
        omitted_coefficients_nan_verified=True, mandatory_road_and_population_verified=True,
        focal_mesh_included_verified=True, below_30_retained_with_flag=True, no_local_significance_inference=True,
        expanded_wls_reference_checks=references, readback_verified=True,
        protected_inputs_unchanged=True, protected_sha256=before, source_sha256=sha(source), output_sha256=sha(path),
        seconds=time.monotonic()-started, output=str(path.relative_to(ROOT)))
    assert all(sha(ROOT / key) == digest for key, digest in before.items())
    (output / 'local_fit_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'README.md').write_text('# Focused GWPR full focal-mesh result\n\n'
        f'Reproduce `python3 src/analyses/run_land_cover_poi_gwpr_local.py`. Fixed bisquare bandwidth {radius:g} km, five periods, original units, no fixed effects. '
        'Road density and Population are mandatory. Only locally constant added controls are omitted from the numerical equation; their coefficients remain NaN with a recorded list and bit mask. '
        'The local intercept absorbs their constant contribution. Other rank failures retain all coefficient values as NaN. No ridge or radius fallback is used. '
        'All focal mesh identifiers are represented, and final fits include the focal mesh. Fewer-than-thirty-record estimates remain flagged. '
        'Local weighted R squared is a training-fit diagnostic, not cross-validated prediction or a national pooled R squared. '
        'The bandwidth minimum is approximate and conditional on the common validation support; it is not a proven national optimum. '
        'There are no local standard errors or significance claims. The earlier baseline map does not display these expanded coefficients.\n')
    pointer = dict(decision_id=contract['decision_id'], input=contract['input'],
        search=str(SEARCH.relative_to(ROOT)), bandwidth_km=radius,
        local_coefficients=str(path.relative_to(ROOT)), validation=str((output/'local_fit_validation.json').relative_to(ROOT)),
        constant_control_rule=contract['constant_control_rule'], full_local_fit_completed=True,
        baseline_and_pooled_outputs_preserved=True)
    (PLAN / 'active_gwpr_extension.json').write_text(json.dumps(pointer, indent=2) + '\n')
    print(json.dumps({key:value for key,value in report.items() if key not in ['protected_sha256', 'expanded_wls_reference_checks']}, indent=2), flush=True)


if __name__ == '__main__':
    main()

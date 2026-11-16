"""Whole-mesh holdout search for the focused multivariate pooled GWPR.

Run after the three pooled layers. Rank 3-50 km candidates on identical
estimable centers only; report the support of that conditional comparison.
"""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import argparse
import json
import time
import numpy as np
import pandas as pd
from gwpr_multivariate_pooled import MultivariateMoments, RadiusIndex, mesh_centroids
from run_gwpr_current_bandwidth_search import sha

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'data/exp/land-cover-poi-extension'


def main(contract_path=None):
    start = time.monotonic()
    contract_path = Path(contract_path).resolve() if contract_path else PLAN / 'execution_contract.json'
    contract = json.loads(contract_path.read_text())
    pooled = json.loads((PLAN / 'pooled_validation.json').read_text())
    assert contract['confirmed'] and pooled['status'] == 'passed'
    rule = contract.get('constant_control_rule', 'strict')
    out = PLAN / ('gwpr-search-3-50km' if rule == 'strict' else 'gwpr-search-constant-controls-3-50km')
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / contract['input']
    assert sha(source) == contract['panel_sha256']
    before = {str(p.relative_to(ROOT)): sha(p) for p in [source, contract_path, PLAN / 'pooled_validation.json', ROOT / 'docs/AnaSOP.md']}
    panel = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = panel['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    names = ['Intercept'] + contract['explanatory']
    values = panel[[contract['outcome']] + contract['explanatory']].to_numpy(float).reshape(len(codes), 5, len(names))
    coordinates = mesh_centroids(codes)
    moments = MultivariateMoments(values, rule)
    del panel
    index = RadiusIndex(coordinates)
    national = moments.fit(np.arange(len(codes)), np.ones(len(codes)))
    reference = json.loads((PLAN / 'national_validation.json').read_text())['results'][0]['extended']['coefficients']
    beta = np.array([row['coefficient'] for row in reference])
    assert national.status == 'ok'
    np.testing.assert_allclose(national.beta, beta, rtol=1e-7, atol=1e-8)
    national_difference = float(abs(national.beta-beta).max())
    source_centers = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km/validation_centers_input.csv'
    original_centers = pd.read_csv(source_centers, dtype={'Mesh Code': str})
    centers = original_centers.loc[original_centers['Mesh Code'].isin(codes)].reset_index(drop=True)
    original_centers.loc[~original_centers['Mesh Code'].isin(codes)].to_csv(out / 'unavailable_land_cover_centers.csv', index=False)
    assert len(centers) == 1282
    expansion = centers['Validation Weight'].to_numpy(float)
    assert np.isclose(expansion.sum(), len(codes))
    centers.to_csv(out / 'validation_centers_input.csv', index=False)
    lookup = {code: i for i, code in enumerate(codes)}
    focuses = np.array([lookup[code] for code in centers['Mesh Code']])
    radii = np.array(contract['candidate_radii_km'], float)
    assert np.array_equal(radii, np.arange(3., 51.))
    losses = np.full((len(centers), len(radii)), np.nan)
    ledger, references = [], []
    moment_rank_disagreements = 0
    print(f'Input verified: {len(codes):,} meshes, 14 parameters, {len(centers)} validation centers; rule={rule}.', flush=True)
    for row, focus in enumerate(focuses):
        ids, distance = index.query(coordinates[focus], radii[-1], exclude=focus)
        assert focus not in ids
        order = np.argsort(distance, kind='stable')
        ids, distance = ids[order], distance[order]
        # Compute exact bisquare weights for all candidates in one matrix multiply.
        weights = np.maximum(1 - (distance[:, None]/radii[None, :])**2, 0)**2
        counts = np.searchsorted(distance, radii, side='left')
        sums = weights.T @ moments.features[ids]
        minimum = np.minimum.accumulate(moments.minimum[ids], axis=0) if len(ids) else None
        maximum = np.maximum.accumulate(moments.maximum[ids], axis=0) if len(ids) else None
        totals, squares = weights.sum(0), (weights*weights).sum(0)
        effective = np.divide(totals*totals, squares, out=np.zeros(len(radii)), where=squares > 0)
        for j, h in enumerate(radii):
            count = counts[j]
            lo = minimum[count-1] if count else np.full(moments.p, np.nan)
            hi = maximum[count-1] if count else np.full(moments.p, np.nan)
            fitted = moments.fit_sums(sums[j], lo, hi, count, effective[j])
            if count and fitted.reason != 'constant_retained_predictor':
                # Small local variances can lose precision in globally centered
                # sufficient statistics. Direct locally centered SVD determines
                # both estimability and coefficients whenever constants allow.
                stable = moments.qr_fit(ids[:count], weights[:count, j])
                moment_rank_disagreements += int(fitted.status != stable.status)
                fitted = stable
            prediction = moments.predict(focus, fitted) if fitted.status == 'ok' else None
            status, reason = fitted.status, fitted.reason
            if fitted.status == 'ok' and prediction is None:
                status, reason = 'unpredictable', 'heldout_control_differs_from_training_constant'
            elif fitted.status == 'ok':
                residual = values[focus, :, 0] - prediction
                losses[row, j] = residual @ residual / 5
                if (row % 100 == 0 and h in [3, 10, 25, 50]) or (h == 3):
                    local_ids, local_weights = ids[:count], weights[:count, j]
                    qr, reference_anchor, reference_offset, reference_intercept = moments.qr_reference(local_ids, local_weights, fitted.active, return_center=True)
                    columns = np.r_[0, fitted.active+1]
                    reference_prediction = reference_intercept + ((values[focus, :, 1:][:, fitted.active]-reference_anchor)-reference_offset) @ qr[fitted.active+1]
                    np.testing.assert_allclose(qr[columns], fitted.beta[columns], rtol=1e-5, atol=1e-7)
                    np.testing.assert_allclose(reference_prediction, prediction, rtol=1e-6, atol=1e-7)
                    references.append({'Mesh Code': codes[focus], 'Bandwidth km': h,
                        'Maximum Coefficient Difference': float(abs(qr[columns]-fitted.beta[columns]).max()),
                        'Maximum Prediction Difference': float(abs(reference_prediction-prediction).max())})
            omitted = np.setdiff1d(fitted.constant, fitted.active)
            ledger.append({'Mesh Code': codes[focus], 'Bandwidth km': float(h), 'Validation Weight': expansion[row],
                'Fit Status': status, 'Failure Reason': reason, 'Level Prediction MSE': losses[row, j],
                'Training Meshes': int(count), 'Training Records': int(count*5), 'Below 30 Records': count*5 < 30,
                'Effective Training Meshes': float(effective[j]), 'Estimated Parameters': len(fitted.active)+1,
                'Design Rank': fitted.rank, 'Scaled Design Condition': fitted.condition,
                'Constant Predictors': '; '.join(np.array(contract['explanatory'])[fitted.constant]),
                'Omitted Constant Controls': '; '.join(np.array(contract['explanatory'])[omitted])})
        if (row+1) % 100 == 0 or row+1 == len(centers):
            print(f'Completed {row+1}/{len(centers)} centers in {time.monotonic()-start:.1f}s.', flush=True)
    common = np.isfinite(losses).all(axis=1)
    common_coverage = float(expansion[common].sum()/expansion.sum())
    summary = []
    for j, radius in enumerate(radii):
        valid = np.isfinite(losses[:, j])
        mse = float(np.average(losses[common, j], weights=expansion[common])) if common.any() else np.nan
        summary.append({'Bandwidth km': radius, 'Validation Centers': len(centers), 'Successful Centers': int(valid.sum()),
            'Successful Weight Coverage': float(expansion[valid].sum()/expansion.sum()), 'Common Validation Centers': int(common.sum()),
            'Common Weight Coverage': common_coverage, 'Common Weighted Level MSE': mse, 'Common Weighted Level RMSE': float(np.sqrt(mse)),
            'Available Center Weighted Level MSE': float(np.average(losses[valid, j], weights=expansion[valid])) if valid.any() else np.nan})
    table = pd.DataFrame(summary)
    detail = pd.DataFrame(ledger)
    table.to_csv(out / 'bandwidth_search.csv', index=False)
    detail.to_parquet(out / 'center_radius_validation.parquet', index=False)
    np.save(out / 'validation_mse.npy', losses)
    centers['Common Estimable Support'] = common
    centers.to_csv(out / 'validation_centers.csv', index=False)
    detail.loc[detail['Fit Status'].ne('ok')].groupby(['Bandwidth km', 'Failure Reason']).size().rename('Centers').reset_index().to_csv(out / 'failure_reasons.csv', index=False)
    best = table.loc[table['Common Weighted Level MSE'].idxmin()].to_dict() if common.any() else None
    minimum = dict(status='completed' if common.any() else 'no_common_estimable_support', constant_control_rule=rule,
        common_validation_centers=int(common.sum()), common_weight_coverage=common_coverage,
        minimum=None if best is None else {key: best[key] for key in ['Bandwidth km', 'Common Weighted Level MSE', 'Common Weighted Level RMSE']},
        approximate_and_conditional_cv=True, national_optimum_established=False, full_national_local_fit_performed=False)
    (out / 'search_minimum.json').write_text(json.dumps(minimum, indent=2) + '\n')
    pd.testing.assert_frame_equal(detail, pd.read_parquet(out / 'center_radius_validation.parquet'))
    assert len(references) >= 5 and len(detail) == len(centers)*48
    assert all(sha(ROOT / path) == digest for path, digest in before.items())
    report = dict(status='passed', decision_id=contract['decision_id'], constant_control_rule=rule,
        execution_contract=str(contract_path.relative_to(ROOT)),
        periods=contract['periods'], explanatory=contract['explanatory'], whole_mesh_holdout_verified=True,
        same_estimable_support_for_comparison=True, omitted_controls_prediction_checked=True,
        national_equal_weight_coefficient_maximum_difference=national_difference,
        local_estimator='Locally centered weighted SVD; independent expanded intercept-plus-controls WLS checks',
        moment_rank_disagreements_corrected_by_direct_svd=moment_rank_disagreements,
        expanded_weighted_reference_checks=references, protected_inputs_unchanged=True,
        readback_verified=True, search_minimum=minimum, seconds=time.monotonic()-start,
        source_sha256=sha(source), source_centers_sha256=sha(source_centers))
    (out / 'search_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'README.md').write_text('# Focused multivariate pooled GWPR bandwidth search\n\n'
        f'Reproduce with `python3 src/analyses/run_land_cover_poi_gwpr_search.py --contract {contract_path.relative_to(ROOT)}`. Uses the five-period complete-land-cover projection, original units and fixed bisquare great-circle weights. '
        'All five focal records are excluded together. Reuses the existing stratified validation centers except the four with unavailable land cover. '
        'Tile expansion weights still sum to the complete-case mesh population. Compare radii only on the identical set of estimable centers. '
        'Available-center scores change support and must not rank candidates. Constant-control handling is read from the execution contract. '
        'If omission of constant added controls is approved, their coefficient remains NaN, and holdout prediction is allowed only when the held-out variable matches the training constant. '
        'There are no fixed effects, ridge, regressor deletion for other collinearities, or radius fallback. No full coefficient surface or national optimum is implied by this conditional search.\n')
    print(json.dumps(minimum, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract', type=Path)
    main(parser.parse_args().contract)

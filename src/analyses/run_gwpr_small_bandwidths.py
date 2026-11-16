#!/usr/bin/env python3
"""Add requested 3/4 km fits and comparable diagnostic CV; preserve selection."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'

import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

from gwpr_twoways import bisquare_weights
from run_gwpr_twoways import ROOT, OUT, PLAN, load_panel, fit, sha
from run_gwpr_all_bandwidths import inspect_result

EXT = OUT / 'small-bandwidths'
DECISION = 'MILI-D-20261009-027'


def main():
    start = time.monotonic()
    policy = json.loads((PLAN / 'execution_contract.json').read_text())
    assert policy['additional_candidate_distances_km'] == [3, 4]
    assert policy['additional_candidate_decision_id'] == DECISION
    EXT.mkdir(exist_ok=True)
    prior = json.loads((OUT / 'all-bandwidths/run_manifest.json').read_text())
    protected = dict(prior['protected_sha256'])
    for row in prior['runs']:
        protected.update(row['output_sha256'])
    for name in ['selected_bandwidth.json', 'bandwidth_search.csv',
                 'bandwidth_center_ledger.parquet', 'validation_mse.npy', 'validation_centers.csv',
                 'all-bandwidths/run_manifest.json', 'all-bandwidths/national_fit_summary.csv']:
        path = OUT / name
        protected[str(path.relative_to(ROOT))] = sha(path)
    assert all(sha(ROOT / p) == h for p, h in protected.items())
    fit_protected = {p: h for p, h in prior['protected_sha256'].items()
                     if p.startswith('data/processed/') or p.endswith('.xlsx')}
    rows = []
    for radius in [3, 4]:
        destination = OUT / f'candidate_{radius}km'
        if not (destination / 'fit_validation.json').exists():
            fit(candidate_radius=radius, candidate_phase='additional_small_bandwidth_national_fit')
        row = inspect_result(radius, destination, fit_protected)
        row['decision_id'] = DECISION
        rows.append(row)
    codes, membership, panel, index, contract, source = load_panel()
    centers = pd.read_csv(OUT / 'validation_centers.csv', dtype={'Mesh Code': 'string', 'Primary Tile': 'string'})
    positions = {code: i for i, code in enumerate(codes)}
    old = np.load(OUT / 'validation_mse.npy')
    assert old.shape == (len(centers), 46)
    small = np.full((len(centers), 2), np.nan)
    ledger = []; references = []
    for c, code in enumerate(centers['Mesh Code']):
        focus = positions[code]
        for column, radius in enumerate([3, 4]):
            ids, distance = index.query(index.coordinates[focus], radius, exclude=focus)
            assert focus not in ids
            weights = bisquare_weights(distance, radius)
            local = panel.fit(ids, weights)
            if local.status == 'ok':
                error = panel.within_residual(focus, local)
                small[c, column] = float(error @ error / panel.t)
                if c % 100 == 0:
                    beta, period = panel.qr_reference(ids, weights)
                    assert np.allclose(local.beta, beta, rtol=1e-7, atol=1e-8)
                    assert np.allclose(local.time_effect, period, rtol=1e-7, atol=1e-8)
                    references.append(dict(mesh=code, bandwidth_km=radius,
                                           coefficient_max_difference=float(np.max(abs(local.beta-beta)))))
            ledger.append({'Mesh Code': code, 'Bandwidth km': radius,
                           'Within Change MSE': small[c, column],
                           'Training Meshes': local.positive_meshes,
                           'Fit Status': local.status, 'Failure Reason': local.reason})
    pd.DataFrame(ledger).to_parquet(EXT / 'additional_validation_ledger.parquet', index=False)
    np.save(EXT / 'additional_validation_mse.npy', small)
    scores = np.column_stack([small, old])
    common = np.isfinite(scores).all(axis=1)
    original_common = np.isfinite(old).all(axis=1)
    assert np.array_equal(original_common, centers['Common Estimable'].to_numpy())
    assert common.any()
    weights = centers['Validation Weight'].to_numpy()
    centers['Expanded Common Estimable'] = common
    centers.to_csv(EXT / 'expanded_validation_centers.csv', index=False)
    summary = []
    for column, radius in enumerate(range(3, 51)):
        ok = np.isfinite(scores[:, column])
        summary.append({'Bandwidth km': radius, 'Validation Centers': len(centers),
                        'Successful Centers': int(ok.sum()), 'Failed Centers': int((~ok).sum()),
                        'Expanded Common Validation Centers': int(common.sum()),
                        'Expanded Common Weighted Within MSE': float(np.average(scores[common, column], weights=weights[common])),
                        'Expanded Common Weight Coverage': float(weights[common].sum()/weights.sum())})
    summary = pd.DataFrame(summary)
    summary.to_csv(EXT / 'expanded_bandwidth_search.csv', index=False)
    old_fits = pd.read_csv(OUT / 'all-bandwidths/national_fit_summary.csv')
    new_fits = pd.DataFrame([{k: v for k, v in row.items() if k not in ['output_sha256', 'failure_reasons']} for row in rows])
    combined = pd.concat([new_fits, old_fits], ignore_index=True).sort_values('bandwidth_km')
    combined = combined.rename(columns={'Common Weighted Within MSE': 'Original 5-50 Common Weighted Within MSE'})
    combined = combined.merge(summary, left_on='bandwidth_km', right_on='Bandwidth km', validate='one_to_one').drop(columns='Bandwidth km')
    combined.to_csv(EXT / 'national_fit_summary_3_to_50km.csv', index=False)
    assert len(pd.read_csv(EXT / 'national_fit_summary_3_to_50km.csv')) == 48
    assert all(sha(ROOT / p) == h for p, h in protected.items())
    best = summary.loc[summary['Expanded Common Weighted Within MSE'].idxmin()]
    report = dict(status='passed', decision_id=DECISION,
                  additional_distances_km=[3, 4], total_completed_distances=48,
                  national_meshes_per_distance=134830, observations_per_distance=539320,
                  whole_mesh_leave_out=True, training_only_local_time_absorption=True,
                  original_common_validation_centers=int(original_common.sum()),
                  expanded_common_validation_centers=int(common.sum()),
                  additional_common_validation_losses=int((original_common & ~common).sum()),
                  expanded_common_weight_coverage=float(weights[common].sum()/weights.sum()),
                  diagnostic_minimum_bandwidth_km=int(best['Bandwidth km']),
                  diagnostic_minimum_mse=float(best['Expanded Common Weighted Within MSE']),
                  diagnostic_boundary_optimum=bool(best['Bandwidth km'] in [3, 50]),
                  scores_conditional_on_changed_common_support=True, approximate_cv=True,
                  original_selected_bandwidth_preserved=5, new_bandwidth_formally_selected=False,
                  original_46_runs_and_scores_unchanged=True, protected_files_unchanged=True,
                  qr_reference_checks=references, protected_sha256=protected,
                  elapsed_seconds=time.monotonic()-start, additional_runs=rows)
    (EXT / 'run_manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(combined[['bandwidth_km','successes','failures','Expanded Common Weighted Within MSE']].head(8).to_string(index=False), flush=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ['qr_reference_checks','protected_sha256','additional_runs']}, indent=2), flush=True)


if __name__ == '__main__':
    main()

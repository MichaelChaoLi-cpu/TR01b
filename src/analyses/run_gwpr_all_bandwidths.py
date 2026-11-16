#!/usr/bin/env python3
"""Run all 46 requested nationwide bandwidths using the verified GWPR engine.

Resume completed fits after checking their protected inputs and output contents.
Each worker writes only its own candidate directory and log. No new selection,
model, transformation, map, or local significance procedure is introduced.
"""
import os

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout, redirect_stderr
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from run_gwpr_twoways import ROOT, OUT, PLAN, fit, sha

BATCH = OUT / 'all-bandwidths'
DECISION = 'MILI-D-20261009-026'


def inspect_result(radius, destination, protected):
    report = json.loads((destination / 'fit_validation.json').read_text())
    assert report['status'] == 'passed' and report['bandwidth_km'] == radius
    assert report['national_meshes'] == 134830 and report['observations'] == 539320
    assert report['original_meshes_retained'] and report['failed_coefficients_nan']
    assert report['protected_files_unchanged']
    assert all(report['protected_sha256'].get(p) == h for p, h in protected.items())
    result = pd.read_parquet(destination / 'local_coefficients.parquet')
    assert len(result) == 134830 and result['Mesh Code'].is_unique
    accepted = pd.read_csv(ROOT / 'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv',
                           usecols=['Mesh Code'], dtype={'Mesh Code': 'string'})
    assert result['Mesh Code'].tolist() == sorted(accepted['Mesh Code'].unique().tolist())
    assert result['Bandwidth km'].eq(radius).all()
    good = result['Fit Status'].eq('ok')
    slopes = ['Road Density Coefficient', 'Population Coefficient']
    assert np.isfinite(result.loc[good, slopes].to_numpy()).all()
    assert result.loc[~good, slopes].isna().all().all()
    assert result.loc[~good, 'Failure Reason'].str.len().gt(0).all()
    assert int(good.sum()) == report['successes']
    residual = pd.read_parquet(destination / 'focal_residuals.parquet',
                               columns=['Mesh Code', 'GWPR Within Residual'])
    assert len(residual) == 539320
    assert residual['Mesh Code'].tolist() == np.repeat(result['Mesh Code'].to_numpy(), 4).tolist()
    assert residual['GWPR Within Residual'].isna().to_numpy().reshape(-1, 4).all(axis=1).tolist() == (~good).tolist()
    names = ['local_coefficients.parquet', 'local_coefficients.csv',
             'focal_residuals.parquet', 'fit_validation.json']
    files = {str((destination / name).relative_to(ROOT)): sha(destination / name) for name in names}
    return dict(bandwidth_km=radius, national_meshes=len(result), observations=len(residual),
                successes=report['successes'], failures=report['failures'],
                failure_reasons=report['failure_reasons'],
                elapsed_seconds=report['elapsed_seconds'],
                coefficient_path=str((destination / 'local_coefficients.parquet').relative_to(ROOT)),
                csv_path=str((destination / 'local_coefficients.csv').relative_to(ROOT)),
                residual_path=str((destination / 'focal_residuals.parquet').relative_to(ROOT)),
                validation_path=str((destination / 'fit_validation.json').relative_to(ROOT)),
                output_sha256=files)


def run_one(radius, protected):
    destination = OUT if radius == 5 else OUT / f'candidate_{radius}km'
    reused = False
    if (destination / 'fit_validation.json').exists():
        row = inspect_result(radius, destination, protected)
        reused = True
    else:
        with (BATCH / 'logs' / f'bandwidth_{radius:02d}km.log').open('w') as stream:
            with redirect_stdout(stream), redirect_stderr(stream):
                fit(candidate_radius=radius, candidate_phase='all_bandwidth_national_fit')
        row = inspect_result(radius, destination, protected)
    row['reused_completed_fit'] = reused
    row['decision_id'] = DECISION
    (BATCH / f'bandwidth_{radius:02d}km.json').write_text(json.dumps(row, indent=2) + '\n')
    return row


def main(workers):
    started = time.monotonic()
    policy = json.loads((PLAN / 'execution_contract.json').read_text())
    assert policy['all_bandwidth_national_fits_confirmed']
    assert policy['all_bandwidth_decision_id'] == DECISION
    BATCH.mkdir(exist_ok=True); (BATCH / 'logs').mkdir(exist_ok=True)
    protected_paths = sorted((ROOT / 'data/processed').rglob('*.parquet')) + sorted((ROOT / 'data/results/tables').glob('*.xlsx'))
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    membership = ROOT / 'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv'
    protected[str(membership.relative_to(ROOT))] = sha(membership)
    # Existing fit reports predate the explicit membership checksum; it is checked
    # centrally before/after and its actual identifier content is checked per fit.
    fit_protected = {p: h for p, h in protected.items() if p != str(membership.relative_to(ROOT))}
    rows = [run_one(5, fit_protected)]
    print('Completed 1/46: reused verified selected 5 km fit', flush=True)
    # Longer-radius jobs first minimize the final scheduling tail.
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(run_one, radius, fit_protected): radius for radius in range(50, 5, -1)}
        for task in as_completed(jobs):
            row = task.result(); rows.append(row)
            print(f"Completed {len(rows)}/46: {row['bandwidth_km']} km; "
                  f"estimable {row['successes']:,}, failed {row['failures']:,}; "
                  f"batch elapsed {time.monotonic() - started:.1f}s", flush=True)
    rows.sort(key=lambda row: row['bandwidth_km'])
    assert [row['bandwidth_km'] for row in rows] == list(range(5, 51))
    assert all(sha(ROOT / p) == h for p, h in protected.items())
    scores = pd.read_csv(OUT / 'bandwidth_search.csv')
    summary = pd.DataFrame([{k: v for k, v in row.items()
                             if k not in ['output_sha256', 'failure_reasons']} for row in rows])
    summary = summary.merge(scores[['Bandwidth km', 'Common Weighted Within MSE']],
                            left_on='bandwidth_km', right_on='Bandwidth km', validate='one_to_one')
    summary = summary.drop(columns='Bandwidth km')
    summary.to_csv(BATCH / 'national_fit_summary.csv', index=False)
    assert len(pd.read_csv(BATCH / 'national_fit_summary.csv')) == 46
    manifest = dict(status='passed', decision_id=DECISION, workers=workers,
                    candidate_radii_km=list(range(5, 51)), completed=46,
                    focal_model_count=134830 * 46, observations_per_bandwidth=539320,
                    selected_bandwidth_preserved=5, bandwidth_selection_unchanged=True,
                    common_validation_scoring_unchanged=True,
                    all_meshes_retained_every_bandwidth=True, failed_slopes_nan=True,
                    protected_files_unchanged=True, protected_sha256=protected,
                    elapsed_seconds=time.monotonic() - started, runs=rows)
    (BATCH / 'run_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"All 46 nationwide fits verified in {manifest['elapsed_seconds']:.1f}s", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    assert 1 <= args.workers <= 4
    main(args.workers)

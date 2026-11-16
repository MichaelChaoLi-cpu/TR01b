"""Fixed-distance pooled GWPR search on the corrected national panel.

Run locally: python3 src/analyses/run_gwpr_current_bandwidth_search.py
The stratified, whole-mesh holdout CV is approximate, conditional on common
estimable support. This script does not fit a full national coefficient surface.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[_name] = '1'

import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from gwpr_pooled import PooledMoments, RadiusIndex, mesh_centroids, bisquare_weights

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'data/exp/estimation-framework-planning/current-common-cohort'
NATIONAL = ROOT / 'data/exp/figure-table-generation/current-common-cohort/national'
OUT = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search'
KEYS = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main(contract_path=None, output_directory=None):
    start = time.monotonic()
    contract_path = Path(contract_path) if contract_path is not None else PLAN / 'estimation_decisions.json'
    output = Path(output_directory) if output_directory is not None else OUT
    contract = json.loads(contract_path.read_text())
    assert contract['confirmed'] and contract['effects'] == [] and contract['model'] == 'pooling'
    audit = json.loads((ROOT / contract['preprocessing_validation']).read_text())
    national = json.loads((NATIONAL / 'validation.json').read_text())
    source = ROOT / contract['input']
    assert sha(source) == audit['panel_sha256'] == national['input_sha256']
    output.mkdir(parents=True, exist_ok=True)
    before = {str(p.relative_to(ROOT)): sha(p) for p in [source, contract_path,
        ROOT / contract['preprocessing_validation'], NATIONAL / 'validation.json',
        ROOT / 'src/analyses/gwpr_pooled.py', ROOT / 'src/analyses/gwpr_twoways.py', Path(__file__)]}
    panel = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = panel['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    t = len(contract['periods'])
    assert len(codes) == contract['expected_meshes'] and len(panel) == contract['expected_observations'] == len(codes)*t
    assert np.array_equal(panel['Road Year'].to_numpy().reshape(-1,t), np.tile(contract['periods'],(len(codes),1)))
    assert np.array_equal(panel['Population Year'].to_numpy().reshape(-1,t),np.tile(contract['population_years'],(len(codes),1)))
    assert np.array_equal(panel['Nighttime Light Year'].to_numpy(),panel['Road Year'].to_numpy())
    assert not panel.duplicated(['Mesh Code','Road Year']).any()
    assert int((panel['Population']==0).sum()) == contract['expected_zero_population_observations']
    values = panel[['Nighttime Radiance','Road Length Density','Population']].to_numpy().reshape(-1,t,3)
    assert np.isfinite(values).all() and np.array_equal(values[:,1,2],values[:,2,2])
    moments = PooledMoments(values)
    national_fit = moments.fit(np.arange(len(codes)), np.ones(len(codes)))
    national_beta = np.array([r['coefficient'] for r in national['results'][0]['coefficients']])
    assert national_fit.status == 'ok'
    assert np.allclose(national_fit.beta,national_beta,rtol=1e-9,atol=1e-9)
    national_delta = float(abs(national_fit.beta-national_beta).max())
    coordinates = mesh_centroids(codes)
    index = RadiusIndex(coordinates)
    all_zero = (values[:,:,2]==0).all(1)
    meshes = pd.DataFrame({'Mesh Code':codes, 'Primary Tile':[c[:4] for c in codes],
        'Latitude':coordinates[:,0],'Longitude':coordinates[:,1], 'All Period Population Zero':all_zero})
    tiles = sorted(meshes['Primary Tile'].unique())
    counts = meshes.groupby('Primary Tile').size().reindex(tiles).to_numpy()
    target = contract['validation_centers']
    quota = np.minimum(4,counts)
    remaining = target-int(quota.sum())
    assert remaining >= 0
    capacity = counts-quota
    fraction = remaining*capacity/capacity.sum()
    addition = np.floor(fraction).astype(int)
    leftover = remaining-int(addition.sum())
    for j in np.argsort(-(fraction-addition),kind='stable')[:leftover]: addition[j]+=1
    quota += addition
    assert quota.sum()==target and (quota<=counts).all()
    rng = np.random.default_rng(contract['validation_seed'])
    parts=[]
    for tile,count,selected_count in zip(tiles,counts,quota):
        eligible=meshes.loc[meshes['Primary Tile'].eq(tile)]
        chosen=eligible.iloc[np.sort(rng.choice(len(eligible),size=int(selected_count),replace=False))].copy()
        chosen['Validation Weight']=float(count/selected_count)
        parts.append(chosen)
    centers=pd.concat(parts,ignore_index=True).sort_values('Mesh Code').reset_index(drop=True)
    assert len(centers)==target and centers['Mesh Code'].is_unique and centers['Primary Tile'].nunique()==len(tiles)
    centers_path=output/'validation_centers_input.csv'
    centers.to_csv(centers_path,index=False)
    pd.DataFrame({'Primary Tile':tiles,'Eligible Meshes':counts,'Validation Centers':quota}).to_csv(output/'sampling_strata.csv',index=False)
    lookup={c:i for i,c in enumerate(codes)}
    focuses=np.array([lookup[c] for c in centers['Mesh Code']])
    expansion=centers['Validation Weight'].to_numpy(float)
    assert np.isclose(expansion.sum(),len(codes)) and (expansion>0).all()
    radii=np.array(contract['candidate_radii_km'],dtype=float)
    assert len(radii) >= 2 and np.isfinite(radii).all() and radii.min() > 0
    assert np.array_equal(np.diff(radii), np.ones(len(radii)-1))
    scores = np.full((len(centers), len(radii)), np.nan)
    ledger, reference_checks = [], []
    print(f'Input verified: {len(codes):,} meshes; {len(panel):,} records; {len(centers):,} centers; {len(radii)} radii.', flush=True)

    for row_index, focus in enumerate(focuses):
        candidates, distances = index.query(coordinates[focus], radii.max(), exclude=focus)
        assert focus not in candidates
        base = centers.iloc[row_index]
        for radius_index, radius in enumerate(radii):
            inside = distances < radius
            ids, ds = candidates[inside], distances[inside]
            weights = bisquare_weights(ds, radius)
            fit = moments.fit(ids, weights)
            if fit.status == 'ok':
                residual = values[focus, :, 0] - moments.predict(focus, fit)
                scores[row_index, radius_index] = float(residual @ residual / t)
                if row_index % 100 == 0 and radius in (1, 3, 25, 50):
                    reference = moments.qr_reference(ids, weights)
                    reference_predictions = reference[0] + values[focus, :, 1:] @ reference[1:]
                    prediction_delta = float(abs(reference_predictions - moments.predict(focus, fit)).max())
                    coefficient_delta = float(abs(reference - fit.beta).max())
                    assert np.allclose(reference, fit.beta, rtol=1e-7, atol=1e-8)
                    assert np.allclose(reference_predictions, moments.predict(focus, fit), rtol=1e-7, atol=1e-8)
                    reference_checks.append({'mesh': str(base['Mesh Code']), 'radius_km': float(radius),
                                             'maximum_coefficient_difference': coefficient_delta,
                                             'maximum_prediction_difference': prediction_delta})
            ledger.append({'Mesh Code': str(base['Mesh Code']), 'Primary Tile': str(base['Primary Tile']),
                           'Validation Weight': float(expansion[row_index]),
                           'All Period Population Zero': bool(all_zero[focus]), 'Bandwidth km': float(radius),
                           'Level Prediction MSE': float(scores[row_index, radius_index]),
                           'Training Meshes': fit.positive_meshes, 'Training Observations': fit.positive_meshes*t,
                           'Below 30 Training Observations': fit.positive_meshes*t < 30, 'Effective Training Meshes': fit.effective_meshes,
                           'Fit Status': fit.status, 'Failure Reason': fit.reason,
                           'Design Rank': fit.rank, 'Scaled Design Condition': fit.scaled_condition})
        if (row_index + 1) % 100 == 0 or row_index + 1 == len(centers):
            print(f'Completed {row_index + 1:,}/{len(centers):,} centers in {time.monotonic()-start:.1f}s.', flush=True)

    common = np.isfinite(scores).all(1)
    common_count = int(common.sum())
    coverage = float(expansion[common].sum() / expansion.sum())
    detail_support = np.array([r['Training Meshes'] for r in ledger]).reshape(len(centers),len(radii))
    summary = []
    for j, radius in enumerate(radii):
        valid = np.isfinite(scores[:, j])
        mse = float(np.average(scores[common, j], weights=expansion[common])) if common_count else np.nan
        summary.append({'Bandwidth km': float(radius), 'Validation Centers': len(centers),
                        'Successful Centers': int(valid.sum()), 'Failed Centers': int((~valid).sum()),
                        'Successful Weight Coverage': float(expansion[valid].sum()/expansion.sum()),
                        'Estimable Below 30 Training Observations': int(((detail_support[:,j]*t < 30) & valid).sum()),
                        'Failed All Zero Population Centers': int((~valid & all_zero[focuses]).sum()),
                        'Common Validation Centers': common_count, 'Common Weight Coverage': coverage,
                        'Common Weighted Level MSE': mse, 'Common Weighted Level RMSE': float(np.sqrt(mse)),
                        'Available Center Weighted Level MSE': float(np.average(scores[valid, j], weights=expansion[valid])) if valid.any() else np.nan})
    output.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(summary)
    detail = pd.DataFrame(ledger)
    table.to_csv(output / 'bandwidth_search.csv', index=False)
    detail.to_parquet(output / 'center_radius_validation.parquet', index=False)
    centers['Common Estimable Support'] = common
    centers.to_csv(output / 'validation_centers.csv', index=False)
    np.save(output / 'validation_mse.npy', scores)
    failed = detail[detail['Fit Status'] != 'ok']
    reasons = failed.groupby(['Bandwidth km', 'Failure Reason']).size().rename('Centers').reset_index()
    reasons.to_csv(output / 'failure_reasons.csv', index=False)

    best = None
    if common_count:
        best_row = table.loc[table['Common Weighted Level MSE'].idxmin()]
        best = {'radius_km': float(best_row['Bandwidth km']),
                'common_weighted_level_mse': float(best_row['Common Weighted Level MSE']),
                'common_weighted_level_rmse': float(best_row['Common Weighted Level RMSE']),
                'at_search_boundary': bool(best_row['Bandwidth km'] in (radii.min(), radii.max()))}
    minimum = {'status': 'completed' if best else 'no_common_estimable_support',
               'bandwidth_decision_id': contract['bandwidth_decision_id'],
               'model': 'local weighted pooled with intercept and two slopes; no fixed effects',
               'score': 'whole-mesh five-period holdout radiance-level MSE',
               'candidate_radii_km': radii.tolist(), 'validation_centers': len(centers),
               'common_validation_centers': common_count, 'common_weight_coverage': coverage,
               'common_all_period_zero_population_centers': int((common & all_zero[focuses]).sum()),
               'excluded_primary_tiles': sorted(centers.loc[~centers['Primary Tile'].isin(centers.loc[common, 'Primary Tile']), 'Primary Tile'].unique().tolist()),
               'minimum': best, 'approximate_and_conditional_cv': True,
               'full_national_local_fit_performed': False,
               'full_fit_authorized': contract.get('full_national_local_fit_authorized', False)}
    dump(output / 'search_minimum.json', minimum)
    after = {path: sha(ROOT / path) for path in before}
    assert before == after
    assert len(reference_checks) >= 10
    assert len(detail) == len(centers)*len(radii)
    saved_table = pd.read_csv(output / 'bandwidth_search.csv')
    assert np.allclose(table.select_dtypes('number'), saved_table.select_dtypes('number'), equal_nan=True)
    saved_detail = pd.read_parquet(output / 'center_radius_validation.parquet')
    assert saved_detail.equals(detail)
    validation = {'status': 'passed', 'decision_id': contract['decision_id'],
                  'cohort_decision_id': contract['cohort_decision_id'],
                  'bandwidth_decision_id': contract['bandwidth_decision_id'],
                  'execution_contract': str(contract_path.relative_to(ROOT)),
                  'source_sha256': sha(source), 'validation_centers_sha256': sha(centers_path),
                  'sample_membership_verified': True, 'population_zeros_preserved': True,
                  'population_snapshot_reuse_verified': True, 'effects': [],
                  'whole_mesh_exclusion_verified': True, 'same_cohort_for_every_scored_radius': True,
                  'national_equal_weight_coefficient_maximum_difference': national_delta,
                  'expanded_weighted_reference_checks': reference_checks,
                  'protected_hashes_unchanged': True, 'protected_sha256': before,
                  'saved_outputs_readback_passed': True, 'seconds': time.monotonic()-start,
                  'search_minimum': minimum,
                  'output_sha256': {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.suffix in ('.csv', '.parquet', '.npy', '.json') and p.name != 'search_validation.json'}}
    dump(output / 'search_validation.json', validation)
    (output / 'README.md').write_text(
        '# Fixed-distance geographically weighted pooled search\n\n'
        f"Run `{contract.get('reproduce_command', 'python3 src/analyses/run_gwpr_current_bandwidth_search.py')}` from the repository root. "
        f"Compare {len(radii)} radii from {radii.min():g} to {radii.max():g} km in 1 km increments. "
        'Uses the approved common national five-period panel, original units, genuine zeros, intercept, road density '
        'and population. No mesh or period effects. Fixed-distance bisquare weights and exact great-circle '
        'mesh-centroid distances; no predictor dropping, ridge or radius fallback.\n\n'
        'All five observations of each validation mesh are excluded from training. 1,286 stratified centers '
        'and tile expansion weights approximate nationwide level prediction CV. Rank failures retain NaN. '
        'Rank candidates only on the identical common estimable center set. Its weight coverage is a '
        'sample-design diagnostic, not an exact national fraction. Available-center scores have different '
        'supports and must not be used for comparing radii. Excluded support remains documented.\n\n'
        '`bandwidth_search.csv` contains all candidates; `center_radius_validation.parquet` contains '
        'every fit status and loss; `failure_reasons.csv` aggregates failure reasons; '
        '`validation_centers.csv` flags common support; `validation_mse.npy` preserves the loss matrix. '
        '`search_minimum.json` reports the conditional minimum, and `search_validation.json` records '
        'source hashes and equivalence checks. A boundary minimum does not establish an interior optimum. '
        'Common-support coverage limits the selection claim. This execution performs bandwidth validation only; '
        'existing local coefficient outputs keep the specification stated in their own contracts.\n')
    print(json.dumps(minimum, indent=2), flush=True)


if __name__ == '__main__':
    main()

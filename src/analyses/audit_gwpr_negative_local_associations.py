"""Locate negative 3 km slopes and compare adjacent 4/5 km candidate signs.

Descriptive diagnostics only: no local significance or causal classification.
Run locally: python3 src/analyses/audit_gwpr_negative_local_associations.py
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[_name] = '1'

from pathlib import Path
import json
import time
import numpy as np
import pandas as pd

from gwpr_pooled import PooledMoments, RadiusIndex, mesh_centroids, bisquare_weights
from run_gwpr_pooled_candidate_mesh_map import sha, dump

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'data/exp/estimation-framework-planning/gwpr-negative-local-associations'


def sign_summary(frame):
    good = frame['Fit Status'].eq('ok')
    beta = frame['Road Density Coefficient']
    negative = good & (beta < 0)
    return {'Meshes': len(frame), 'Estimable Meshes': int(good.sum()), 'Failed Meshes': int((~good).sum()),
            'Negative Meshes': int(negative.sum()), 'Positive Meshes': int((good & (beta > 0)).sum()),
            'Exact Zero Meshes': int((good & (beta == 0)).sum()),
            'Negative Share Among Estimable': float(negative.sum()/good.sum()) if good.any() else np.nan,
            'Negative Below 30 Records': int((negative & frame['Below 30 Observations']).sum()),
            'Negative Median Coefficient': float(beta[negative].median()),
            'Negative Median Local Records': float(frame.loc[negative, 'Local Observations'].median()),
            'Negative Median Effective Meshes': float(frame.loc[negative, 'Effective Weight Meshes'].median()),
            'Negative Median Scaled Condition': float(frame.loc[negative, 'Scaled Design Condition'].median())}


def stability_metrics(beta, common, support):
    b = beta[common]
    neg3 = b[:, 0] < 0
    negall = (b < 0).all(1)
    agreement = (np.sign(b) == np.sign(b[:, :1])).all(1)
    adequate = support[common].all(1)
    def group(mask):
        return {'common_estimable_meshes': int(mask.sum()),
                'baseline_negative_meshes': int((neg3 & mask).sum()),
                'negative_at_all_three_radii': int((negall & mask).sum()),
                'negative_persistence_share': float((negall & mask).sum()/(neg3 & mask).sum()) if (neg3 & mask).any() else None,
                'all_sign_agreement_share': float(agreement[mask].mean()) if mask.any() else None,
                'baseline_negative_remaining_negative_at_4km': int(((b[:, 1] < 0) & neg3 & mask).sum()),
                'baseline_negative_remaining_negative_at_5km': int(((b[:, 2] < 0) & neg3 & mask).sum())}
    return {'common_estimable': group(np.ones(len(b), dtype=bool)),
            'common_estimable_at_least_30_records_each_radius': group(adequate)}


def main():
    start = time.monotonic()
    contract_path = PLAN / 'execution_contract.json'
    contract = json.loads(contract_path.read_text())
    assert contract['effects'] == [] and contract['radii_km'] == [3, 4, 5]
    source, base_path, pref_path = [ROOT / contract[k] for k in ('input', 'baseline', 'prefecture_reference')]
    baseline = pd.read_parquet(base_path).sort_values('Mesh Code').reset_index(drop=True)
    fit_report = json.loads((base_path.parent / 'local_fit_validation.json').read_text())
    assert sha(base_path) == fit_report['output_sha256'] and fit_report['status'] == 'passed'
    assert sha(source) == fit_report['protected_sha256'][str(source.relative_to(ROOT))]
    protected = list((ROOT / 'data/processed').rglob('*.parquet'))
    protected += list((ROOT / 'data/results/tables').glob('*.xlsx'))
    protected += [p for p in base_path.parent.iterdir() if p.is_file()]
    protected += [contract_path, ROOT / 'docs/AnaSOP.md', ROOT / 'src/analyses/gwpr_pooled.py', Path(__file__)]
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(protected))}
    out = ROOT / contract['output_directory']; out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = panel['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    n = len(codes)
    assert n == contract['expected_meshes'] and len(panel) == contract['expected_observations']
    assert np.array_equal(codes, baseline['Mesh Code'].to_numpy())
    values = panel[['Nighttime Radiance', 'Road Length Density', 'Population']].to_numpy().reshape(n, 4, 3)
    engine = PooledMoments(values); coordinates = mesh_centroids(codes); index = RadiusIndex(coordinates)
    all_zero = (values[:, :, 2] == 0).all(1)
    frames = {3: baseline}
    references = []
    for radius in [4, 5]:
        coefficients = np.full((n, 3), np.nan); q = np.zeros(n, dtype=np.int32)
        effective = np.full(n, np.nan); condition = np.full(n, np.nan); ranks = np.zeros(n, dtype=np.int8)
        statuses, reasons = [], []
        for i in range(n):
            ids, distance = index.query(coordinates[i], radius)
            assert i in ids
            weights = bisquare_weights(distance, radius)
            fit = engine.fit(ids, weights)
            coefficients[i] = fit.beta; q[i] = fit.positive_meshes
            effective[i] = fit.effective_meshes; condition[i] = fit.scaled_condition; ranks[i] = fit.rank
            statuses.append(fit.status); reasons.append(fit.reason)
            if i % 10000 == 0 and fit.status == 'ok':
                qr = engine.qr_reference(ids, weights)
                assert np.allclose(qr, fit.beta, rtol=1e-7, atol=1e-8)
                references.append({'radius_km': radius, 'mesh': str(codes[i]),
                                   'maximum_coefficient_difference': float(abs(qr-fit.beta).max())})
            if (i+1) % 40000 == 0 or i+1 == n:
                print(f'Adjacent {radius} km: {i+1:,}/{n:,} meshes; elapsed {time.monotonic()-start:.1f}s', flush=True)
        frame = pd.DataFrame({'Mesh Code': codes, 'Latitude': coordinates[:, 0], 'Longitude': coordinates[:, 1],
                              'Bandwidth km': radius, 'Intercept': coefficients[:, 0],
                              'Road Density Coefficient': coefficients[:, 1], 'Population Coefficient': coefficients[:, 2],
                              'Positive Weight Meshes': q, 'Local Observations': q*4, 'Effective Weight Meshes': effective,
                              'Design Rank': ranks, 'Scaled Design Condition': condition, 'Fit Status': statuses,
                              'Failure Reason': reasons, 'Below 30 Observations': q*4 < 30,
                              'All Period Population Zero': all_zero})
        good = frame['Fit Status'].eq('ok').to_numpy()
        assert np.isfinite(coefficients[good]).all() and np.isnan(coefficients[~good]).all()
        path = out / f'local_coefficients_{radius}km.parquet'
        frame.to_parquet(path, index=False); assert pd.read_parquet(path).equals(frame)
        assert np.all(q >= baseline['Positive Weight Meshes'].to_numpy())
        frames[radius] = frame

    pref = pd.read_parquet(pref_path)[['Mesh Code', 'Prefecture Code', 'Prefecture']]
    assert pref['Mesh Code'].is_unique and len(pref) == n
    localized = baseline.merge(pref, on='Mesh Code', how='left', validate='one_to_one')
    assert localized['Prefecture'].notna().all()
    rows = []
    for (code, name), group in localized.groupby(['Prefecture Code', 'Prefecture'], sort=True):
        rows.append({'Prefecture Code': code, 'Prefecture': name, **sign_summary(group)})
    county = pd.DataFrame(rows)
    assert len(county) == 47 and county['Meshes'].sum() == n
    assert county['Negative Meshes'].sum() == int((baseline['Road Density Coefficient'] < 0).sum())
    county.to_csv(out / 'negative_coefficients_by_prefecture_3km.csv', index=False)
    support_rows = []
    for r, frame in frames.items():
        for name, mask in [('Negative', frame['Road Density Coefficient'] < 0),
                           ('Positive', frame['Road Density Coefficient'] > 0),
                           ('Exact Zero', frame['Road Density Coefficient'] == 0)]:
            sub = frame[mask]
            support_rows.append({'Bandwidth km': r, 'Sign': name, 'Meshes': len(sub),
                                 'Below 30 Records': int(sub['Below 30 Observations'].sum()),
                                 'Median Local Records': float(sub['Local Observations'].median()),
                                 'Median Effective Meshes': float(sub['Effective Weight Meshes'].median()),
                                 'Median Scaled Condition': float(sub['Scaled Design Condition'].median()),
                                 'Coefficient p05': float(sub['Road Density Coefficient'].quantile(.05)),
                                 'Coefficient Median': float(sub['Road Density Coefficient'].median()),
                                 'Coefficient p95': float(sub['Road Density Coefficient'].quantile(.95))})
    pd.DataFrame(support_rows).to_csv(out / 'coefficient_sign_support.csv', index=False)
    beta = np.column_stack([frames[r]['Road Density Coefficient'].to_numpy() for r in [3, 4, 5]])
    common = np.isfinite(beta).all(1)
    support = np.column_stack([frames[r]['Local Observations'].to_numpy() >= 30 for r in [3, 4, 5]])
    metrics = stability_metrics(beta, common, support)
    audit = pref.set_index('Mesh Code').loc[codes].reset_index()
    audit['Common Estimable'] = common
    audit['At Least 30 Records At Every Radius'] = support.all(1)
    for j, r in enumerate([3, 4, 5]):
        audit[f'Road Coefficient {r}km'] = beta[:, j]
        audit[f'Fit Status {r}km'] = frames[r]['Fit Status'].to_numpy()
    audit['Negative At Every Radius'] = common & (beta < 0).all(1)
    audit.to_parquet(out / 'mesh_sign_stability.parquet', index=False)
    county_stability = []
    for (code, name), ids in audit.groupby(['Prefecture Code', 'Prefecture']).groups.items():
        ix = np.asarray(ids)
        m = stability_metrics(beta[ix], common[ix], support[ix])
        row = {'Prefecture Code': code, 'Prefecture': name}
        row.update(m['common_estimable'])
        row.update({'adequate_' + k: v for k, v in m['common_estimable_at_least_30_records_each_radius'].items()})
        county_stability.append(row)
    pd.DataFrame(county_stability).to_csv(out / 'negative_sign_stability_by_prefecture.csv', index=False)
    report = {'status': 'passed', 'decision_id': contract['decision_id'],
              'meshes': n, 'effects': [], 'radii_km': [3, 4, 5],
              'national_by_radius': {str(r): sign_summary(frame) for r, frame in frames.items()},
              'sign_stability': metrics, 'no_statistical_significance_claim': True,
              'top_prefectures_by_negative_share_3km': county.sort_values('Negative Share Among Estimable', ascending=False).head(10).to_dict('records'),
              'expanded_wls_checks': references, 'protected_sha256': before,
              'protected_hashes_unchanged': True, 'all_meshes_retained_every_radius': True,
              'readback_passed': True, 'seconds': time.monotonic()-start}
    assert all(sha(ROOT / p) == h for p, h in before.items())
    assert len(references) >= 35
    # Empty medians are represented as null in JSON; none occur nationally.
    report['output_sha256'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'validation.json'}
    dump(out / 'validation.json', report)
    (out / 'README.md').write_text(
        '# Negative local road associations: geography and adjacent-radius checks\n\n'
        'Run `python3 src/analyses/audit_gwpr_negative_local_associations.py`. '
        'Uses the existing corrected 3 km pooled surface and recomputes the same local model '
        'at 4 and 5 km. These are diagnostic candidates, not finalized bandwidth choices. '
        'All 228,988 focal meshes and original variables are retained; all final fits include the focal mesh.\n\n'
        '`negative_coefficients_by_prefecture_3km.csv` localizes strict negative slopes using '
        'the approved prefecture reference. Its negative-share denominator is estimable meshes; '
        'failure and full prefecture counts remain visible. Prefecture share ranks are descriptive, '
        'not classifications of city centers, suburbs, rural transport function, or physical land area.\n\n'
        '`coefficient_sign_support.csv` reports sign magnitude and record, effective-mesh and '
        'condition diagnostics. `mesh_sign_stability.parquet` preserves every mesh and its '
        'coefficient/status at every radius. `negative_sign_stability_by_prefecture.csv` uses '
        'the identical all-three estimable intersection and separately its at-least-30-record subset. '
        'Signs use strict numeric zero without a newly selected economic effect-size threshold. '
        'Persistence is neither significance nor a spatial equality test.\n\n'
        'No source variable, radius fallback, regressor dropping, ridge penalty, causal interpretation '
        'or new formal figure/table is introduced. `validation.json` records protected hashes, '
        'independent expanded-WLS checks and denominator-explicit results.\n')
    print(json.dumps(metrics, indent=2), flush=True)
    print(county.sort_values('Negative Share Among Estimable', ascending=False).head(10).to_string(index=False), flush=True)


if __name__ == '__main__':
    main()

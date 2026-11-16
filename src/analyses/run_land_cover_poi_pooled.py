"""Ordered national, nine-region and 47-prefecture focused pooled extension."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import json
from statistics import NormalDist
import math
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from run_gwpr_current_bandwidth_search import sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/land-cover-poi-extension'


def fit(sample, explanatory):
    g, n = sample['Mesh Code'].nunique(), len(sample)
    assert n == g * 5 and g > len(explanatory) + 1
    y = sample['Nighttime Radiance'].to_numpy(float)
    raw = sample[explanatory].to_numpy(float)
    mean, scale = raw.mean(0), raw.std(0)
    k = len(explanatory) + 1
    constant = [name for name, value in zip(explanatory, scale) if value == 0]
    if constant:
        return {'status': 'failed', 'reason': 'constant_predictors', 'constant_predictors': constant, 'meshes': g, 'observations': n, 'parameters': k, 'coefficients': []}
    x = np.column_stack([np.ones(n), (raw - mean) / scale])
    beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != k or (singular[-1] / singular[0])**2 <= 1e-12:
        return {'status': 'failed', 'reason': 'rank_deficient_or_numerically_singular', 'meshes': g, 'observations': n, 'parameters': k, 'rank': int(rank), 'coefficients': []}
    residual = y - x @ beta
    gram = x.T @ x
    bread = np.linalg.inv(gram)
    cr1 = g / (g - 1) * (n - 1) / (n - k)
    scores = np.einsum('gtk,gt->gk', x.reshape(g, 5, k), residual.reshape(g, 5))
    covariance = cr1 * bread @ (scores.T @ scores) @ bread
    transform = np.eye(k)
    transform[0, 1:] = -mean / scale
    transform[1:, 1:] = np.diag(1 / scale)
    original_beta = transform @ beta
    original_covariance = transform @ covariance @ transform.T
    se = np.sqrt(np.diag(original_covariance))
    assert np.isfinite(se).all() and (se > 0).all()
    # Independent expanded original-unit least-squares reference.
    original_x = np.column_stack([np.ones(n), raw])
    reference, _, reference_rank, _ = np.linalg.lstsq(original_x, y, rcond=None)
    assert reference_rank == k
    np.testing.assert_allclose(reference, original_beta, rtol=1e-7, atol=1e-8)
    np.testing.assert_allclose(original_x @ reference, x @ beta, rtol=1e-8, atol=1e-7)
    orthogonality = float(np.max(abs(x.T @ residual) / (np.linalg.norm(x, axis=0) * np.linalg.norm(residual))))
    assert orthogonality < 1e-10
    # Verify the cluster meat through explicitly computed original-unit scores.
    raw_scores = np.einsum('gtk,gt->gk', original_x.reshape(g, 5, k), residual.reshape(g, 5))
    np.testing.assert_allclose(raw_scores, scores @ np.linalg.inv(transform), rtol=1e-6, atol=1e-6)
    z = NormalDist().inv_cdf(.975)
    coefficients = [dict(variable=name, coefficient=float(b), clustered_standard_error=float(s),
        confidence_lower=float(b - z*s), confidence_upper=float(b + z*s),
        p_value=float(math.erfc(abs(b/s) / math.sqrt(2))))
        for name, b, s in zip(['Intercept'] + explanatory, original_beta, se)]
    rss = float(residual @ residual)
    tss = float((y - y.mean()) @ (y - y.mean()))
    return dict(status='ok', meshes=int(g), observations=n, parameters=k, rank=int(rank),
        coefficients=coefficients, ordinary_pooled_r_squared=1-rss/tss, cr1_factor=cr1,
        rss=rss, outcome_tss=tss, covariance=original_covariance.tolist(),
        scaled_design_condition=float(singular[0]/singular[-1]),
        original_unit_reference_max_coefficient_difference=float(abs(reference-original_beta).max()),
        residual_orthogonality=orthogonality, zero_population_observations=int(sample['Population'].eq(0).sum()))


def main():
    contract_path = OUT / 'execution_contract.json'
    contract = json.loads(contract_path.read_text())
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261010-033' and not contract['effects']
    source = ROOT / contract['input']
    assert sha(source) == contract['panel_sha256']
    protected = [source, contract_path, ROOT / contract['baseline'], ROOT / 'docs/AnaSOP.md']
    protected += list((ROOT / 'data/results/tables').glob('*.xlsx'))
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    panel = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    assert len(panel) == contract['observations'] and panel['Mesh Code'].nunique() == contract['meshes']
    results, rows, comparison = {}, {}, []
    specs = [('national', [('Japan', panel)]),
             ('regional', list(panel.groupby('Region', sort=True))),
             ('prefecture', list(panel.groupby(['Prefecture Code', 'Prefecture'], sort=True)))]
    for family, groups in specs:
        results[family], rows[family] = [], []
        for label, subset in groups:
            subset = subset.sort_values(['Mesh Code', 'Road Year'])
            labels = list(label) if isinstance(label, tuple) else [label]
            baseline = fit(subset, ['Road Length Density', 'Population'])
            extended = fit(subset, contract['explanatory'])
            assert baseline['status'] == 'ok'
            extended['group'], baseline['group'] = labels, labels
            results[family].append({'extended': extended, 'baseline_same_sample': baseline})
            for result in [baseline, extended]:
                for coefficient in result['coefficients']:
                    rows[family].append({'Group': ' / '.join(map(str, labels)), 'Specification': 'Extended' if result is extended else 'Baseline same sample', **coefficient,
                        'Meshes': result['meshes'], 'Observations': result['observations'], 'R Squared': result['ordinary_pooled_r_squared']})
            road0 = baseline['coefficients'][1]
            road1 = extended['coefficients'][1] if extended['status'] == 'ok' else {}
            comparison.append({'Family': family, 'Group': ' / '.join(map(str, labels)), 'Status': extended['status'],
                'Meshes': len(subset)//5, 'Observations': len(subset),
                'Baseline Road Coefficient': road0['coefficient'], 'Extended Road Coefficient': road1.get('coefficient'),
                'Extended Road SE': road1.get('clustered_standard_error'), 'Extended Road Lower 95': road1.get('confidence_lower'),
                'Extended Road Upper 95': road1.get('confidence_upper'), 'Extended Road p Value': road1.get('p_value'),
                'Baseline R Squared': baseline['ordinary_pooled_r_squared'], 'Extended R Squared': extended.get('ordinary_pooled_r_squared')})
            print(f"{family}: {' / '.join(map(str,labels))}; {extended['status']}; road={road1.get('coefficient')}; R2={extended.get('ordinary_pooled_r_squared')}", flush=True)
        assert len(groups) == {'national': 1, 'regional': 9, 'prefecture': 47}[family]
        assert sum(r['extended']['meshes'] for r in results[family]) == contract['meshes']
        assert sum(r['extended']['observations'] for r in results[family]) == contract['observations']
        pd.DataFrame(rows[family]).to_csv(OUT / f'{family}_coefficients.csv', index=False)
        (OUT / f'{family}_validation.json').write_text(json.dumps(dict(status='passed', family=family, results=results[family]), indent=2) + '\n')
    comparison = pd.DataFrame(comparison)
    comparison.to_csv(OUT / 'pooled_road_comparison.csv', index=False)
    wb = Workbook()
    wb.remove(wb.active)
    frames = {family: pd.DataFrame(value) for family, value in rows.items()}
    frames['road comparison'] = comparison
    for title, frame in frames.items():
        ws = wb.create_sheet(title)
        ws.append(frame.columns.tolist())
        for cell in ws[1]:
            cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='254B6F')
            cell.alignment = Alignment(wrap_text=True)
        for values in frame.itertuples(index=False, name=None):
            ws.append([None if pd.isna(value) else value for value in values])
        ws.freeze_panes = 'C2'; ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 26
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, float): cell.number_format = '0.00000000'
    notes = wb.create_sheet('Notes')
    for line in ['Exploratory focused extension; outcome Nighttime Radiance; original units and no fixed effects.',
        'Controls: Road Length Density, Population, five annual land-cover shares, two transport distances and four facility totals.',
        'Other Land Cover Share is retained in data and omitted from the equation. Shares partition valid coverage; partial coverage remains flagged without normalization.',
        'Four Minamitorishima meshes with unavailable land-cover data are excluded only from this estimation projection; original data retain NaN.',
        'POI source editions are replicated across all five periods under the approved static assumption; they are not observed historical facilities.',
        'Mesh-clustered CR1: G/(G-1)*(N-1)/(N-K); normal 95 percent intervals, unadjusted for multiple comparisons.',
        'Baseline and extended estimates in this workbook use identical complete-case samples within each area.',
        'R squared reflects the joint fit of all model regressors; conditional associations do not identify causal effects.',
        'Original road-source transitions, population offsets and snapshot coverage limitations remain.']:
        notes.append([line])
    notes.column_dimensions['A'].width = 140
    workbook = OUT / 'pooled_land_cover_poi_extension.xlsx'
    wb.save(workbook)
    check = load_workbook(workbook, data_only=True)
    for title, frame in frames.items():
        values = list(check[title].values)
        assert values[0] == tuple(frame.columns) and len(values) == len(frame) + 1
        for original, saved in zip(frame.itertuples(index=False, name=None), values[1:]):
            for a, b in zip(original, saved):
                if pd.isna(a): assert b is None
                elif isinstance(a, (int, float)): assert np.isclose(a, b, rtol=1e-13, atol=1e-14)
                else: assert a == b
    assert all(sha(ROOT / path) == digest for path, digest in before.items())
    report = dict(status='passed', decision_id=contract['decision_id'], meshes=contract['meshes'], observations=contract['observations'],
        effects=[], explanatory=contract['explanatory'], model_counts={family: len(value) for family, value in results.items()},
        estimable_model_counts={family: sum(r['extended']['status']=='ok' for r in value) for family, value in results.items()},
        same_sample_baseline_comparisons=True, original_unit_reference_verified=True, cluster_scores_verified=True,
        exact_geographic_partitions_verified=True, workbook_readback_verified=True, protected_inputs_unchanged=True,
        protected_sha256=before, workbook=str(workbook.relative_to(ROOT)))
    (OUT / 'pooled_validation.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()

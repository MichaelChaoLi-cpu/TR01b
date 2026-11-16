#!/usr/bin/env python3
"""National Pooled Regression with Census Structural Zeros.

Plan: Same-sample national conditional level associations (MILI-D-20261009-036).
Framework: AnaSOP Sections 5-7; intercept and two slopes, no fixed effects,
original units, equal weights, mesh-clustered CR1 and normal 95% intervals.
Run locally: python3 src/analyses/table_national_pooled_regression_with_census_structural_zeros.py
"""
from pathlib import Path
from statistics import NormalDist
import hashlib
import json

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from table_pilot_fixed_effects_baseline import cluster_covariance

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/national-pooled-population-zero-corrected/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/national-pooled-population-zero-corrected'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    active = ROOT / 'data/exp/estimation-framework-planning/current-common-cohort/estimation_decisions.json'
    if active.exists():
        from rerun_current_common_pooled import main as current_rerun
        return current_rerun('national')
    # The current approved scope supersedes the preserved four-period body.
    current = ROOT / 'data/exp/estimation-framework-planning/five-period-2024/estimation_decisions.json'
    if current.exists():
        from rerun_five_period_pooled import main as rerun
        return rerun('national')
    contract = json.loads(CONTRACT.read_text())
    # MILI-D-20261011-046: preserve historical source contracts; redirect only export.
    contract['output_workbook'] = str((Path('data/exp/figure-table-generation/historical-baseline-tables/regenerated/four-period') / Path(contract['output_workbook']).name))
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261009-036'
    assert contract['effects'] == [] and contract['intercept']
    assert contract['original_scale'] and contract['zeros_retained'] and not contract['imputation']
    QA.mkdir(parents=True, exist_ok=True)
    protected = sorted((ROOT / 'data/processed').rglob('*.parquet'))
    protected += sorted((ROOT / 'data/results/tables').glob('*.xlsx'))
    protected = [p for p in protected if p != ROOT / contract['output_workbook']]
    protected += [CONTRACT, ROOT / 'docs/AnaSOP.md', ROOT / contract['preprocessing_validation']]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    sample = pd.read_parquet(ROOT / contract['input']).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    g, t = contract['expected_meshes'], len(contract['periods'])
    n = len(sample)
    assert n == contract['expected_observations'] == g * t
    assert sample['Mesh Code'].nunique() == g
    assert not sample.duplicated(['Mesh Code', 'Road Year']).any()
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(g, t), np.tile(contract['periods'], (g, 1)))
    assert np.array_equal(sample['Population Year'].to_numpy().reshape(g, t), np.tile(contract['population_years'], (g, 1)))
    membership = sample[['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']]
    preprocessing = json.loads((ROOT / contract['preprocessing_validation']).read_text())
    assert contract['input'] == preprocessing['new_balanced_panel']
    assert sha(ROOT / contract['input']) == preprocessing['new_balanced_panel_sha256']
    variables = [contract['outcome']] + contract['explanatory']
    values = sample[variables].to_numpy(dtype=float)
    assert np.isfinite(values).all()
    zeros = int(sample['Population'].eq(0).sum())
    assert zeros == contract['expected_zero_population_observations']
    population = sample['Population'].to_numpy().reshape(g, t)
    assert np.array_equal(population[:, 1], population[:, 2])
    y, regressors = values[:, 0], values[:, 1:]
    x = np.column_stack([np.ones(n), regressors])
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    assert rank == 3
    residual = y - x @ beta
    k = len(beta)
    correction = g / (g - 1) * (n - 1) / (n - k)
    covariance = cluster_covariance(x, residual, g, t, correction)
    se = np.sqrt(np.diag(covariance))
    assert np.isfinite(se).all() and (se > 0).all()

    # Equivalent centered/scaled representation verifies both estimates and
    # clustered covariance without changing the scientific variable scales.
    mean, scale = regressors.mean(axis=0), regressors.std(axis=0)
    assert (scale > 0).all()
    scaled_x = np.column_stack([np.ones(n), (regressors - mean) / scale])
    scaled_beta, _, scaled_rank, _ = np.linalg.lstsq(scaled_x, y, rcond=None)
    transform = np.eye(k)
    transform[0, 1:] = -mean / scale
    transform[1:, 1:] = np.diag(1 / scale)
    equivalent_beta = transform @ scaled_beta
    scaled_residual = y - scaled_x @ scaled_beta
    equivalent_covariance = transform @ cluster_covariance(scaled_x, scaled_residual, g, t, correction) @ transform.T
    assert scaled_rank == rank
    np.testing.assert_allclose(beta, equivalent_beta, rtol=1e-9, atol=1e-10)
    np.testing.assert_allclose(covariance, equivalent_covariance, rtol=1e-8, atol=1e-12)
    normalized_scores = (scaled_x.T @ residual) / (np.linalg.norm(scaled_x, axis=0) * np.linalg.norm(residual))
    assert np.max(np.abs(normalized_scores)) < 1e-10
    rss = float(residual @ residual)
    centered_y = y - y.mean()
    tss = float(centered_y @ centered_y)
    r_squared = 1 - rss / tss
    assert 0 <= r_squared <= 1
    z = NormalDist().inv_cdf(.5 + contract['confidence_level'] / 2)
    names = ['Intercept'] + contract['explanatory']
    estimates = [dict(variable=name, coefficient=float(b), clustered_standard_error=float(s),
                      confidence_lower=float(b-z*s), confidence_upper=float(b+z*s))
                 for name, b, s in zip(names, beta, se)]
    rows = [[e['variable'], e['coefficient'], e['clustered_standard_error'], e['confidence_lower'], e['confidence_upper']] for e in estimates]
    diagnostics = [('Observations', n), ('Meshes', g), ('Periods', t),
                   ('Zero-population observations', zeros), ('Ordinary pooled R squared', r_squared),
                   ('Mesh fixed effects', 'No'), ('Period fixed effects', 'No'),
                   ('Intercept included', 'Yes'), ('Clustering', 'Mesh Code')]
    rows += [[name, value, None, None, None] for name, value in diagnostics]
    headers = ['Term', 'Coefficient or diagnostic value', 'Mesh-clustered standard error', 'Lower 95% confidence bound', 'Upper 95% confidence bound']
    table = pd.DataFrame(rows, columns=headers)
    assert table.shape == (12, 5)
    table.to_csv(QA / 'table.csv', index=False)
    membership.to_csv(QA / 'sample_membership.csv', index=False)
    saved_membership = pd.read_csv(QA / 'sample_membership.csv', dtype={'Mesh Code': str})
    assert membership.astype({'Mesh Code': str}).equals(saved_membership)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Pooled regression'
    ws.append([contract['table_title']])
    ws.merge_cells('A1:E1')
    ws['A1'].font = Font(size=13, bold=True)
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='254B6F')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[2].height = 42
    for row in rows:
        ws.append(row)
    for row in ws.iter_rows(min_row=3, max_row=5, min_col=2):
        for cell in row:
            cell.number_format = '0.000000'
    for key, width in zip('ABCDE', [34, 28, 28, 28, 28]):
        ws.column_dimensions[key].width = width
    ws.freeze_panes = 'B3'
    notes = wb.create_sheet('Notes')
    for line in [
        'Outcome: Nighttime Radiance (nW/cm^2/sr); road density: km/km^2; Population: persons.',
        'Years: roads/lights 2002, 2003, 2004, 2010; population 2000, 2005, 2005, 2010.',
        'Equal-weight OLS with intercept and two regressors; neither mesh nor period fixed effects.',
        'Corrected balanced national sample verified against the approved preprocessing checksum and sample rules.',
        'Original scales and true zeros retained; no imputation, transformations or island exclusions.',
        'Mesh-clustered CR1 covariance; G/(G-1)*(N-1)/(N-3); normal-approximation 95% confidence bounds.',
        'Ordinary pooled R squared: 1 - pooled RSS / sum((radiance - mean radiance)^2).',
        'Ordinary pooled R squared describes joint prediction by road density and population, not roads alone.',
        'Pooled slopes combine within-mesh and between-mesh variation; no causal interpretation.',
        'Mesh clustering allows dependence within meshes, but does not remove omitted-variable bias or neighboring-mesh dependence.',
        'Population 2005 is reused in the two middle periods; road-source comparability is not established.',
        'Current primary model under MILI-D-20261009-037; output review pending.'
    ]:
        notes.append([line])
        notes.cell(notes.max_row, 1).alignment = Alignment(wrap_text=True, vertical='top')
        notes.row_dimensions[notes.max_row].height = 32
    notes.column_dimensions['A'].width = 120
    output = ROOT / contract['output_workbook']
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    readback = load_workbook(output, data_only=True)['Pooled regression']
    assert list(next(readback.iter_rows(min_row=2, max_row=2, values_only=True))) == headers
    for expected, actual in zip(rows, readback.iter_rows(min_row=3, max_row=14, values_only=True)):
        for a, b in zip(expected, actual):
            if isinstance(a, (int, float)):
                assert np.isclose(a, b, rtol=1e-13, atol=1e-14)
            else:
                assert a == b
    after = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert before == after
    report = dict(status='passed', decision_id=contract['decision_id'], table_title=contract['table_title'],
                  coefficients=estimates, observations=n, meshes=g, periods=contract['periods'],
                  zero_population_observations=zeros, effects=[], intercept=True, design_rank=int(rank),
                  residual_degrees_of_freedom=n-k, cr1_factor=correction, ordinary_pooled_r_squared=r_squared,
                  rss=rss, centered_outcome_tss=tss, confidence_distribution=contract['confidence_distribution'],
                  approved_preprocessing_sample_verified=True, population_snapshot_reuse_verified=True,
                  sample_membership_sha256=sha(QA/'sample_membership.csv'),
                  equivalent_representation_max_coefficient_difference=float(np.max(np.abs(beta-equivalent_beta))),
                  equivalent_representation_max_covariance_difference=float(np.max(np.abs(covariance-equivalent_covariance))),
                  residual_orthogonality_passed=True, exported_values_verified=True, protected_hashes_unchanged=True,
                  protected_sha256=before, output=contract['output_workbook'], output_sha256=sha(output),
                  input=contract['input'], input_sha256=sha(ROOT/contract['input']),
                  covariance=covariance.tolist(), source_comparability_established=False, causal_identification=False,
                  human_output_review='pending')
    (QA/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    (QA/'README.md').write_text(
        '# National Pooled Regression with Census Structural Zeros\n\n'
        'MILI-D-20261009-036; generated under AnaSOP Sections 5-8. '
        'Current primary national model, verified against the approved corrected preprocessing sample. '
        'Read validation.json for numerical checks and coefficients; table.csv mirrors the workbook.\n\n'
        'Run from the repository root: `python3 src/analyses/table_national_pooled_regression_with_census_structural_zeros.py`.\n\n'
        'Pooled OLS includes an intercept, Road Length Density and Population, with no fixed effects. '
        'Original-scale variables and all documented zeros are retained. '
        'Ordinary pooled R squared describes joint prediction by road density and population. '
        'The pooled estimate combines between-mesh and within-mesh patterns, and is associational.\n\n'
        'Protected input, other formal workbook and contract hashes are checked before and after generation. '
        'The AnaSOP hash is a fit-time snapshot; subsequent skill-guided completion notes are separately documented. '
        'Raw and processed sources remain unchanged. '
        'Workbook readback is verified; human output review remains pending.\n')
    print(json.dumps({key: report[key] for key in ['status','coefficients','observations','meshes','ordinary_pooled_r_squared','output']}, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Pilot Fixed-Effects Baseline.

Plan: One approved historical pilot table (MILI-D-20261009-014).
Framework: AnaSOP Sections 5-7; original-scale OLS, mesh/period effects,
mesh-clustered CR1 covariance, large-cluster normal confidence bounds.
"""
from pathlib import Path
from statistics import NormalDist
import hashlib
import json

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/pilot-fixed-effects/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/pilot-fixed-effects'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def absorb_balanced(x):
    return x - x.mean(axis=1, keepdims=True) - x.mean(axis=0, keepdims=True) + x.mean(axis=(0, 1), keepdims=True)


def cluster_covariance(design, residual, groups, periods, correction):
    scores = (design * residual[:, None]).reshape(groups, periods, -1).sum(axis=1)
    bread = np.linalg.inv(design.T @ design)
    covariance = correction * bread @ (scores.T @ scores) @ bread
    return (covariance + covariance.T) / 2


def main(contract_path=CONTRACT, qa_path=QA):
    contract = json.loads(contract_path.read_text())
    assert contract['confirmed'] and contract['decision_id'] in [
        'MILI-D-20261009-014', 'MILI-D-20261009-015', 'MILI-D-20261009-033']
    assert contract['original_scale'] and not contract['imputation'] and not contract['source_rescaling']
    qa_path.mkdir(parents=True, exist_ok=True)
    protected = sorted((ROOT / 'data/processed').rglob('*.parquet')) + [ROOT / 'docs/AnaSOP.md', contract_path]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    source = pd.read_parquet(ROOT / contract['input'])
    years = contract['periods']
    variables = [contract['outcome']] + contract['explanatory']
    assert len(source) == contract.get('source_observations', 32000) and not source.duplicated(['Mesh Code', 'Road Year']).any()
    history = source[source['Road Year'].isin(years)].copy()
    finite = np.isfinite(history[variables].to_numpy()).all(axis=1)
    counts = history.assign(finite=finite).groupby('Mesh Code')['finite'].sum()
    codes = sorted(counts.index[counts.eq(len(years))])
    sample = history[history['Mesh Code'].isin(codes)].sort_values(['Mesh Code', 'Road Year'])
    g, t = len(codes), len(years)
    n = len(sample)
    assert (g, n) == (contract['expected_meshes'], contract['expected_observations'])
    assert np.isfinite(sample[variables].to_numpy()).all() and n == g*t
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(g, t), np.tile(years, (g, 1)))
    array = sample[variables].to_numpy(dtype=float).reshape(g, t, len(variables))
    residualized = absorb_balanced(array)
    y = residualized[:, :, 0].reshape(n)
    x = residualized[:, :, 1:].reshape(n, 2)
    assert np.linalg.matrix_rank(x) == 2
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    full_rank = g + t - 1 + x.shape[1]
    residual_df = n - full_rank
    correction = g/(g-1) * (n-1)/residual_df
    covariance = cluster_covariance(x, residual, g, t, correction)
    assert np.linalg.eigvalsh(covariance).min() > 0
    se = np.sqrt(np.diag(covariance))
    z = NormalDist().inv_cdf((1+contract['confidence_level'])/2)
    bounds = np.column_stack((beta-z*se, beta+z*se))
    absorbed_r2 = 1-float(residual @ residual)/float(y @ y)

    # Independent equivalent representation: mesh-demeaned data with period indicators.
    mesh_demeaned = array-array.mean(axis=1, keepdims=True)
    indicators = np.eye(t)[:, 1:]
    centered_indicators = indicators-indicators.mean(axis=0)
    design_with_time = np.column_stack((mesh_demeaned[:, :, 1:].reshape(n, 2),
                                       np.tile(centered_indicators, (g, 1))))
    beta_with_time = np.linalg.lstsq(design_with_time, mesh_demeaned[:, :, 0].reshape(n), rcond=None)[0]
    residual_with_time = mesh_demeaned[:, :, 0].reshape(n)-design_with_time @ beta_with_time
    covariance_with_time = cluster_covariance(design_with_time, residual_with_time, g, t, correction)[:2, :2]
    assert np.allclose(beta, beta_with_time[:2], rtol=1e-10, atol=1e-10)
    assert np.allclose(residual, residual_with_time, rtol=1e-10, atol=1e-10)
    assert np.allclose(covariance, covariance_with_time, rtol=1e-9, atol=1e-12)
    assert np.allclose((x.T @ residual)/n, 0, atol=1e-9)
    assert np.allclose(residual.reshape(g, t).mean(axis=0), 0, atol=1e-10)
    assert np.allclose(residual.reshape(g, t).mean(axis=1), 0, atol=1e-10)
    assert sample[sample['Road Year'].eq(2003)]['Population'].reset_index(drop=True).equals(
        sample[sample['Road Year'].eq(2004)]['Population'].reset_index(drop=True))

    rows = [[name, float(b), float(s), float(lo), float(hi)]
            for name, b, s, (lo, hi) in zip(contract['explanatory'], beta, se, bounds)]
    rows.extend([
        ['Observations', n, None, None, None],
        ['Meshes / clusters', g, None, None, None],
        ['Periods', ', '.join(map(str, years)), None, None, None],
        ['Mesh fixed effects', 'Yes', None, None, None],
        ['Period fixed effects', 'Yes', None, None, None],
        ['Sample', contract.get('sample_label', 'Balanced historical pilot'), None, None, None],
        ['Outcome', contract['outcome'], None, None, None],
        ['Covariance', 'Mesh-clustered CR1', None, None, None],
        ['R-squared after both effects', absorbed_r2, None, None, None],
    ])
    assert len(rows) == 11
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Baseline'
    sheet.merge_cells('A1:E1')
    sheet['A1'] = contract['table_title']
    sheet['A1'].font = Font(name='Calibri', size=16, bold=True, color='17324D')
    sheet.merge_cells('A2:E2')
    sheet['A2'] = contract.get('geography_label', 'Fukuoka-area trial') + ' | Original-scale linear model | 2002, 2003, 2004, 2010'
    sheet['A2'].font = Font(name='Calibri', size=11, color='526679')
    headers = ['Term / diagnostic', 'Coefficient / value', 'Clustered standard error', '95% lower bound', '95% upper bound']
    for j, text in enumerate(headers, 1):
        cell = sheet.cell(4, j, text)
        cell.fill = PatternFill('solid', fgColor='17324D')
        cell.font = Font(name='Calibri', color='FFFFFF', bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    for i, row in enumerate(rows, 5):
        for j, value in enumerate(row, 1):
            cell = sheet.cell(i, j, value)
            cell.font = Font(name='Calibri', size=11)
            cell.alignment = Alignment(vertical='center', wrap_text=True,
                                       horizontal='left' if j == 1 or isinstance(value, str) else 'right')
            if i in [5, 6] and j > 1:
                cell.number_format = '0.00000000'
            if i % 2 == 1:
                cell.fill = PatternFill('solid', fgColor='F0F4F8')
    sheet['B15'].number_format = '0.000000'
    notes = [
        'Interpretation: within-mesh association conditional on Population and common period effects; no causal claim or local-heterogeneity estimate.',
        'Road Length Density is in km/km2; Population is in persons; Nighttime Radiance is the area-weighted mean in nW/cm2/sr.',
        f'Only the analysis selects complete historical meshes. All {len(source):,} source-panel records remain unchanged; existing 2024 candidate materials are preserved.',
        'Matched census years: 2000, 2005, 2005, 2010. The middle two periods reuse identical population; snapshots are not annual.',
        f'CR1 correction: G/(G-1) times (N-1)/(N-K), with G={g}, N={n}, K={full_rank} including fixed effects. Bounds use normal approximation.',
        'Clustering allows within-mesh dependence; neighboring-mesh dependence remains unresolved. Road inventory comparability is still conditional.',
        'R-squared uses only radiance variation remaining after both effects; it excludes the fit contributed by the fixed effects.',
        'Specification: original units, true zeros retained, equal weights; no imputation, log transformation, scaling, extra controls, or trends.',
    ]
    notes.extend(contract.get('additional_notes', []))
    for i, note in enumerate(notes, 18):
        sheet.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)
        cell = sheet.cell(i, 1, note)
        cell.font = Font(name='Calibri', size=10, color='526679')
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        sheet.row_dimensions[i].height = 29
    for name, width in zip('ABCDE', [35, 38, 23, 21, 21]):
        sheet.column_dimensions[name].width = width
    sheet.row_dimensions[1].height = 26
    sheet.row_dimensions[4].height = 31
    for i in range(5, 16):
        sheet.row_dimensions[i].height = 25
    sheet.freeze_panes = 'B5'
    sheet.auto_filter.ref = 'A4:E15'
    sheet.sheet_view.showGridLines = False
    sheet.print_options.horizontalCentered = True
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_area = f'A1:E{17+len(notes)}'
    output = ROOT / contract['output_workbook']
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    # Validate the exported numeric values rather than only the in-memory estimates.
    exported = load_workbook(output, data_only=True)
    assert exported.sheetnames == ['Baseline']
    view = exported['Baseline']
    for i, row in enumerate(rows, 5):
        for j, expected in enumerate(row, 1):
            actual = view.cell(i, j).value
            if isinstance(expected, float):
                assert np.isclose(actual, expected, rtol=1e-13, atol=1e-15)
            else:
                assert actual == expected, (i, j, actual, expected)
    assert all(sha(ROOT / p) == h for p, h in before.items())
    sample[['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']].to_csv(qa_path/'sample_membership.csv', index=False)
    coefficients = [dict(variable=name, coefficient=float(b), clustered_standard_error=float(s),
                         confidence_lower=float(lo), confidence_upper=float(hi))
                    for name, b, s, (lo, hi) in zip(contract['explanatory'], beta, se, bounds)]
    report = dict(status='passed', decision_id=contract['decision_id'], table_title=contract['table_title'],
                  outcome=contract['outcome'], coefficients=coefficients, observations=n, meshes=g, periods=years,
                  absorbed_r_squared=absorbed_r2, absorbed_regressor_rank=int(np.linalg.matrix_rank(x)),
                  full_design_rank=full_rank, residual_degrees_of_freedom=residual_df, cr1_factor=correction,
                  confidence_distribution=contract['confidence_distribution'],
                  equivalent_representation_max_coefficient_difference=float(np.abs(beta-beta_with_time[:2]).max()),
                  equivalent_representation_max_covariance_difference=float(np.abs(covariance-covariance_with_time).max()),
                  residual_orthogonality_passed=True, exported_values_verified=True,
                  source_hashes_unchanged=True, protected_sha256=before,
                  source_comparability_established=False, nationwide_model=contract.get('nationwide_model', False), causal_identification=False,
                  output=contract['output_workbook'], output_sha256=sha(output),
                  sample_membership_sha256=sha(qa_path/'sample_membership.csv'),
                  input=contract['input'], population_version=contract.get('population_version', 'previous source-unlisted-as-missing version'),
                  zero_population_observations=int(sample['Population'].eq(0).sum()),
                  covariance_reference='https://www.statsmodels.org/v0.12.2/_modules/statsmodels/stats/sandwich_covariance.html')
    (qa_path/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'protected_sha256'}, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Regional Fixed-Effects Baselines.

Plan: one regional comparison table under MILI-D-20261009-018.
Framework: AnaSOP Sections 5-7; original-scale separate regional OLS with
mesh and regional period effects, mesh-clustered CR1, normal 95% intervals.
"""
from pathlib import Path
from statistics import NormalDist
import json

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from table_pilot_fixed_effects_baseline import absorb_balanced, cluster_covariance, sha

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/regional-fixed-effects/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/regional-fixed-effects'


def fit_region(sample, contract):
    variables = [contract['outcome']] + contract['explanatory']
    t = len(contract['periods'])
    n = len(sample)
    g = sample['Mesh Code'].nunique()
    assert n == g*t and g > 2
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(g, t), np.tile(contract['periods'], (g, 1)))
    array = sample[variables].to_numpy(dtype=float).reshape(g, t, 3)
    assert np.isfinite(array).all()
    residualized = absorb_balanced(array)
    y = residualized[:, :, 0].reshape(n)
    x = residualized[:, :, 1:].reshape(n, 2)
    assert np.linalg.matrix_rank(x) == 2
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    rank = g + t - 1 + 2
    df = n - rank
    correction = g/(g-1) * (n-1)/df
    cov = cluster_covariance(x, residual, g, t, correction)
    assert np.linalg.eigvalsh(cov).min() > 0
    se = np.sqrt(np.diag(cov))
    z = NormalDist().inv_cdf((1 + contract['confidence_level'])/2)
    bounds = np.column_stack([beta-z*se, beta+z*se])
    r2 = 1 - float(residual @ residual) / float(y @ y)

    # Independent equivalent FE representation with explicit regional period indicators.
    mesh_demeaned = array - array.mean(axis=1, keepdims=True)
    indicators = np.eye(t)[:, 1:]
    indicators -= indicators.mean(axis=0)
    alternative = np.column_stack([mesh_demeaned[:, :, 1:].reshape(n, 2), np.tile(indicators, (g, 1))])
    alt_y = mesh_demeaned[:, :, 0].reshape(n)
    alt_beta = np.linalg.lstsq(alternative, alt_y, rcond=None)[0]
    alt_residual = alt_y - alternative @ alt_beta
    alt_cov = cluster_covariance(alternative, alt_residual, g, t, correction)[:2, :2]
    assert np.allclose(beta, alt_beta[:2], rtol=1e-10, atol=1e-10)
    assert np.allclose(residual, alt_residual, rtol=1e-10, atol=1e-10)
    assert np.allclose(cov, alt_cov, rtol=1e-9, atol=1e-12)
    assert np.allclose((x.T @ residual)/n, 0, atol=1e-9)
    assert np.allclose(residual.reshape(g, t).mean(axis=0), 0, atol=1e-10)
    assert np.allclose(residual.reshape(g, t).mean(axis=1), 0, atol=1e-10)
    assert np.array_equal(sample.loc[sample['Road Year'].eq(2003), 'Population'],
                          sample.loc[sample['Road Year'].eq(2004), 'Population'])
    coefficients = [dict(variable=name, coefficient=float(b), clustered_standard_error=float(s),
                         confidence_lower=float(lo), confidence_upper=float(hi))
                    for name, b, s, (lo, hi) in zip(contract['explanatory'], beta, se, bounds)]
    return dict(meshes=g, observations=n, coefficients=coefficients, absorbed_r_squared=r2,
                zero_population_observations=int(sample['Population'].eq(0).sum()),
                full_design_rank=rank, residual_degrees_of_freedom=df, cr1_factor=correction,
                absorbed_regressor_rank=2, residual_orthogonality_passed=True,
                equivalent_representation_max_coefficient_difference=float(abs(beta-alt_beta[:2]).max()),
                equivalent_representation_max_covariance_difference=float(abs(cov-alt_cov).max()))


def main(contract_path=CONTRACT, qa_path=QA):
    contract = json.loads(contract_path.read_text())
    assert contract['confirmed'] and contract['decision_id'] in ['MILI-D-20261009-018','MILI-D-20261009-034']
    assert contract['original_scale'] and not contract['imputation'] and not contract['source_rescaling']
    qa_path.mkdir(parents=True, exist_ok=True)
    protected = sorted((ROOT / 'data/processed').rglob('*.parquet')) + [
        ROOT / 'docs/AnaSOP.md', contract_path,
        ROOT / 'data/results/tables/Table_national_fixed_effects_baseline.xlsx',
        ROOT / 'data/results/tables/Table_pilot_fixed_effects_baseline.xlsx',
        ROOT / 'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv',
    ]
    protected.extend(ROOT / p for p in contract.get('additional_protected_files', []))
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    variables = [contract['outcome']] + contract['explanatory']
    columns = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year'] + variables
    source = pd.read_parquet(ROOT / contract['input'], columns=columns)
    assert len(source) == contract.get('source_observations',3891200) and not source.duplicated(['Mesh Code', 'Road Year']).any()
    finite = np.isfinite(source[variables].to_numpy()).all(axis=1)
    counts = source.assign(finite=finite).groupby('Mesh Code').finite.sum()
    codes = counts.index[counts.eq(4)]
    excluded = contract.get('excluded_mesh_codes', [])
    codes = codes[~codes.isin(excluded)]
    mapping = pd.read_parquet(ROOT / contract['region_mapping'])
    assert mapping['Mesh Code'].is_unique and len(mapping) == len(codes) == contract['expected_meshes']
    assert mapping['Assignment Status'].isin(contract.get('accepted_assignment_statuses',['assigned'])).all() and mapping.Region.notna().all()
    assert set(mapping['Mesh Code']) == set(codes)
    sample = source[source['Mesh Code'].isin(codes)].merge(mapping[['Mesh Code', 'Region']],
                                                         on='Mesh Code', how='left', validate='many_to_one')
    sample = sample.sort_values(['Mesh Code', 'Road Year'])
    assert len(sample) == contract['expected_observations'] and np.isfinite(sample[variables].to_numpy()).all()
    national = pd.read_csv(ROOT / contract.get('national_sample_membership','data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv'), dtype={'Mesh Code':'string'})
    national = national.loc[~national['Mesh Code'].isin(excluded)]
    for column in ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']:
        assert np.array_equal(sample[column].to_numpy(), national[column].to_numpy())
    assert sample.Region.value_counts().to_dict() == {k:v*4 for k,v in contract['expected_region_meshes'].items()}

    results = []
    rows = []
    for region in contract['regions']:
        subset = sample.loc[sample.Region.eq(region)].sort_values(['Mesh Code', 'Road Year'])
        result = fit_region(subset, contract)
        assert result['meshes'] == contract['expected_region_meshes'][region]
        result['region'] = region
        results.append(result)
        for term in result['coefficients']:
            rows.append([region, term['variable'], term['coefficient'], term['clustered_standard_error'],
                         term['confidence_lower'], term['confidence_upper'], result['meshes'],
                         result['observations'], result['absorbed_r_squared']])
        print(f"{region}: {result['meshes']:,} meshes; road coefficient {result['coefficients'][0]['coefficient']:.8f}", flush=True)
    assert len(rows) == 18 and sum(r['observations'] for r in results) == contract['expected_observations']
    assert sum(r['meshes'] for r in results) == contract['expected_meshes']

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Regional Baselines'
    sheet.merge_cells('A1:I1'); sheet['A1'] = contract['table_title']
    sheet['A1'].font = Font(name='Calibri', size=16, bold=True, color='17324D')
    sheet.merge_cells('A2:I2')
    sheet['A2'] = 'Nighttime Radiance | Original-scale OLS | Mesh and regional period effects | 2002, 2003, 2004, 2010'
    sheet['A2'].font = Font(name='Calibri', size=11, color='526679')
    headers = ['Region', 'Term', 'Coefficient', 'Clustered SE', '95% lower bound', '95% upper bound', 'Meshes / clusters', 'Observations', 'Absorbed R-squared']
    for j, value in enumerate(headers, 1):
        cell = sheet.cell(4, j, value)
        cell.font = Font(name='Calibri', bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='17324D')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    for i, row in enumerate(rows, 5):
        for j, value in enumerate(row, 1):
            cell = sheet.cell(i, j, value)
            cell.font = Font(name='Calibri', size=11)
            cell.alignment = Alignment(vertical='center', horizontal='left' if j < 3 else 'right')
            if j in [3, 4, 5, 6]: cell.number_format = '0.00000000'
            if j == 9: cell.number_format = '0.000000'
            if j in [7, 8]: cell.number_format = '#,##0'
            if ((i-5)//2) % 2 == 0: cell.fill = PatternFill('solid', fgColor='F0F4F8')
        sheet.row_dimensions[i].height = 25
    notes = [
        'Each region is estimated separately with Population as a control, mesh effects, regional period effects, and mesh-clustered CR1 covariance. Confidence bounds use a normal approximation.',
        f"The nine samples partition the accepted national balanced sample: {len(mapping):,} meshes and {len(sample):,} observations. Substantive inputs are unchanged, original units and true zeros retained.",
        f"Grouping follows MLIT automobile transportation statistics, with Okinawa included in Kyushu. Frozen 2024 administrative polygons allocate each mesh to its largest regional land intersection; all {int(mapping['Cross Region Mesh'].sum()):,} cross-region meshes remain included.",
        'Road Length Density: km/km2. Population: persons. Nighttime Radiance: mean nW/cm2/sr. Census years: 2000, 2005, 2005, 2010; the middle population snapshot is reused.',
        'CR1 correction is computed separately by region as G/(G-1) times (N-1)/(N-K), with all mesh and period effects counted in K. Absorbed R-squared excludes the fit of the fixed effects.',
        'Results are conditional within-mesh associations, not causal effects. Different regional significance decisions do not establish a significant difference between regions; no equality test is reported.',
        'Historical road measurement and harmonized lights remain source constraints. Mesh clustering does not resolve dependence across neighboring meshes; current administrative polygons are not historical land masks.',
    ]
    notes.extend(contract.get('additional_notes', []))
    for i, note in enumerate(notes, 25):
        sheet.merge_cells(start_row=i, start_column=1, end_row=i, end_column=9)
        sheet.cell(i, 1, note).font = Font(name='Calibri', size=10, color='526679')
        sheet.cell(i, 1).alignment = Alignment(wrap_text=True, vertical='top')
        sheet.row_dimensions[i].height = 30
    for col, width in zip('ABCDEFGHI', [22, 25, 16, 16, 18, 18, 18, 17, 19]):
        sheet.column_dimensions[col].width = width
    sheet.row_dimensions[1].height = 27; sheet.row_dimensions[4].height = 33
    sheet.freeze_panes = 'C5'; sheet.auto_filter.ref = 'A4:I22'; sheet.sheet_view.showGridLines = False
    sheet.page_setup.orientation = 'landscape'; sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1; sheet.page_setup.fitToHeight = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True; sheet.print_area = f'A1:I{24+len(notes)}'
    output = ROOT / contract['output_workbook']
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    exported = load_workbook(output, data_only=True)
    assert exported.sheetnames == ['Regional Baselines']
    for i, row in enumerate(rows, 5):
        for j, expected in enumerate(row, 1):
            actual = exported.active.cell(i, j).value
            if isinstance(expected, float): assert np.isclose(actual, expected, rtol=1e-13, atol=1e-15)
            else: assert actual == expected
    assert all(sha(ROOT / path) == digest for path, digest in before.items())
    membership = qa_path / 'sample_membership.csv'
    sample[['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year', 'Region']].to_csv(membership, index=False)
    report = dict(status='passed', decision_id=contract['decision_id'], outcome=contract['outcome'],
                  table_title=contract['table_title'], periods=contract['periods'], results=results,
                  input=contract['input'],region_mapping=contract['region_mapping'],
                  zero_population_observations=int(sample.Population.eq(0).sum()),
                  observations=len(sample), meshes=len(mapping), cross_region_meshes=int(mapping['Cross Region Mesh'].sum()),
                  sample_partition_verified=True, accepted_national_sample_keys_identical=not bool(excluded),
                  accepted_national_keys_match_after_declared_exclusions=True,excluded_mesh_codes=excluded,
                  exported_values_verified=True, protected_sha256=before, source_hashes_unchanged=True,
                  output=contract['output_workbook'], output_sha256=sha(output),
                  sample_membership_sha256=sha(membership), causal_identification=False,
                  formal_between_region_equality_test=False,
                  confidence_distribution=contract['confidence_distribution'])
    (qa_path / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved: {output.relative_to(ROOT)}', flush=True)
    print('All nine numerical equivalence checks, exhaustive partition, unchanged-input hashes, and workbook readback passed.', flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Prefecture Fixed-Effects Baselines.

Plan: one 47-prefecture comparison workbook under MILI-D-20261009-020.
Framework: AnaSOP Sections 5-7; the existing original-scale within-stratum
model, mesh and prefecture period effects, mesh-clustered CR1, 95% intervals.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from table_regional_fixed_effects_baselines import fit_region
from table_pilot_fixed_effects_baseline import sha

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/prefecture-fixed-effects/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/prefecture-fixed-effects'


def main():
    contract = json.loads(CONTRACT.read_text())
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261009-020'
    assert contract['original_scale'] and not contract['imputation'] and not contract['source_rescaling']
    QA.mkdir(parents=True, exist_ok=True)
    prior_tables = ['pilot', 'national', 'regional']
    protected = sorted((ROOT / 'data/processed').rglob('*.parquet')) + [CONTRACT, ROOT / 'docs/AnaSOP.md']
    protected += [ROOT / f'data/results/tables/Table_{unit}_fixed_effects_baseline{"s" if unit=="regional" else ""}.xlsx' for unit in prior_tables]
    membership_source = ROOT / 'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv'
    protected.append(membership_source)
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    variables = [contract['outcome']] + contract['explanatory']
    columns = ['Mesh Code','Road Year','Population Year','Nighttime Light Year'] + variables
    source = pd.read_parquet(ROOT / contract['input'], columns=columns)
    assert len(source) == 3891200 and not source.duplicated(['Mesh Code','Road Year']).any()
    finite = np.isfinite(source[variables].to_numpy()).all(axis=1)
    counts = source.assign(finite=finite).groupby('Mesh Code').finite.sum()
    codes = counts.index[counts.eq(4)]
    mapping = pd.read_parquet(ROOT / contract['prefecture_mapping'])
    assert mapping['Mesh Code'].is_unique and set(mapping['Mesh Code']) == set(codes)
    assert len(mapping) == 134830 and mapping['Assignment Status'].eq('assigned').all()
    assert mapping['Prefecture Code'].str.fullmatch(r'[0-9]{2}').all()
    assert mapping.groupby('Prefecture Code').Prefecture.nunique().eq(1).all()
    sample = source[source['Mesh Code'].isin(codes)].merge(mapping[['Mesh Code','Prefecture Code','Prefecture']],
                                                         on='Mesh Code', how='left', validate='many_to_one')
    sample = sample.sort_values(['Mesh Code','Road Year'])
    assert len(sample) == 539320 and np.isfinite(sample[variables].to_numpy()).all()
    national = pd.read_csv(membership_source, dtype={'Mesh Code':'string'})
    for col in columns[:4]:
        assert np.array_equal(sample[col].to_numpy(), national[col].to_numpy())
    assert sample['Prefecture Code'].value_counts().to_dict() == {code:count*4 for code,count in contract['expected_prefecture_meshes'].items()}
    results, rows = [], []
    for code in contract['prefectures']:
        subset = sample.loc[sample['Prefecture Code'].eq(code)].sort_values(['Mesh Code','Road Year'])
        result = fit_region(subset, contract)
        assert result['meshes'] == contract['expected_prefecture_meshes'][code]
        name = contract['prefecture_names'][code]
        assert subset.Prefecture.eq(name).all()
        result.update(prefecture_code=code, prefecture=name)
        results.append(result)
        for term in result['coefficients']:
            rows.append([code, name, term['variable'], term['coefficient'], term['clustered_standard_error'],
                         term['confidence_lower'], term['confidence_upper'], result['meshes'], result['observations'],
                         result['absorbed_r_squared']])
        print(f"{code} {name}: {result['meshes']:,} meshes; road coefficient {result['coefficients'][0]['coefficient']:.8f}", flush=True)
    assert len(results) == 47 and len(rows) == 94
    assert sum(r['meshes'] for r in results) == 134830 and sum(r['observations'] for r in results) == 539320

    workbook = Workbook(); sheet = workbook.active; sheet.title = 'Prefecture Baselines'
    sheet.merge_cells('A1:J1'); sheet['A1'] = contract['table_title']
    sheet['A1'].font = Font(name='Calibri', size=16, bold=True, color='17324D')
    sheet.merge_cells('A2:J2')
    sheet['A2'] = 'Nighttime Radiance | Original-scale OLS | Mesh and prefecture period effects | 2002, 2003, 2004, 2010'
    sheet['A2'].font = Font(name='Calibri', size=11, color='526679')
    headers = ['Prefecture Code','Prefecture','Term','Coefficient','Clustered SE','95% lower bound','95% upper bound','Meshes / clusters','Observations','Absorbed R-squared']
    for j, value in enumerate(headers, 1):
        cell = sheet.cell(4,j,value); cell.font = Font(name='Calibri',bold=True,color='FFFFFF')
        cell.fill = PatternFill('solid',fgColor='17324D'); cell.alignment = Alignment(wrap_text=True,vertical='center')
    for i, row in enumerate(rows,5):
        for j, value in enumerate(row,1):
            cell = sheet.cell(i,j,value); cell.font = Font(name='Calibri',size=11)
            cell.alignment = Alignment(vertical='center',horizontal='left' if j<4 else 'right')
            if j in [4,5,6,7]: cell.number_format = '0.00000000'
            if j in [8,9]: cell.number_format = '#,##0'
            if j==10: cell.number_format = '0.000000'
            if ((i-5)//2)%2==0: cell.fill = PatternFill('solid',fgColor='F0F4F8')
        sheet.row_dimensions[i].height = 25
    notes = [
        'Forty-seven separate models use Population as a control, mesh effects and prefecture-specific period effects, with mesh-clustered CR1 covariance and large-cluster normal confidence bounds.',
        'The same national balanced sample is partitioned exhaustively: 134,830 meshes and 539,320 observations. Original substantive values, true zeros, equal weights and matching years are unchanged.',
        'Assign each mesh directly to its largest prefecture land intersection using frozen 2024 administrative polygons. All 1,999 cross-prefecture meshes remain. No allocation differs from its prior implied transportation Region.',
        'Road Length Density is in km/km2; Population is in persons; Nighttime Radiance is mean nW/cm2/sr. Census years are 2000, 2005, 2005 and 2010, reusing the middle snapshot.',
        'Compute CR1 separately per prefecture: G/(G-1) times (N-1)/(N-K), counting all fixed effects in K. Absorbed R-squared excludes the fit contributed by fixed effects.',
        'Interpretation is conditional within-mesh association, not causality. Individual intervals are not adjusted for multiple comparisons; different signs or significance do not establish a formal between-prefecture difference.',
        'Road inventory comparability, harmonized lights, temporal matching and complete-data selection remain limits. Mesh clustering does not remove neighboring-mesh dependence; current geometry is not a historical land mask.',
    ]
    for i,note in enumerate(notes,101):
        sheet.merge_cells(start_row=i,start_column=1,end_row=i,end_column=10)
        cell = sheet.cell(i,1,note); cell.font = Font(name='Calibri',size=10,color='526679')
        cell.alignment = Alignment(wrap_text=True,vertical='top'); sheet.row_dimensions[i].height = 32
    for col,width in zip('ABCDEFGHIJ',[12,18,25,16,16,18,18,18,17,19]): sheet.column_dimensions[col].width = width
    sheet.row_dimensions[1].height = 27; sheet.row_dimensions[4].height = 33
    sheet.freeze_panes = 'D5'; sheet.auto_filter.ref = 'A4:J98'; sheet.sheet_view.showGridLines = False
    sheet.page_setup.orientation = 'landscape'; sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1; sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True; sheet.print_area = 'A1:J107'; sheet.print_title_rows = '4:4'
    output = ROOT / contract['output_workbook']; output.parent.mkdir(parents=True,exist_ok=True); workbook.save(output)
    exported = load_workbook(output,data_only=True)
    assert exported.sheetnames == ['Prefecture Baselines']
    for i,row in enumerate(rows,5):
        for j,expected in enumerate(row,1):
            actual = exported.active.cell(i,j).value
            if isinstance(expected,float): assert np.isclose(actual,expected,rtol=1e-13,atol=1e-15)
            else: assert actual == expected
    assert all(sha(ROOT/path)==digest for path,digest in before.items())
    membership = QA / 'sample_membership.csv'
    sample[columns[:4]+['Prefecture Code','Prefecture']].to_csv(membership,index=False)
    report = dict(status='passed', decision_id=contract['decision_id'], table_title=contract['table_title'],
                  outcome=contract['outcome'], periods=contract['periods'], results=results, meshes=len(mapping), observations=len(sample),
                  cross_prefecture_meshes=int(mapping['Cross Prefecture Mesh'].sum()),
                  prior_region_assignment_differences=int(mapping['Region Assignment Differs'].sum()),
                  sample_partition_verified=True, accepted_national_sample_keys_identical=True, exported_values_verified=True,
                  protected_sha256=before, source_hashes_unchanged=True, output=contract['output_workbook'], output_sha256=sha(output),
                  sample_membership_sha256=sha(membership), causal_identification=False,
                  formal_between_prefecture_equality_test=False, multiple_comparison_adjustment=False,
                  confidence_distribution=contract['confidence_distribution'])
    (QA/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved: {output.relative_to(ROOT)}',flush=True)
    print('All 47 FE equivalence, partition, input-preservation and workbook readback checks passed.',flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Prefecture Pooled Regressions with Census Structural Zeros.

Plan: One 47-prefecture comparison, MILI-D-20261009-040.
Framework: AnaSOP Sections 5-7; pooled intercept and two slopes, no fixed
effects, original units, mesh-clustered CR1 and normal 95% bounds.
--unaffected-only writes an experimental checkpoint for prefectures unaffected
by the nineteen unresolved geographic cases; it does not export a formal table.
"""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from table_regional_pooled_regressions_with_census_structural_zeros import fit_region
from table_national_pooled_regression_with_census_structural_zeros import sha

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/prefecture-pooled-population-zero-corrected/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/prefecture-pooled-population-zero-corrected'
GEOGRAPHY = ROOT / 'data/exp/data-preprocessing/prefecture-population-zero-corrected'


def checkpoint_unaffected(contract):
    """Compute only complete unaffected prefectures while approval is pending."""
    source = pd.read_parquet(ROOT / contract['input'])
    mapping = pd.read_csv(GEOGRAPHY / 'mesh_prefecture_confirmed_input.csv', dtype={'mesh_code': str, 'prefecture_code': str})
    proposals = pd.read_csv(ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected/unassigned_mesh_region_proposals.csv', dtype={'nearest_prefecture_code': str})
    affected = set(proposals.nearest_prefecture_code)
    names = json.loads((ROOT / 'data/exp/data-preprocessing/prefecture/classification_validation.json').read_text())['prefecture_names']
    sample = source.merge(mapping[['mesh_code', 'prefecture_code']].rename(columns={'mesh_code': 'Mesh Code', 'prefecture_code': 'Prefecture Code'}), on='Mesh Code', how='left', validate='many_to_one')
    sample['No Land Overlap'] = False
    results = []
    for code in contract['prefectures']:
        if code in affected:
            continue
        subset = sample.loc[sample['Prefecture Code'].eq(code)].sort_values(['Mesh Code', 'Road Year'])
        result = fit_region(subset, contract)
        result.update(prefecture_code=code, prefecture=names[code])
        results.append(result)
    assert len(results) == 42
    report = dict(status='unaffected_prefectures_numerically_checked', results=results,
                  affected_prefectures_pending_geographic_decision=sorted(affected),
                  input_sha256=sha(ROOT / contract['input']), classification_geometry_sha256=sha(GEOGRAPHY / 'mesh_prefecture_confirmed_input.csv'),
                  formal_table_generated=False, unresolved_meshes_assigned=False)
    (QA / 'unaffected_checkpoint.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Verified 42 unaffected prefectures; five await explicit geographic exception approval. No formal workbook generated.')


def main(unaffected_only=False):
    active = ROOT / 'data/exp/estimation-framework-planning/current-common-cohort/estimation_decisions.json'
    if active.exists() and not unaffected_only:
        from rerun_current_common_pooled import main as current_rerun
        return current_rerun('prefecture')
    current = ROOT / 'data/exp/estimation-framework-planning/five-period-2024/estimation_decisions.json'
    if current.exists() and not unaffected_only:
        from rerun_five_period_pooled import main as rerun
        return rerun('prefecture')
    contract = json.loads(CONTRACT.read_text())
    # MILI-D-20261011-046: preserve historical source contracts; redirect only export.
    contract['output_workbook'] = str((Path('data/exp/figure-table-generation/historical-baseline-tables/regenerated/four-period') / Path(contract['output_workbook']).name))
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261009-040'
    assert contract['effects'] == [] and contract['intercept'] and contract['original_scale'] and not contract['imputation']
    QA.mkdir(parents=True, exist_ok=True)
    if unaffected_only:
        checkpoint_unaffected(contract)
        return
    allocation = json.loads((ROOT / contract['allocation_decision']).read_text())
    assert allocation['confirmed'] and allocation['mode'] == 'reviewed_nearest_land'
    classification = json.loads((ROOT / contract['classification_validation']).read_text())
    assert classification['status'] == 'passed' and classification['exception_decision_id'] == allocation['decision_id']
    independent = json.loads((GEOGRAPHY / 'independent_geometry_validation.json').read_text())
    assert independent['status'] == 'passed' and independent['interior_strata_checked'] == 47
    output = ROOT / contract['output_workbook']
    protected = sorted((ROOT / 'data/processed').rglob('*.parquet'))
    protected += [p for p in (ROOT / 'data/results/tables').glob('*.xlsx') if p != output]
    protected += sorted((ROOT / 'data/exp/fe-experiments/tables').glob('*.xlsx'))
    protected += [CONTRACT, ROOT / 'docs/AnaSOP.md']
    protected += [ROOT / contract[key] for key in ['preprocessing_validation', 'national_validation', 'national_sample_membership', 'classification_validation', 'allocation_decision']]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    preprocessing = json.loads((ROOT / contract['preprocessing_validation']).read_text())
    assert sha(ROOT / contract['input']) == preprocessing['new_balanced_panel_sha256']
    source = pd.read_parquet(ROOT / contract['input'])
    mapping = pd.read_parquet(ROOT / contract['prefecture_mapping'])
    assert len(source) == contract['expected_observations'] and source['Mesh Code'].nunique() == contract['expected_meshes']
    assert mapping['Mesh Code'].is_unique and len(mapping) == contract['expected_meshes'] == classification['classification_meshes']
    assert set(mapping['Mesh Code']) == set(source['Mesh Code'])
    assert mapping['Prefecture Code'].str.fullmatch(r'[0-9]{2}').all()
    assert set(mapping['Prefecture Code']) == set(contract['prefectures'])
    assert mapping['Assignment Status'].isin(contract['accepted_assignment_statuses']).all()
    assert mapping.groupby('Prefecture Code').size().to_dict() == classification['prefecture_counts']
    assert int(mapping['No Land Overlap'].sum()) == contract['expected_reviewed_exceptions']
    names = classification['prefecture_names']
    assert np.array_equal(mapping['Prefecture'].to_numpy(), mapping['Prefecture Code'].map(names).to_numpy())
    sample = source.merge(mapping[['Mesh Code', 'Prefecture Code', 'Prefecture', 'No Land Overlap']], on='Mesh Code', how='left', validate='many_to_one')
    sample = sample.sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    keys = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']
    national = pd.read_csv(ROOT / contract['national_sample_membership'], dtype={'Mesh Code': str})
    assert sample[keys].astype({'Mesh Code': str}).equals(national)
    assert not sample.duplicated(['Mesh Code', 'Road Year']).any()
    variables = [contract['outcome']] + contract['explanatory']
    assert np.array_equal(sample[variables].to_numpy(), source.sort_values(['Mesh Code', 'Road Year'])[variables].to_numpy())
    checkpoint_path = QA / 'unaffected_checkpoint.json'
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else None
    if checkpoint:
        assert checkpoint['input_sha256'] == sha(ROOT / contract['input'])
    results, rows = [], []
    for code in contract['prefectures']:
        subset = sample.loc[sample['Prefecture Code'].eq(code)].sort_values(['Mesh Code', 'Road Year'])
        result = fit_region(subset, contract)
        assert result['meshes'] == classification['prefecture_counts'][code]
        result.update(prefecture_code=code, prefecture=names[code])
        if checkpoint and code not in checkpoint['affected_prefectures_pending_geographic_decision']:
            previous = next(r for r in checkpoint['results'] if r['prefecture_code'] == code)
            assert result == previous
        results.append(result)
        for estimate in result['coefficients']:
            rows.append([code, names[code], estimate['variable'], estimate['coefficient'], estimate['clustered_standard_error'],
                         estimate['confidence_lower'], estimate['confidence_upper'], result['meshes'], result['observations'], result['ordinary_pooled_r_squared']])
    assert len(results) == 47
    assert sum(r['meshes'] for r in results) == contract['expected_meshes']
    assert sum(r['observations'] for r in results) == contract['expected_observations']
    assert sum(r['zero_population_observations'] for r in results) == contract['expected_zero_population_observations']
    assert sum(r['reviewed_no_land_meshes'] for r in results) == contract['expected_reviewed_exceptions']
    headers = ['Prefecture Code', 'Prefecture', 'Term', 'Coefficient', 'Mesh-clustered standard error', 'Lower 95% confidence bound',
               'Upper 95% confidence bound', 'Meshes', 'Observations', 'Ordinary pooled R squared']
    table = pd.DataFrame(rows, columns=headers)
    assert table.shape == (141, 10)
    table.to_csv(QA / 'table.csv', index=False)
    sample[keys + ['Prefecture Code', 'Prefecture']].to_csv(QA / 'sample_membership.csv', index=False)
    wb = Workbook(); ws = wb.active; ws.title = 'Prefecture pooled regressions'
    ws.append([contract['table_title']]); ws.merge_cells('A1:J1'); ws['A1'].font = Font(size=13, bold=True)
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='254B6F')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[2].height = 45
    for row in rows: ws.append(row)
    for index, row in enumerate(ws.iter_rows(min_row=3, max_row=143), start=3):
        row[0].number_format = '@'
        for cell in row[3:7]: cell.number_format = '0.000000000' if row[2].value == 'Population' else '0.000000'
        row[9].number_format = '0.0000'
        if ((index-3)//3) % 2:
            for cell in row: cell.fill = PatternFill('solid', fgColor='EEF3F8')
    for column, width in zip('ABCDEFGHIJ', [14, 19, 25, 18, 24, 24, 24, 14, 16, 22]): ws.column_dimensions[column].width = width
    ws.freeze_panes='D3'; ws.auto_filter.ref='A2:J143'
    notes = wb.create_sheet('Notes'); notes.column_dimensions['A'].width=120
    lines = [
        'Outcome: Nighttime Radiance (nW/cm^2/sr); Road Length Density: km/km^2; Population: persons.',
        'Forty-seven separate equal-weight pooled OLS regressions with an intercept and two regressors; no mesh or period fixed effects.',
        'Road/light years 2002, 2003, 2004, 2010; population years 2000, 2005, 2005, 2010.',
        'All 228,988 meshes and 915,952 observations partition the current national balanced sample; all 274,959 population zeros remain.',
        'Direct largest-positive-prefecture-land-overlap classification with frozen 2024 polygons; independent of the previous Region assignment.',
        'Nineteen explicitly approved nearest-land prefecture exceptions retain flags and no invented land areas; see classification diagnostics.',
        'Mesh-clustered CR1, G/(G-1)*(N-1)/(N-3), evaluated separately per prefecture; normal-approximation 95% confidence bounds.',
        'Individual confidence bounds are exploratory and unadjusted for multiple comparisons across forty-seven prefectures.',
        'Ordinary pooled R squared uses each prefecture outcome mean and is joint fit of roads and population, not roads alone.',
        'Pooled slopes combine between-mesh and within-mesh patterns; no causal interpretation or formal between-prefecture difference test.',
        'Mesh clustering does not remove neighboring-mesh dependence or omitted-variable bias. Road comparability and reused population remain limits.',
        'No additional transforms, controls, weights or island exclusions; national and regional pooled outputs and all substantive source data unchanged.',
        'MILI-D-20261009-040; numerical validation completed; human output review pending.'
    ]
    for line in lines:
        notes.append([line]); notes.cell(notes.max_row,1).alignment=Alignment(wrap_text=True,vertical='top'); notes.row_dimensions[notes.max_row].height=32
    output.parent.mkdir(parents=True,exist_ok=True); wb.save(output)
    readback=load_workbook(output,data_only=True)['Prefecture pooled regressions']
    assert list(next(readback.iter_rows(min_row=2,max_row=2,values_only=True)))==headers
    for expected,actual in zip(rows,readback.iter_rows(min_row=3,max_row=143,values_only=True)):
        for a,b in zip(expected,actual):
            if isinstance(a,(int,float)):assert np.isclose(a,b,rtol=1e-13,atol=1e-14)
            else:assert a==b
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in protected}
    report=dict(status='passed',decision_id=contract['decision_id'],allocation_decision_id=allocation['decision_id'],table_title=contract['table_title'],
                results=results,meshes=contract['expected_meshes'],observations=contract['expected_observations'],
                zero_population_observations=contract['expected_zero_population_observations'],reviewed_no_land_meshes=19,
                effects=[],intercept=True,exact_national_partition_verified=True,exported_values_verified=True,
                protected_hashes_unchanged=True,protected_sha256=before,table_shape=[141,10],
                unaffected_checkpoint_reproduced=checkpoint is not None,output=contract['output_workbook'],output_sha256=sha(output),
                sample_membership_sha256=sha(QA/'sample_membership.csv'),causal_identification=False,
                formal_between_prefecture_coefficient_test=False,multiple_comparison_adjustment=False,human_output_review='pending')
    (QA/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    (QA/'README.md').write_text(
        '# Prefecture Pooled Regressions with Census Structural Zeros\n\n'
        'MILI-D-20261009-040; forty-seven separate pooled intercept-and-two-slope models, original units, no fixed effects. '
        'See table.csv, validation.json and sample_membership.csv for estimates and checks. '
        'The workbook contains 141 coefficient rows and ten columns.\n\n'
        'Reproduce locally: `python3 src/analyses/table_prefecture_pooled_regressions_with_census_structural_zeros.py`.\n\n'
        'All national balanced-sample meshes, population zeros and nineteen expressly reviewed exceptions are retained. '
        'Each model uses mesh-clustered CR1 and normal 95% intervals. Ordinary R squared describes joint fit. '
        'Intervals are exploratory and unadjusted for multiplicity; no formal between-prefecture coefficient test or causal interpretation.\n\n'
        'Equivalent representations, orthogonality, full-rank designs, exhaustive membership, source hashes and workbook readback pass. '
        'Protected AnaSOP hashes describe the fit-time document; later completion notes are recorded separately. '
        'National and regional pooled results remain unchanged. Human output review is pending.\n')
    print('Saved: '+contract['output_workbook'])
    print('All 47 models, national partition, retained zeros, protected inputs and workbook readback passed.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--unaffected-only',action='store_true')
    main(unaffected_only=parser.parse_args().unaffected_only)

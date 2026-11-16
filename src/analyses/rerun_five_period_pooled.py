"""Shared implementation for the three approved five-period pooled tables.

Each dedicated table script invokes exactly one model family. No fixed effects.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from table_regional_pooled_regressions_with_census_structural_zeros import fit_region, sha

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'data/processed/national/five_period'
QA_ROOT = ROOT / 'data/exp/figure-table-generation/five-period-2024'
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/five-period-2024/estimation_decisions.json'
TITLES = {'national': 'National Pooled Regression with Census Structural Zeros',
          'regional': 'Regional Pooled Regressions with Census Structural Zeros',
          'prefecture': 'Prefecture Pooled Regressions with Census Structural Zeros'}


def main(family):
    contract = json.loads(CONTRACT.read_text())
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261010-012'
    assert contract['effects'] == [] and contract['periods'] == [2002, 2003, 2004, 2010, 2024]
    audit = json.loads((ROOT / contract['preprocessing_validation']).read_text())
    source = ROOT / contract['input']
    assert audit['status'] == 'passed' and sha(source) == audit['balanced_panel_sha256']
    # MILI-D-20261011-046: historical regeneration stays outside the active handoff.
    output = ROOT / 'data/exp/figure-table-generation/historical-baseline-tables/regenerated/five-period-2024' / ('Table_' + TITLES[family].lower().replace(' ', '_') + '.xlsx')
    qa = QA_ROOT / family
    qa.mkdir(parents=True, exist_ok=True)
    protected = list((ROOT / 'data/processed').rglob('*.parquet'))
    protected += [p for p in (ROOT / 'data/results/tables').glob('*.xlsx') if p != output]
    protected += [CONTRACT, ROOT / 'docs/AnaSOP.md']
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    sample = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    mapping = pd.read_parquet(DEST / ('mesh_prefecture_national_preprocessed.parquet' if family == 'prefecture' else 'mesh_region_national_preprocessed.parquet'))
    assert mapping['Mesh Code'].is_unique and set(mapping['Mesh Code']) == set(sample['Mesh Code'])
    selected = ['Mesh Code', 'No Land Overlap']
    if family == 'regional': selected += ['Region']
    if family == 'prefecture': selected += ['Prefecture Code', 'Prefecture']
    sample = sample.merge(mapping[selected], on='Mesh Code', validate='many_to_one')
    assert len(sample) == audit['observations'] and sample['Mesh Code'].nunique() == audit['meshes']
    keys = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']
    group_columns = [] if family == 'national' else ['Region'] if family == 'regional' else ['Prefecture Code', 'Prefecture']
    sample[keys + group_columns].to_csv(qa / 'sample_membership.csv', index=False)
    results, rows = [], []
    if family == 'national': groups = [((), sample)]
    elif family == 'regional': groups = [( (name,), sample[sample.Region.eq(name)] ) for name in contract['regions']]
    else: groups = list(sample.groupby(['Prefecture Code', 'Prefecture'], sort=True))
    for labels, subset in groups:
        subset = subset.sort_values(['Mesh Code', 'Road Year'])
        fit = fit_region(subset, contract)
        fit['group'] = list(labels)
        results.append(fit)
        for e in fit['coefficients']:
            row = list(labels) + [e['variable'], e['coefficient'], e['clustered_standard_error'], e['confidence_lower'], e['confidence_upper']]
            if family != 'national': row += [fit['meshes'], fit['observations'], fit['ordinary_pooled_r_squared']]
            rows.append(row)
    assert len(results) == {'national': 1, 'regional': 9, 'prefecture': 47}[family]
    assert sum(r['meshes'] for r in results) == audit['meshes']
    assert sum(r['observations'] for r in results) == audit['observations']
    assert sum(r['zero_population_observations'] for r in results) == audit['zero_population_observations']
    if family == 'national':
        fit = results[0]
        diagnostics = [('Observations', fit['observations']), ('Meshes', fit['meshes']), ('Periods', 5),
                       ('Zero-population observations', fit['zero_population_observations']), ('Ordinary pooled R squared', fit['ordinary_pooled_r_squared']),
                       ('Mesh fixed effects', 'No'), ('Period fixed effects', 'No'), ('Intercept included', 'Yes'), ('Clustering', 'Mesh Code')]
        rows += [[a, b, None, None, None] for a, b in diagnostics]
    headers = group_columns + ['Term', 'Coefficient or diagnostic value' if family == 'national' else 'Coefficient',
                               'Mesh-clustered standard error', 'Lower 95% confidence bound', 'Upper 95% confidence bound']
    if family != 'national': headers += ['Meshes', 'Observations', 'Ordinary pooled R squared']
    expected = {'national': (12, 5), 'regional': (27, 9), 'prefecture': (141, 10)}[family]
    table = pd.DataFrame(rows, columns=headers)
    assert table.shape == expected
    table.to_csv(qa / 'table.csv', index=False)
    wb = Workbook(); ws = wb.active; ws.title = 'Pooled results'
    ws.append([TITLES[family]]); ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws['A1'].font = Font(size=13, bold=True); ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='254B6F')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[2].height = 50
    for row in rows: ws.append(row)
    for index, row in enumerate(ws.iter_rows(min_row=3), start=0):
        for cell in row:
            if isinstance(cell.value, float): cell.number_format = '0.000000000'
            if index // 3 % 2: cell.fill = PatternFill('solid', fgColor='EEF3F8')
    for index, header in enumerate(headers, start=1): ws.column_dimensions[get_column_letter(index)].width = 28 if family == 'national' else 24
    ws.freeze_panes = get_column_letter(len(group_columns) + 2) + '3'
    notes = wb.create_sheet('Notes')
    for line in [
        'Road/light years: 2002, 2003, 2004, 2010, 2024; population years: 2000, 2005, 2005, 2010, 2020.',
        'Outcome: mean Nighttime Radiance (nW/cm^2/sr); road density: km/km^2; Population: persons.',
        'Original-scale pooled OLS: intercept, Road Length Density, Population; equal weights and no fixed effects.',
        'The complete five-period cohort is shared by all four rerun model families; documented population zeros and island meshes retained.',
        'Mesh-clustered CR1 factor G/(G-1)*(N-1)/(N-3); normal 95% confidence bounds, unadjusted for multiple comparisons.',
        'Ordinary centered pooled R squared describes joint prediction by both regressors, not the separate road contribution.',
        '2024 ordinary-centerline lengths are allocated geometrically; source equivalence with historical supplied road density is not established.',
        'No road source rescaling or calibration. Source transitions can contribute to pooled slope differences.',
        '2024 uses 2020 population (four-year offset); the 2005 census snapshot is reused in 2003 and 2004.',
        'Frozen nine-region/47-prefecture assignments, including nineteen approved no-land exceptions, are retained.',
        'Conditional association only; no causal effect or formal between-area coefficient-equality test.',
        'MILI-D-20261010-012; numerical validation complete; human output review pending.'
    ]:
        notes.append([line]); notes.cell(notes.max_row, 1).alignment = Alignment(wrap_text=True)
        notes.row_dimensions[notes.max_row].height = 32
    notes.column_dimensions['A'].width = 120
    output.parent.mkdir(parents=True, exist_ok=True); wb.save(output)
    readback = load_workbook(output, data_only=True)['Pooled results']
    assert list(next(readback.iter_rows(min_row=2, max_row=2, values_only=True))) == headers
    for arow, brow in zip(rows, readback.iter_rows(min_row=3, max_row=len(rows)+2, values_only=True)):
        for a, b in zip(arow, brow):
            if isinstance(a, (int, float)): assert np.isclose(a, b, rtol=1e-13, atol=1e-14)
            else: assert a == b
    assert all(sha(ROOT / p) == digest for p, digest in before.items())
    report = dict(status='passed', decision_id=contract['decision_id'], family=family, table_title=TITLES[family],
                  meshes=audit['meshes'], observations=audit['observations'], periods=contract['periods'], population_years=contract['population_years'],
                  zero_population_observations=audit['zero_population_observations'], effects=[], results=results,
                  exact_national_partition_verified=True, workbook_readback_verified=True, input_sha256=sha(source),
                  output=str(output.relative_to(ROOT)), output_sha256=sha(output), table_shape=list(expected),
                  protected_hashes_unchanged=True, protected_sha256=before, human_output_review='pending',
                  source_comparability_established=False, source_calibration=False, causal_identification=False)
    (qa / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status='passed', family=family, output=report['output'],
                         summaries=[dict(group=r['group'], road=r['coefficients'][1], r_squared=r['ordinary_pooled_r_squared']) for r in results]), indent=2), flush=True)

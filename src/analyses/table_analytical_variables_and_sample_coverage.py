#!/usr/bin/env python3
"""Analytical Variables and Sample Coverage.

AnaSOP Sections 4-7: original-scale, available-case descriptive statistics at
mesh-period, distinct mesh or financial-government level. No model refitting.
Reproduce: uv run python src/analyses/table_analytical_variables_and_sample_coverage.py
"""
from pathlib import Path
import hashlib
import json
import os
import textwrap

os.environ.setdefault('MPLCONFIGDIR', '/tmp/tr01b-matplotlib-formal')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / 'data/exp/umd-four-layer/inputs/model_panel.parquet'
SCREEN = ROOT / 'data/exp/umd-mismatch-screen/mesh_screen_2024.parquet'
MUNICIPAL = ROOT / 'data/exp/umd-municipal-context/municipal_evidence_2024.parquet'
OUT = ROOT / 'data/results/tables/Table_analytical_variables_and_sample_coverage.xlsx'
AUDIT = ROOT / 'data/exp/figure-table-generation/analytical-variables-and-sample-coverage'
PERIODS = '2002, 2003, 2004, 2010, 2024'
TIME_VARYING = [
    ('Nighttime Radiance', 'nW/cm2/sr', PERIODS),
    ('Road Length Density', 'km/km2', PERIODS),
    ('Population', 'persons/mesh', '2000, 2005 (twice), 2010, 2020'),
    ('Urban Land Cover Share', 'area proportion', PERIODS),
    ('Forest Land Cover Share', 'area proportion', PERIODS),
    ('Cropland Land Cover Share', 'area proportion', PERIODS),
    ('Shrublands and Grasslands', 'area proportion', PERIODS),
    ('Water Land Cover Share', 'area proportion', PERIODS),
]
STATIC = [
    ('Distance to Railway Station', 'km', 'Railway Source Year', 2024),
    ('Distance to Passenger Airport', 'km', 'Airport Source Year', 2021),
    ('School Facility Count', 'facilities/mesh', 'School Facility Source Year', 2023),
    ('Medical Facility Count', 'facilities/mesh', 'Medical Facility Source Year', 2020),
    ('Logistics Facility Count', 'facilities/mesh', 'Logistics Facility Source Year', 2013),
    ('Visitor and Event Facility Count', 'facilities/mesh', 'Visitor and Event Facility Source Year', 2014),
]
GOVERNMENT = [
    ('Candidate Fraction of Supported Meshes', 'proportion', '2024 screen'),
    ('Length Weighted 24h Volume', 'vehicles/24 h', '2021'),
    ('Maintenance Share of Expenditure', 'ratio', 'FY2023'),
    ('Maintenance Share of Standard Fiscal Scale', 'ratio', 'FY2023'),
    ('Single Year Fiscal Revenue Need Ratio', 'ratio', 'FY2023'),
]

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    validation_paths = [ROOT / 'data/exp/umd-four-layer/pooled_validation.json',
                        SCREEN.parent / 'validation.json', MUNICIPAL.parent / 'validation.json']
    protected = [PANEL, SCREEN, MUNICIPAL, *validation_paths]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    pv, sv, mv = [json.loads(p.read_text()) for p in validation_paths]
    assert all(v['status'] == 'passed' for v in [pv, sv, mv])
    assert pv['input_sha256'] == sha(PANEL)
    assert sv['output_sha256'] == sha(SCREEN) and mv['output_sha256'] == sha(MUNICIPAL)
    for v in [sv, mv]:
        for path, digest in v['source_hashes'].items():
            assert sha(ROOT / path) == digest
    panel = pd.read_parquet(PANEL)
    screen = pd.read_parquet(SCREEN)
    municipal = pd.read_parquet(MUNICIPAL)
    assert len(panel) == 1916930 and panel['Mesh Code'].nunique() == 383386
    assert not panel.duplicated(['Mesh Code', 'Road Year']).any()
    assert panel.groupby('Mesh Code').size().eq(5).all()
    assert sorted(panel['Road Year'].unique()) == [2002, 2003, 2004, 2010, 2024]
    matches = panel[['Road Year', 'Population Year']].drop_duplicates().sort_values('Road Year')
    assert matches['Population Year'].tolist() == [2000, 2005, 2005, 2010, 2020]
    assert panel['Nighttime Light Year'].equals(panel['Road Year'])
    assert panel['Land Cover Year'].equals(panel['Road Year'])
    assert panel['Land Cover Product'].eq('MCD12Q1 Collection 6.1 UMD').all()
    assert len(screen) == 383386 and screen['Mesh Code'].is_unique
    assert set(screen['Mesh Code']) == set(panel['Mesh Code'])
    assert len(municipal) == 1741 and municipal['Government Code'].is_unique
    assert municipal['Fiscal Year'].eq(2023).all() and municipal['Traffic Year'].eq(2021).all()
    assert municipal['Road Year'].eq(2024).all() and municipal['Population Year'].eq(2020).all()
    latest = panel.loc[panel['Road Year'].eq(2024)].sort_values('Mesh Code')
    rows, details = [], []

    def summarize(frame, name, unit, periods, level, categorical=False):
        values = frame[name]
        valid = values.dropna()
        n, total = len(valid), len(values)
        row = {'Variable': name, 'Unit': unit, 'Source periods': periods,
               'Statistical unit': level, 'Valid count': n,
               'Missing (%)': 100 * (total - n) / total}
        if categorical:
            row.update({'Mean': np.nan, 'SD': np.nan, 'Median': np.nan})
            zero = None
        else:
            a = valid.to_numpy(dtype=float)
            assert np.isfinite(a).all()
            mean, sd, median = valid.astype(float).agg(['mean', 'std', 'median'])
            # Independent NumPy check, with sample SD (N-1 denominator).
            np.testing.assert_allclose([mean, sd, median],
                [np.mean(a), np.std(a, ddof=1), np.median(a)], rtol=1e-12, atol=1e-12)
            row.update({'Mean': float(mean), 'SD': float(sd), 'Median': float(median)})
            zero = int((a == 0).sum())
        rows.append(row)
        details.append({'variable': name, 'total': total, 'valid': n, 'missing': total-n,
                        'zeros': zero, 'statistical_unit': level,
                        'numeric_moments': not categorical})

    for name, unit, periods in TIME_VARYING:
        summarize(panel, name, unit, periods, 'Mesh-period')
    for name, unit, source_year, year in STATIC:
        assert panel[source_year].eq(year).all()
        assert panel.groupby('Mesh Code')[name].nunique(dropna=False).eq(1).all()
        summarize(latest, name, unit, str(year) + ' (static)', 'Mesh (static)')
    summarize(panel, 'Barren', 'area proportion', PERIODS, 'Mesh-period')
    summarize(screen, 'Potential Mismatch Candidate', '0/1 indicator', '2024 screen', 'Mesh')
    summarize(screen, 'Land Context', 'category', '2024 UMD', 'Mesh', categorical=True)
    for name, unit, periods in GOVERNMENT:
        summarize(municipal, name, unit, periods, 'Municipal government')
    result = pd.DataFrame(rows)
    assert result.shape == (22, 9)
    assert result['Variable'].is_unique
    assert len(screen['Potential Mismatch Candidate'].dropna()) == 376219
    assert int(screen['Potential Mismatch Candidate'].sum()) == 66097
    assert municipal['Length Weighted 24h Volume'].isna().sum() == 7
    categories = screen['Land Context'].value_counts(dropna=False).rename_axis('Land Context').reset_index(name='Meshes')
    categories['Share of all screen meshes (%)'] = 100 * categories['Meshes'] / len(screen)
    assert categories['Meshes'].sum() == 383386
    notes = [
        ('Scope', 'Descriptive coverage is conditional on the approved extended cohort: 383,386 meshes and 1,916,930 mesh-period records. It is not coverage of every Japanese land mesh.'),
        ('Excluded source cases', 'Four Minamitorishima meshes with unavailable land cover remain outside the extended cohort; their original missing values are preserved. No blanket island exclusion is used.'),
        ('Periods', 'Five irregular road/light periods: 2002, 2003, 2004, 2010, 2024. Population matches: 2000, 2005, 2005, 2010, 2020. Repeated 2005 values contribute twice to mesh-period summaries.'),
        ('Static facilities', 'Distances and counts are summarized once per mesh; the actual selected source editions are repeated unchanged across all five model periods.'),
        ('Original units', 'Land-cover shares and fiscal/mismatch ratios retain original values, without percent conversion, normalization, trimming or logarithms. Missing (%) is expressed as a percentage.'),
        ('SD', 'Sample standard deviation, with N-1 denominator. Numerical moments use available values only. True zeros are retained.'),
        ('Land cover', 'UMD six-category aggregation; water is the regression reference. Full-mesh shares are not renormalized under incomplete coverage.'),
        ('Mismatch', 'The binary mean is the candidate fraction among 376,219 supported meshes: 66,097 candidates. The 7,167 unsupported indicators remain missing, not zero. Land Context covers all 383,386 screen meshes; categorical moments are blank.'),
        ('Municipal assignment', 'Largest identified municipal overlap within fixed Prefecture, with designated-city parent consolidation. 320 meshes have unavailable government links, including 38 candidates; they remain in the mesh ledger.'),
        ('Government sample', '1,741 financial governments; seven traffic outcomes are unavailable. Municipal ratios use available supported denominators. Traffic is surveyed major-road territorial volume, whereas finance is own-government FY2023 expenditure and fiscal resources.'),
        ('Dates', 'Municipal screen: road/light and land context 2024, matched population 2020; surveyed traffic 2021; actual fiscal year 2023. These form a linked cross-section.'),
        ('Interpretation', 'Zero radiance does not establish zero economic activity. Potential mismatch is an empirical screen, not proven excessive roads, ownership-matched costs or a causal effect.'),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine='openpyxl') as writer:
        result.to_excel(writer, sheet_name='Variables and coverage', index=False)
        pd.DataFrame(notes, columns=['Topic', 'Note']).to_excel(writer, sheet_name='Notes', index=False)
        categories.to_excel(writer, sheet_name='Land context', index=False)
        wb = writer.book
        for ws in wb:
            ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='24516B')
                cell.alignment = Alignment(wrap_text=True, vertical='center')
            ws.row_dimensions[1].height = 32
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.font = Font(name='Calibri', size=11)
                    cell.alignment = Alignment(wrap_text=True, vertical='center')
                    if cell.row % 2 == 0:cell.fill = PatternFill('solid', fgColor='F1F5F8')
        ws = wb['Variables and coverage']
        for j, width in enumerate([43, 19, 37, 25, 16, 16, 16, 16, 16], start=1):
            ws.column_dimensions[get_column_letter(j)].width = width
        for row in ws.iter_rows(min_row=2):
            ws.row_dimensions[row[0].row].height = 34
            row[4].number_format = '#,##0'
            row[5].number_format = '0.00'
            # Keep small nonzero area shares visible (Barren mean is about 0.000313).
            decimals = 6 if row[1].value in ['area proportion', 'ratio', 'proportion', '0/1 indicator'] else 3
            for cell in row[6:]:cell.number_format = '#,##0.' + '0' * decimals
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = 'landscape'; ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 1
        ws.print_title_rows = '1:1'; ws.print_area = ws.dimensions
        wb['Notes'].column_dimensions['A'].width = 28
        wb['Notes'].column_dimensions['B'].width = 135
        for row in range(2, len(notes)+2):wb['Notes'].row_dimensions[row].height = 46
        for col, width in zip('ABC', [35, 18, 36]):wb['Land context'].column_dimensions[col].width = width
        for row in wb['Land context'].iter_rows(min_row=2):
            row[1].number_format = '#,##0';row[2].number_format = '0.00'
    readback = pd.read_excel(OUT, sheet_name='Variables and coverage')
    pd.testing.assert_frame_equal(result, readback, check_dtype=False, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(categories, pd.read_excel(OUT, sheet_name='Land context'), check_dtype=False)
    pd.testing.assert_frame_equal(pd.DataFrame(notes, columns=['Topic', 'Note']),
                                 pd.read_excel(OUT, sheet_name='Notes'), check_dtype=False)
    wb = load_workbook(OUT, data_only=False)
    assert wb['Variables and coverage'].max_row == 23 and wb['Variables and coverage'].max_column == 9
    assert not any(c.data_type == 'f' for ws in wb for row in ws for c in row)
    result.to_csv(AUDIT / 'table_values.csv', index=False)
    OUT.with_suffix('.caption.md').write_text('Analytical Variables and Sample Coverage. Original-scale available-case moments use the stated statistical unit. SD is the sample standard deviation. See the Notes and Land context sheets for cohort boundaries, date alignment, retained zeros, missing indicators and category counts. Numerical values in the workbook retain full precision.\n')
    cells = []
    for row in result.itertuples(index=False, name=None):
        decimals = 6 if row[1] in ['area proportion', 'ratio', 'proportion', '0/1 indicator'] else 3
        cells.append([textwrap.fill(str(row[0]), 31), str(row[1]), textwrap.fill(str(row[2]), 28),
                      textwrap.fill(str(row[3]), 22), f'{row[4]:,}', f'{row[5]:.2f}',
                      *['—' if pd.isna(v) else f'{v:,.{decimals}f}' for v in row[6:]]])
    fig, ax = plt.subplots(figsize=(20, 12));ax.axis('off')
    table = ax.table(cellText=cells, colLabels=[textwrap.fill(c, 16) for c in result.columns],
                     cellLoc='left', colWidths=[.21, .10, .18, .12, .09, .08, .075, .075, .075],
                     bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False);table.set_fontsize(9)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor('#d2dce2');cell.set_linewidth(.5)
        if r == 0:cell.set_facecolor('#24516b');cell.get_text().set_color('white');cell.get_text().set_weight('bold')
        elif r % 2 == 0:cell.set_facecolor('#f1f5f8')
    fig.subplots_adjust(left=.01, right=.99, top=.99, bottom=.01)
    fig.savefig(AUDIT / 'preview.png', dpi=120, facecolor='white');plt.close(fig)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    report = {'status': 'generated_pending_visual_and_human_review', 'title': 'Analytical Variables and Sample Coverage',
              'human_review': 'pending', 'rows': 22, 'columns': 9, 'cohort_meshes': 383386,
              'cohort_records': 1916930, 'municipal_governments': 1741,
              'statistics': details, 'source_hashes': hashes, 'source_values_unchanged': True,
              'workbook_all_main_cells_readback_verified': True, 'numpy_statistics_verified': True,
              'static_replication_verified': True, 'categorical_moments_blank': True,
              'workbook_sha256': sha(OUT), 'script_sha256': sha(Path(__file__))}
    (AUDIT / 'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Saved: {OUT.relative_to(ROOT)}')
    print(result.to_string(index=False))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Regional Pooled Regressions with Census Structural Zeros.

Plan: One nine-region comparison, MILI-D-20261009-039.
Framework: AnaSOP Sections 5-7; separate original-scale pooled OLS with
intercepts, no fixed effects, mesh-clustered CR1 and normal 95% bounds.
Run locally: python3 src/analyses/table_regional_pooled_regressions_with_census_structural_zeros.py
"""
from pathlib import Path
from statistics import NormalDist
import json

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from table_national_pooled_regression_with_census_structural_zeros import sha, cluster_covariance

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/regional-pooled-population-zero-corrected/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/regional-pooled-population-zero-corrected'


def fit_region(sample, contract):
    t = len(contract['periods'])
    n, g = len(sample), sample['Mesh Code'].nunique()
    assert n == g * t and g > 3
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(g, t), np.tile(contract['periods'], (g, 1)))
    assert np.array_equal(sample['Population Year'].to_numpy().reshape(g, t), np.tile(contract['population_years'], (g, 1)))
    assert np.array_equal(sample['Nighttime Light Year'].to_numpy(), sample['Road Year'].to_numpy())
    values = sample[[contract['outcome']] + contract['explanatory']].to_numpy(dtype=float)
    assert np.isfinite(values).all()
    y, regressors = values[:, 0], values[:, 1:]
    x = np.column_stack([np.ones(n), regressors])
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    assert rank == 3
    residual = y - x @ beta
    correction = g / (g - 1) * (n - 1) / (n - rank)
    covariance = cluster_covariance(x, residual, g, t, correction)
    assert np.linalg.eigvalsh(covariance).min() > 0
    se = np.sqrt(np.diag(covariance))
    assert np.isfinite(se).all() and (se > 0).all()

    # Verify an algebraically equivalent representation in the original units.
    mean, scale = regressors.mean(axis=0), regressors.std(axis=0)
    assert (scale > 0).all()
    alternate_x = np.column_stack([np.ones(n), (regressors - mean) / scale])
    alternate_beta, _, alternate_rank, _ = np.linalg.lstsq(alternate_x, y, rcond=None)
    transform = np.eye(3)
    transform[0, 1:] = -mean / scale
    transform[1:, 1:] = np.diag(1 / scale)
    equivalent_beta = transform @ alternate_beta
    alternate_residual = y - alternate_x @ alternate_beta
    equivalent_covariance = transform @ cluster_covariance(alternate_x, alternate_residual, g, t, correction) @ transform.T
    assert alternate_rank == rank
    np.testing.assert_allclose(beta, equivalent_beta, rtol=1e-9, atol=1e-10)
    np.testing.assert_allclose(covariance, equivalent_covariance, rtol=1e-8, atol=1e-12)
    normalized_scores = (alternate_x.T @ residual) / (np.linalg.norm(alternate_x, axis=0) * np.linalg.norm(residual))
    assert np.max(np.abs(normalized_scores)) < 1e-10
    population = sample['Population'].to_numpy().reshape(g, t)
    assert np.array_equal(population[:, 1], population[:, 2])
    rss = float(residual @ residual)
    centered_y = y - y.mean()
    tss = float(centered_y @ centered_y)
    r_squared = 1 - rss / tss
    assert 0 <= r_squared <= 1
    z = NormalDist().inv_cdf((1 + contract['confidence_level']) / 2)
    coefficients = [dict(variable=name, coefficient=float(b), clustered_standard_error=float(s),
                         confidence_lower=float(b-z*s), confidence_upper=float(b+z*s))
                    for name, b, s in zip(['Intercept'] + contract['explanatory'], beta, se)]
    return dict(meshes=int(g), observations=n, coefficients=coefficients,
                ordinary_pooled_r_squared=r_squared, zero_population_observations=int(sample['Population'].eq(0).sum()),
                reviewed_no_land_meshes=int(sample.loc[sample['No Land Overlap'], 'Mesh Code'].nunique()),
                design_rank=int(rank), residual_degrees_of_freedom=n-int(rank), cr1_factor=float(correction),
                covariance=covariance.tolist(), rss=rss, centered_outcome_tss=tss,
                equivalent_representation_max_coefficient_difference=float(np.max(np.abs(beta-equivalent_beta))),
                equivalent_representation_max_covariance_difference=float(np.max(np.abs(covariance-equivalent_covariance))),
                residual_orthogonality_passed=True, population_snapshot_reuse_verified=True)


def main():
    active = ROOT / 'data/exp/estimation-framework-planning/current-common-cohort/estimation_decisions.json'
    if active.exists():
        from rerun_current_common_pooled import main as current_rerun
        return current_rerun('regional')
    # The current approved scope supersedes the preserved four-period body.
    current = ROOT / 'data/exp/estimation-framework-planning/five-period-2024/estimation_decisions.json'
    if current.exists():
        from rerun_five_period_pooled import main as rerun
        return rerun('regional')
    contract = json.loads(CONTRACT.read_text())
    # MILI-D-20261011-046: preserve historical source contracts; redirect only export.
    contract['output_workbook'] = str((Path('data/exp/figure-table-generation/historical-baseline-tables/regenerated/four-period') / Path(contract['output_workbook']).name))
    assert contract['confirmed'] and contract['decision_id'] == 'MILI-D-20261009-039'
    assert contract['effects'] == [] and contract['intercept'] and contract['original_scale']
    assert contract['zeros_retained'] and not contract['imputation']
    QA.mkdir(parents=True, exist_ok=True)
    output = ROOT / contract['output_workbook']
    protected = sorted((ROOT / 'data/processed').rglob('*.parquet'))
    protected += [p for p in (ROOT / 'data/results/tables').glob('*.xlsx') if p != output]
    protected += sorted((ROOT / 'data/exp/fe-experiments/tables').glob('*.xlsx'))
    protected += [CONTRACT, ROOT / 'docs/AnaSOP.md']
    protected += [ROOT / contract[key] for key in ['preprocessing_validation', 'national_validation', 'national_sample_membership', 'classification_validation']]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    preprocessing = json.loads((ROOT / contract['preprocessing_validation']).read_text())
    national = json.loads((ROOT / contract['national_validation']).read_text())
    classification = json.loads((ROOT / contract['classification_validation']).read_text())
    assert national['status'] == classification['status'] == 'passed'
    assert sha(ROOT / contract['input']) == preprocessing['new_balanced_panel_sha256'] == national['input_sha256']
    assert sha(ROOT / contract['region_mapping']) == national['protected_sha256'][contract['region_mapping']]
    source = pd.read_parquet(ROOT / contract['input'])
    mapping = pd.read_parquet(ROOT / contract['region_mapping'])
    assert len(source) == contract['expected_observations'] and source['Mesh Code'].nunique() == contract['expected_meshes']
    assert mapping['Mesh Code'].is_unique and len(mapping) == contract['expected_meshes']
    assert set(mapping['Mesh Code']) == set(source['Mesh Code'])
    assert mapping['Region'].notna().all() and set(mapping['Region']) == set(contract['regions'])
    assert mapping['Assignment Status'].isin(contract['accepted_assignment_statuses']).all()
    assert mapping.groupby('Region').size().to_dict() == contract['expected_region_meshes']
    assert int(mapping['No Land Overlap'].sum()) == contract['expected_reviewed_exceptions']
    assert mapping.loc[mapping['No Land Overlap'], 'Assignment Status'].eq('reviewed_no_land_overlap').all()
    sample = source.merge(mapping[['Mesh Code', 'Region', 'No Land Overlap']], on='Mesh Code', how='left', validate='many_to_one')
    sample = sample.sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    assert not sample.duplicated(['Mesh Code', 'Road Year']).any()
    keys = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']
    membership = pd.read_csv(ROOT / contract['national_sample_membership'], dtype={'Mesh Code': str})
    assert sample[keys].astype({'Mesh Code': str}).equals(membership)
    assert int(sample['Population'].eq(0).sum()) == contract['expected_zero_population_observations']
    assert np.array_equal(sample[[contract['outcome']] + contract['explanatory']].to_numpy(),
                          source.sort_values(['Mesh Code', 'Road Year'])[[contract['outcome']] + contract['explanatory']].to_numpy())
    results, rows = [], []
    for region in contract['regions']:
        subset = sample.loc[sample['Region'].eq(region)].sort_values(['Mesh Code', 'Road Year'])
        result = fit_region(subset, contract)
        result['region'] = region
        assert result['meshes'] == contract['expected_region_meshes'][region]
        results.append(result)
        for estimate in result['coefficients']:
            rows.append([region, estimate['variable'], estimate['coefficient'], estimate['clustered_standard_error'],
                         estimate['confidence_lower'], estimate['confidence_upper'], result['meshes'],
                         result['observations'], result['ordinary_pooled_r_squared']])
    assert sum(r['meshes'] for r in results) == contract['expected_meshes']
    assert sum(r['observations'] for r in results) == contract['expected_observations']
    assert sum(r['zero_population_observations'] for r in results) == contract['expected_zero_population_observations']
    assert sum(r['reviewed_no_land_meshes'] for r in results) == contract['expected_reviewed_exceptions']
    headers = ['Region', 'Term', 'Coefficient', 'Mesh-clustered standard error', 'Lower 95% confidence bound',
               'Upper 95% confidence bound', 'Meshes', 'Observations', 'Ordinary pooled R squared']
    table = pd.DataFrame(rows, columns=headers)
    assert table.shape == (27, 9)
    table.to_csv(QA / 'table.csv', index=False)
    sample[keys + ['Region']].to_csv(QA / 'sample_membership.csv', index=False)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Regional pooled regressions'
    ws.append([contract['table_title']])
    ws.merge_cells('A1:I1')
    ws['A1'].font = Font(size=13, bold=True)
    ws.append(headers)
    for cell in ws[2]:
        cell.fill = PatternFill('solid', fgColor='254B6F')
        cell.font = Font(bold=True, color='FFFFFF')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[2].height = 45
    for row in rows:
        ws.append(row)
    for index, row in enumerate(ws.iter_rows(min_row=3, max_row=29), start=3):
        for cell in row[2:6]:
            cell.number_format = '0.000000000' if row[1].value == 'Population' else '0.000000'
        row[8].number_format = '0.0000'
        if ((index-3)//3) % 2:
            for cell in row:
                cell.fill = PatternFill('solid', fgColor='EEF3F8')
    for column, width in zip('ABCDEFGHI', [23, 25, 18, 24, 24, 24, 14, 16, 22]):
        ws.column_dimensions[column].width = width
    ws.freeze_panes = 'C3'
    ws.auto_filter.ref = 'A2:I29'
    notes = wb.create_sheet('Notes')
    lines = [
        'Outcome: Nighttime Radiance (nW/cm^2/sr); road density: km/km^2; Population: persons.',
        'Nine separate equal-weight pooled OLS regressions with intercept, road density and population; no mesh or period effects.',
        'Same corrected national balanced sample, partitioned exhaustively and exclusively into the approved nine Regions.',
        'Road/light years 2002, 2003, 2004, 2010; population years 2000, 2005, 2005, 2010.',
        'Original scales and documented zeros retained; no transformations, extra controls or island exclusions.',
        'Official transportation-statistics Region grouping; frozen administrative reference and approved land-overlap classification.',
        'All nineteen approved no-land exceptions retained: ten Kanto, seven Kinki and two Kyushu.',
        'One-way mesh-clustered CR1: G/(G-1)*(N-1)/(N-3), evaluated separately for each Region.',
        '95% confidence bounds use the large-cluster normal approximation; individual intervals are unadjusted for multiple comparisons.',
        'Ordinary centered pooled R squared uses the outcome mean within the Region; fit is jointly attributable to roads and population.',
        'Slopes describe pooled conditional associations combining between-mesh and within-mesh variation; no causal interpretation.',
        'Different estimates or significance decisions do not establish a formal between-region coefficient difference; no equality test is selected.',
        'Clustering allows dependence within meshes but does not remove neighboring-mesh dependence or omitted-variable bias.',
        '2005 population is reused; source comparability and historical coastline equivalence remain unresolved.',
        'MILI-D-20261009-039; numerical validation completed; human output review pending.'
    ]
    for line in lines:
        notes.append([line])
        notes.cell(notes.max_row, 1).alignment = Alignment(wrap_text=True, vertical='top')
        notes.row_dimensions[notes.max_row].height = 32
    notes.column_dimensions['A'].width = 120
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    readback = load_workbook(output, data_only=True)['Regional pooled regressions']
    assert list(next(readback.iter_rows(min_row=2, max_row=2, values_only=True))) == headers
    for expected, actual in zip(rows, readback.iter_rows(min_row=3, max_row=29, values_only=True)):
        for a, b in zip(expected, actual):
            if isinstance(a, (int, float)):
                assert np.isclose(a, b, rtol=1e-13, atol=1e-14)
            else:
                assert a == b
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    report = dict(status='passed', decision_id=contract['decision_id'], table_title=contract['table_title'],
                  regions=results, observations=len(sample), meshes=contract['expected_meshes'],
                  zero_population_observations=contract['expected_zero_population_observations'], reviewed_no_land_meshes=19,
                  effects=[], intercept=True, exact_national_partition_verified=True, substantive_values_unchanged=True,
                  exported_values_verified=True, protected_hashes_unchanged=True, protected_sha256=before,
                  output=contract['output_workbook'], output_sha256=sha(output), table_shape=[27, 9],
                  sample_membership_sha256=sha(QA / 'sample_membership.csv'), source_comparability_established=False,
                  causal_identification=False, formal_between_region_coefficient_test=False, human_output_review='pending')
    (QA / 'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    (QA / 'README.md').write_text(
        '# Regional Pooled Regressions with Census Structural Zeros\n\n'
        'MILI-D-20261009-039; one requested nine-region comparison under AnaSOP Sections 5-8. '
        'See validation.json for coefficients, covariance, sample diagnostics and numerical checks. '
        'table.csv mirrors the 27-row, 9-column workbook; sample_membership.csv records the exhaustive national partition.\n\n'
        'Reproduce locally: `python3 src/analyses/table_regional_pooled_regressions_with_census_structural_zeros.py`.\n\n'
        'Nine separate pooled regressions with intercept, Road Length Density and Population, original units, no fixed effects. '
        'Each model uses mesh-clustered CR1 and normal 95% confidence bounds. '
        'R squared is ordinary centered fit within each Region and describes joint prediction. '
        'Slopes are associational; no formal between-region equality test or causal claim is made.\n\n'
        'All 228,988 meshes, 915,952 observations, 274,959 population zeros and nineteen reviewed exceptions remain included. '
        'Numerical equivalents, residual orthogonality, membership, inputs and workbook readback pass. '
        'The national pooled result and experiment tables are unchanged. '
        'The AnaSOP checksum is a fit-time snapshot; subsequent completion notes are separately recorded. '
        'Human output review remains pending.\n')
    summary = [dict(region=r['region'], meshes=r['meshes'], coefficients=r['coefficients'],
                    ordinary_pooled_r_squared=r['ordinary_pooled_r_squared']) for r in results]
    print(json.dumps(dict(status='passed', output=contract['output_workbook'], regions=summary), indent=2))


if __name__ == '__main__':
    main()

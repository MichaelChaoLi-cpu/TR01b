"""Reconcile the approved municipal evidence to validated UMD mesh screening.

Uses the existing frozen jurisdiction ledger and verified fiscal/traffic inputs.
AnaSOP Sections 4-7, descriptive overall/context-specific fractions and Spearman.
No new geometry allocation, exclusions, thresholds, regression or causal model.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from run_municipality_mismatch_trial import sha, summarize_mesh, corr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/umd-municipal-context'
SCREEN = ROOT / 'data/exp/umd-mismatch-screen/mesh_screen_2024.parquet'
SCREEN_CHECK = ROOT / 'data/exp/umd-mismatch-screen/validation.json'
REF = ROOT / 'data/processed/national/municipality_mismatch_trial'
OLD = ROOT / 'data/exp/municipality-mismatch-trial'
OUTCOMES = ['Length Weighted 24h Volume', 'Maintenance Share of Expenditure',
            'Maintenance Share of Standard Fiscal Scale', 'Single Year Fiscal Revenue Need Ratio']
X = 'Candidate Fraction of Supported Meshes'

def main():
    geo_path = REF / 'mesh_municipality_reference_preprocessed.parquet'
    fiscal_path = REF / 'municipal_fiscal_reference_preprocessed.parquet'
    traffic_path = REF / 'municipal_traffic_reference_preprocessed.parquet'
    old_path = OLD / 'municipal_evidence_2024.parquet'
    old_check = OLD / 'delivery_validation.json'
    protected = [SCREEN, SCREEN_CHECK, geo_path, fiscal_path, traffic_path, old_path, old_check]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    check = json.loads(SCREEN_CHECK.read_text())
    assert check['status'] == 'passed' and check['classification'] == 'UMD'
    assert check['output_sha256'] == sha(SCREEN)
    assert json.loads(old_check.read_text())['status'] == 'passed'
    d = pd.read_parquet(SCREEN)
    geo = pd.read_parquet(geo_path)
    fiscal = pd.read_parquet(fiscal_path)
    old = pd.read_parquet(old_path).set_index('Government Code').sort_index()
    assert len(d) == len(geo) == 383386 and d['Mesh Code'].is_unique and geo['Mesh Code'].is_unique
    dg, gg = d.set_index('Mesh Code').sort_index(), geo.set_index('Mesh Code').sort_index()
    assert dg.index.equals(gg.index)
    # Separate native pandas string missing-sentinel metadata from code values.
    # Neither source column is cast, filled or overwritten by this comparison.
    pd.testing.assert_series_equal(dg['Prefecture Code'], gg['Prefecture Code'], check_dtype=False)
    ledger = d.merge(geo.drop(columns='Prefecture Code'), on='Mesh Code', how='left', validate='one_to_one')
    assert len(ledger) == len(d)
    for col in d:
        pd.testing.assert_series_equal(ledger[col], d[col])
    for col in geo.columns.difference(['Mesh Code', 'Prefecture Code']):
        pd.testing.assert_series_equal(ledger.set_index('Mesh Code').sort_index()[col], gg[col])
    assert ledger['Government Code'].isna().sum() == 320
    linked = ledger.dropna(subset=['Government Code'])
    meshes = pd.DataFrame([{'Government Code': code, **summarize_mesh(z)}
                          for code, z in linked.groupby('Government Code')])
    assert len(meshes) == len(fiscal) == 1741 and fiscal['Government Code'].is_unique
    assert set(meshes['Government Code']) == set(fiscal['Government Code']) == set(old.index)
    # Exact fiscal identity check: only screening-derived measures change.
    f = fiscal.set_index('Government Code').sort_index()
    for col in f:
        pd.testing.assert_series_equal(f[col], old[col])
    traffic_columns = [c for c in old.columns if c.startswith('Designated Managed ') or c in
        ['Survey Segment Rows', 'Surveyed Segment Length', 'Published Volume Length',
         'Published Volume Length Coverage', 'Length Weighted 24h Volume', 'Includes Estimated Direction Length']]
    a = fiscal.merge(meshes, on='Government Code', validate='one_to_one').merge(
        old[traffic_columns].reset_index(), on='Government Code', validate='one_to_one')
    for col, value in [('Road Year', 2024), ('Nighttime Light Year', 2024), ('Population Year', 2020), ('Traffic Year', 2021)]:
        a[col] = value
    a = a.sort_values('Government Code').reset_index(drop=True)
    indexed = a.set_index('Government Code')
    # Independently recompute counts/fractions from nullable indicators and IDs.
    for code, z in linked.groupby('Government Code'):
        supported = z['Potential Mismatch Candidate'].notna()
        c = z['Potential Mismatch Candidate'].eq(True).fillna(False)
        row = indexed.loc[code]
        assert row['Cohort Meshes'] == z['Mesh Code'].nunique()
        assert row['Supported Meshes'] == supported.sum()
        assert row['Candidate Meshes'] == c.sum()
        expected = c.sum() / supported.sum() if supported.any() else np.nan
        assert np.isclose(row[X], expected, equal_nan=True)
    # Validate old traffic values with an independent weighted sum of segments.
    t = pd.read_parquet(traffic_path)
    assert len(t) == 99417 and t['Traffic Year'].eq(2021).all()
    for code, z in t.groupby('Government Code'):
        valid = z['Published 24h Volume'].notna() & z['Segment Length'].gt(0)
        den = z.loc[valid, 'Segment Length'].sum()
        value = (z.loc[valid, 'Published 24h Volume'] * z.loc[valid, 'Segment Length']).sum() / den if den > 0 else np.nan
        assert np.isclose(value, indexed.loc[code, 'Length Weighted 24h Volume'], rtol=1e-13, equal_nan=True)
    for col in [*f.columns, *traffic_columns]:
        pd.testing.assert_series_equal(indexed[col], old[col])
    unlinked = ledger.loc[ledger['Government Code'].isna()]
    missing_candidates = int(unlinked['Potential Mismatch Candidate'].fillna(False).sum())
    assert int(a['Candidate Meshes'].sum()) + missing_candidates == check['candidate_meshes'] == 66097
    assert int(a['Supported Meshes'].sum()) + int(unlinked['Supported Comparison'].sum()) == check['supported_meshes'] == 376219
    assert int(a['Cohort Meshes'].sum()) + len(unlinked) == len(ledger)
    strata = []
    for (code, context), z in linked.groupby(['Government Code', 'Land Context']):
        c = z['Potential Mismatch Candidate'].fillna(False)
        n, k = int(z['Supported Comparison'].sum()), int(c.sum())
        zero = int(z.loc[c, 'Nighttime Radiance'].eq(0).sum())
        strata.append({'Government Code': code, 'Land Context': context, 'Cohort Meshes': len(z),
            'Supported Meshes': n, 'Candidate Meshes': k, 'Candidate Fraction of Supported Meshes': k / n if n else np.nan,
            'Candidate Zero Radiance Meshes': zero, 'Candidate Zero Radiance Fraction': zero / k if k else np.nan})
    land = pd.DataFrame(strata).merge(fiscal[['Government Code', 'Government Name', 'Prefecture', 'Government Type']],
                                    on='Government Code', validate='many_to_one')
    assert land['Cohort Meshes'].sum() == len(linked)
    assert land['Candidate Meshes'].sum() == a['Candidate Meshes'].sum()
    correlations = [corr(a, X, y, 'All municipal governments') for y in OUTCOMES]
    for context, z in land.groupby('Land Context'):
        joined = z.merge(a[['Government Code', *OUTCOMES]], on='Government Code', validate='one_to_one')
        correlations.extend(corr(joined, X, y, 'Land context: ' + context) for y in OUTCOMES)
    cor = pd.DataFrame(correlations)
    # Independent centered rank-dot verification for all four outcomes/eight scopes.
    for _, row in cor.iterrows():
        if row['Scope'] == 'All municipal governments':
            z = a
        else:
            context = row['Scope'].removeprefix('Land context: ')
            z = land.loc[land['Land Context'].eq(context)].merge(a[['Government Code', row['Outcome']]], on='Government Code', validate='one_to_one')
        pairs = z[[X, row['Outcome']]].replace([np.inf, -np.inf], np.nan).dropna()
        assert len(pairs) == row['Municipalities']
        if len(pairs) > 1:
            x, y = [pairs[col].rank(method='average').to_numpy(copy=True) for col in [X, row['Outcome']]]
            x -= x.mean(); y -= y.mean()
            den = np.sqrt((x @ x) * (y @ y))
            rho = (x @ y) / den if den > 0 else np.nan
        else:
            rho = np.nan
        assert np.isclose(rho, row['Spearman'], atol=1e-12, rtol=1e-12, equal_nan=True)
    OUT.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(OUT / 'municipal_mesh_ledger_2024.parquet', index=False)
    a.to_parquet(OUT / 'municipal_evidence_2024.parquet', index=False)
    a.to_csv(OUT / 'municipal_evidence_2024.csv', index=False)
    land.to_parquet(OUT / 'municipal_land_context_summary.parquet', index=False)
    cor.to_csv(OUT / 'municipal_context_rank_correlations.csv', index=False)
    unlinked[['Mesh Code', 'Land Context', 'Potential Mismatch Candidate', 'Supported Comparison',
              'Municipality Assignment Status']].to_csv(OUT / 'unlinked_meshes.csv', index=False)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    report = {'status': 'passed', 'classification': 'UMD', 'screen_decision_id': check['decision_id'],
        'figure_execution_decision_id': 'MILI-D-20261011-032', 'municipal_governments': len(a),
        'mesh_ledger_rows': len(ledger), 'linked_meshes': len(linked), 'unlinked_meshes': len(unlinked),
        'linked_candidates': int(a['Candidate Meshes'].sum()), 'unlinked_candidate_meshes': missing_candidates,
        'all_candidates': 66097, 'candidate_fraction_missing_governments': int(a[X].isna().sum()),
        'traffic_missing_governments': int(a[OUTCOMES[0]].isna().sum()),
        'fiscal_and_traffic_values_unchanged': True, 'geographic_assignments_unchanged': True,
        'municipal_counts_independently_checked': len(a), 'rank_comparisons_independently_checked': len(cor),
        'source_hashes': hashes, 'source_files_unchanged': True,
        'output_sha256': sha(OUT / 'municipal_evidence_2024.parquet'),
        'ledger_sha256': sha(OUT / 'municipal_mesh_ledger_2024.parquet'),
        'correlation_sha256': sha(OUT / 'municipal_context_rank_correlations.csv'),
        'year_alignment': {'road_light': 2024, 'population': 2020, 'traffic': 2021, 'fiscal': 2023},
        'national_correlations': cor.loc[cor['Scope'].eq('All municipal governments')].to_dict('records'),
        'candidate_fraction_range': [float(a[X].min()), float(a[X].max())]}
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (OUT / 'README.md').write_text(
        '# UMD municipal context\n\nReproduce with `python src/analyses/reconcile_umd_municipal_context.py`. '
        'Uses the validated UMD 2024 screen with the frozen mesh-government assignment. All fiscal '
        'fields, traffic values, years and missing outcomes agree with historical verified inputs; '
        'only screen-derived fractions and context summaries change. All 1,741 government counts '
        'and 32 overall/context outcome rank comparisons are independently checked. The full mesh '
        'ledger, unlinked assignments and zero-denominator contexts remain explicit. Territorial '
        'traffic is surveyed major-road traffic, whereas fiscal accounts are own-government FY2023 '
        'realized spending. They are not ownership-matched road costs or causal fiscal effects. '
        'No new threshold, regression, significance test or road-overprovision classification.\n')
    print(json.dumps({k: report[k] for k in ['status', 'municipal_governments', 'linked_candidates',
        'unlinked_candidate_meshes', 'candidate_fraction_missing_governments', 'national_correlations']}, indent=2), flush=True)

if __name__ == '__main__':
    main()

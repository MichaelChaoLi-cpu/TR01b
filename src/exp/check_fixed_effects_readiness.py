#!/usr/bin/env python3
"""Inspect historical pilot variation; do not fit a model or select its sample."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/feasibility-check/fixed-effects-readiness'
YEARS = [2002, 2003, 2004, 2010]
VARIABLES = ['Road Length Density', 'Population', 'Nighttime Radiance']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protected = sorted((ROOT / 'data/processed/pilot').glob('*.parquet')) + [ROOT / 'docs/AnaSOP.md']
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    panel = pd.read_parquet(ROOT / 'data/processed/pilot/road_population_light_pilot_preprocessed.parquet')
    assert len(panel) == 32000 and not panel.duplicated(['Mesh Code', 'Road Year']).any()
    historic = panel[panel['Road Year'].isin(YEARS)].copy()
    assert len(historic) == 25600 and historic['Mesh Code'].nunique() == 6400
    historic['joint_numeric'] = np.isfinite(historic[VARIABLES].to_numpy()).all(axis=1)
    counts = historic.groupby('Mesh Code')['joint_numeric'].sum()
    count_distribution = counts.value_counts().reindex(range(5), fill_value=0).sort_index()
    count_distribution.rename_axis('joint_numeric_periods').rename('meshes').to_csv(OUT / 'historical_coverage_period_count.csv')
    coverage = historic.groupby('Road Year')['joint_numeric'].agg(['sum', 'size']).reset_index()
    coverage.columns = ['road_year', 'joint_numeric_meshes', 'all_meshes']
    coverage.to_csv(OUT / 'historical_coverage_by_period.csv', index=False)
    balanced_codes = counts.index[counts.eq(4)]
    balanced = historic[historic['Mesh Code'].isin(balanced_codes)]
    assert len(balanced) == len(balanced_codes) * 4 and balanced['joint_numeric'].all()
    summaries, change_checks, distinct_counts = [], [], []
    for variable in VARIABLES:
        wide = balanced.pivot(index='Mesh Code', columns='Road Year', values=variable)[YEARS]
        x = wide.to_numpy(dtype=float)
        entity_mean = x.mean(axis=1, keepdims=True)
        period_mean = x.mean(axis=0, keepdims=True)
        grand_mean = x.mean()
        within = x - entity_mean
        # This closed form applies to the balanced diagnostic subset only.
        two_way = x - entity_mean - period_mean + grand_mean
        total_ss = float(((x - grand_mean) ** 2).sum())
        within_ss = float((within ** 2).sum())
        two_way_ss = float((two_way ** 2).sum())
        assert np.allclose(two_way.mean(axis=0), 0, atol=1e-9)
        assert np.allclose(two_way.mean(axis=1), 0, atol=1e-9)
        varying = np.ptp(x, axis=1) > 0
        summaries.append(dict(variable=variable, diagnostic_meshes=len(x), diagnostic_records=x.size,
                              meshes_with_recorded_within_change=int(varying.sum()),
                              meshes_with_constant_recorded_values=int((~varying).sum()),
                              share_meshes_with_recorded_within_change=float(varying.mean()),
                              overall_rms_deviation=float(np.sqrt(total_ss/x.size)),
                              mesh_demeaned_rms=float(np.sqrt(within_ss/x.size)),
                              two_way_demeaned_rms=float(np.sqrt(two_way_ss/x.size)),
                              mesh_demeaned_share_of_total_ss=within_ss/total_ss if total_ss else None,
                              two_way_demeaned_share_of_total_ss=two_way_ss/total_ss if total_ss else None))
        frequencies = wide.nunique(axis=1).value_counts().reindex(range(1, 5), fill_value=0)
        for n, mesh_count in frequencies.items():
            distinct_counts.append(dict(variable=variable, distinct_recorded_values=int(n), meshes=int(mesh_count)))
        for a, b in zip(YEARS[:-1], YEARS[1:]):
            delta = wide[b] - wide[a]
            change_checks.append(dict(variable=variable, earlier_year=a, later_year=b, diagnostic_meshes=len(wide),
                                      identical_recorded_values=int(delta.eq(0).sum()),
                                      share_identical_recorded_values=float(delta.eq(0).mean()),
                                      median_signed_change=float(delta.median()),
                                      median_absolute_change=float(delta.abs().median())))
    pd.DataFrame(summaries).to_csv(OUT / 'balanced_variation_summary.csv', index=False)
    pd.DataFrame(change_checks).to_csv(OUT / 'balanced_adjacent_change_checks.csv', index=False)
    pd.DataFrame(distinct_counts).to_csv(OUT / 'balanced_distinct_value_counts.csv', index=False)
    reused = balanced.pivot(index='Mesh Code', columns='Road Year', values='Population')
    assert reused[2003].equals(reused[2004])
    assert all(digest(ROOT / p) == h for p, h in before.items())
    report = dict(status='passed', decision_id='MILI-D-20261009-012',
                  anasop='docs/AnaSOP.md', historical_years=YEARS,
                  full_candidate_panel_records=len(panel), historical_diagnostic_records=len(historic),
                  historical_all_meshes=6400, historical_joint_numeric_records=int(counts.sum()),
                  meshes_with_at_least_two_joint_numeric_periods=int(counts.ge(2).sum()),
                  records_in_meshes_with_at_least_two_joint_numeric_periods=int(counts[counts.ge(2)].sum()),
                  historical_balanced_diagnostic_meshes=len(balanced_codes),
                  historical_balanced_diagnostic_records=len(balanced),
                  population_2003_2004_identical=True, variation_summary=summaries,
                  fixed_effect_dimensions_selected=False, outcome_selected=False,
                  source_comparability_established=False, nationwide_coverage_established=False,
                  estimator_fitted=False, estimation_sample_selected=False,
                  saved_processed_data_modified=False, input_hashes_unchanged=True,
                  protected_sha256=before)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'protected_sha256'}, indent=2))


if __name__ == '__main__':
    main()

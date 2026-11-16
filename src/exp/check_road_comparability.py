#!/usr/bin/env python3
"""Assess road source comparability without altering data or the research plan."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/feasibility-check/road-comparability'
PILOT = ROOT / 'data/exp/data-preprocessing/pilot'
REFERENCES = [
    ('historical_source_and_fields', 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N04.html'),
    ('latest_source_and_fields', 'https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N13-2024.html'),
    ('latest_width_classes', 'https://nlftp.mlit.go.jp/ksj/gml/codelist/N13_RoadWidth.html'),
    ('drm_current_width_definition', 'https://www.drm.jp/database/use/road-admin/doc-dbupdate/'),
    ('gsi_25000_width_definition', 'https://www.gsi.go.jp/common/000218185.pdf'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protected = list((ROOT / 'data/processed/pilot').glob('*.parquet')) + [ROOT / 'docs/AnaSOP.md']
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    panel = pd.read_parquet(ROOT / 'data/processed/pilot/road_population_light_pilot_preprocessed.parquet')
    assert len(panel) == 32000 and panel['Mesh Code'].nunique() == 6400
    density = panel.pivot(index='Mesh Code', columns='Road Year', values='Road Length Density')
    comparison = []
    for earlier, later in [(2002, 2003), (2003, 2004), (2004, 2010), (2010, 2024)]:
        paired = density[[earlier, later]].dropna()
        assert np.isfinite(paired.to_numpy()).all()
        positive = paired[earlier].gt(0)
        ratio = paired.loc[positive, later] / paired.loc[positive, earlier]
        comparison.append(dict(earlier_year=earlier, later_year=later,
                               common_numeric_meshes=len(paired), positive_denominator_meshes=int(positive.sum()),
                               earlier_density_mean=float(paired[earlier].mean()), later_density_mean=float(paired[later].mean()),
                               later_to_earlier_aggregate_density_ratio=float(paired[later].sum()/paired[earlier].sum()),
                               later_to_earlier_median_ratio=float(ratio.median()),
                               ratio_p10=float(ratio.quantile(.1)), ratio_p25=float(ratio.quantile(.25)),
                               ratio_p75=float(ratio.quantile(.75)), ratio_p90=float(ratio.quantile(.9)),
                               later_numeric_zero=int(paired[later].eq(0).sum()),
                               ratio_below_half=int(ratio.lt(.5).sum()), ratio_above_two=int(ratio.gt(2).sum()),
                               source_change=earlier == 2010 and later == 2024,
                               causal_or_growth_interpretation=False))
    pd.DataFrame(comparison).to_csv(OUT / 'matched_density_summary.csv', index=False)
    matched = density[[2010, 2024]].dropna().rename(columns={2010: 'density_2010', 2024: 'density_2024'})
    matched['ratio_2024_to_2010'] = matched.density_2024 / matched.density_2010.where(matched.density_2010.gt(0))
    matched.reset_index().to_csv(OUT / 'matched_density_2010_2024.csv', index=False)
    grid = pd.read_csv(PILOT / 'common_grid_trial.csv', dtype={'mesh_code': 'string'}).set_index('mesh_code')
    area_checks = []
    for year in [2002, 2003, 2004, 2010]:
        part = panel[panel['Road Year'].eq(year)].set_index('Mesh Code')
        areas = part['Mesh Area'].dropna()
        relative = (areas / grid.loc[areas.index, 'common_mesh_area_km2'] - 1).abs()
        normalization = (part['Road Length']/part['Mesh Area'] - part['Road Length Density']).abs().dropna()
        area_checks.append(dict(year=year, meshes_with_source_area=len(areas),
                                maximum_absolute_relative_area_difference_pct=float(relative.max()*100),
                                maximum_normalization_residual_m_per_km2=float(normalization.max()*1000)))
    pd.DataFrame(area_checks).to_csv(OUT / 'area_and_unit_checks.csv', index=False)
    latest = pd.read_csv(PILOT / '2024_road_grid_trial.csv')
    width_unknown = float(latest.unknown_width_length_km.sum())
    total_latest_length = float(latest.road_length_km.sum())
    dataset_inventory, variable_inventory = [], []
    for path in protected:
        if path.suffix != '.parquet':
            continue
        data = pd.read_parquet(path)
        name = str(path.relative_to(ROOT))
        dataset_inventory.append(dict(source=name, readable=True, rows=len(data), columns=len(data.columns)))
        for column in data:
            variable_inventory.append(dict(source=name, variable=column, dtype=str(data[column].dtype),
                                           missing_count=int(data[column].isna().sum()), nonmissing_count=int(data[column].notna().sum())))
    pd.DataFrame(dataset_inventory).to_csv(OUT / 'dataset_availability.csv', index=False)
    pd.DataFrame(variable_inventory).to_csv(OUT / 'variable_inventory.csv', index=False)
    question_checks = [
        dict(id='RQ1', status='partly-testable', topic='Spatial alignment across locations and comparable periods',
             evidence='Confirmed variables and candidate panel exist; latest-versus-historical measurement equivalence remains unverified.'),
        dict(id='RQ2', status='partly-testable', topic='Within-period spatial alignment',
             evidence='Numerical coverage supports descriptive within-period checks; model roles and local support are not selected.'),
        dict(id='RQ3', status='not-yet-testable', topic='Comparable five-period changes',
             evidence='Source transition coincides with the latest period. No same-year source bridge separates coverage effects from real changes.'),
        dict(id='RQ4', status='partly-testable', topic='Spatial heterogeneity in associations',
             evidence='Spatial inputs exist; road comparability, variation, local estimability and the final sample still need assessment.'),
    ]
    pd.DataFrame(question_checks).to_csv(OUT / 'question_feasibility.csv', index=False)
    pd.DataFrame(REFERENCES, columns=['evidence_item', 'official_url']).to_csv(OUT / 'official_references.csv', index=False)
    assert all(sha(ROOT / path) == digest for path, digest in before.items())
    report = dict(status='passed', assessment='measurement_equivalence_not_established',
                  common_grid_and_units_verified=True, source_equivalence_verified=False,
                  uniform_adjustment_factor_identified=False, source_effect_separable_from_time_effect=False,
                  matched_density_summary=comparison, area_checks=area_checks,
                  latest_unknown_width_length_km=width_unknown,
                  latest_unknown_width_share_pct=width_unknown/total_latest_length*100,
                  processed_datasets_inspected=len(dataset_inventory), column_entries_inspected=len(variable_inventory),
                  research_questions_inspected=4, question_checks=question_checks,
                  processed_data_and_anasop_unchanged=True, protected_sha256=before,
                  latest_zero_does_not_prove_historical_zero=True, imputation_performed=False,
                  source_scaling_performed=False, period_or_mesh_exclusions_applied=False,
                  official_references=dict(REFERENCES))
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'assessment', 'processed_datasets_inspected',
                     'column_entries_inspected', 'matched_density_summary', 'area_checks',
                     'latest_unknown_width_share_pct', 'processed_data_and_anasop_unchanged']}, indent=2))


if __name__ == '__main__':
    main()
